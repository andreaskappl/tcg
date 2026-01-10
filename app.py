import streamlit as st
import pandas as pd
from PIL import Image
import base64
from io import BytesIO
import os
import math
import requests
from supabase import create_client
from collections import defaultdict
from pathlib import Path
from streamlit_cookies_manager import EncryptedCookieManager


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

COOKIE_SECRET = os.environ.get("COOKIE_SECRET", "")
if not COOKIE_SECRET:
    raise RuntimeError("COOKIE_SECRET fehlt in den Env Vars (für Login-Persistenz).")

cookies = EncryptedCookieManager(prefix="pika_", password=COOKIE_SECRET)
if not cookies.ready():
    st.stop()

st.set_page_config(
    page_title="Pika",
    page_icon="assets/logo.png",
    layout="wide",
)

if "sb_session" not in st.session_state:
    st.session_state["sb_session"] = None
if "sb_user" not in st.session_state:
    st.session_state["sb_user"] = None

@st.cache_resource
def sb():
    """Supabase Client (anon key). Für Auth-Calls ok; DB-RLS greift über User-Token bei REST-Calls."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY fehlt in den Env Vars")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def _auth_headers(access_token: str | None = None) -> dict:
    h = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    if access_token:
        h["Authorization"] = f"Bearer {access_token}"
    return h


def refresh_session_with_token(refresh_token: str) -> dict:
    """
    Tauscht refresh_token -> neues access_token (und evtl. neues refresh_token).
    """
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token"
    r = requests.post(
        url,
        headers=_auth_headers(),
        json={"refresh_token": refresh_token},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_user(access_token: str) -> dict:
    """
    Holt User-Objekt über Supabase Auth REST.
    """
    url = f"{SUPABASE_URL}/auth/v1/user"
    r = requests.get(url, headers=_auth_headers(access_token), timeout=30)
    r.raise_for_status()
    return r.json()


def try_restore_login_from_cookie() -> bool:
    """
    Versucht beim App-Start automatisch einzuloggen:
    Cookie refresh_token -> neues access_token -> user holen.
    Speichert alles in st.session_state.
    """
    if try_restore_login_from_cookie():
        return True

    rt = cookies.get("refresh_token")
    if not rt:
        return False

    try:
        token_data = refresh_session_with_token(rt)
        access_token = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token") or rt
        if not access_token:
            raise RuntimeError(f"refresh_session: kein access_token erhalten: {token_data}")

        user_data = fetch_user(access_token)

        # Wir speichern Session minimal (nur was wir brauchen)
        st.session_state["sb_session"] = {
            "access_token": access_token,
            "refresh_token": new_refresh,
        }
        st.session_state["sb_user"] = {
            "id": user_data.get("id"),
            "email": user_data.get("email"),
        }

        # refresh_token kann rotieren -> Cookie aktualisieren
        cookies["refresh_token"] = new_refresh
        cookies.save()
        return True
    except Exception:
        # Cookie ungültig/abgelaufen -> löschen
        try:
            cookies.pop("refresh_token", None)
            cookies.save()
        except Exception:
            pass
        return False


def auth_gate():
    """Blockiert die gesamte App, bis der User eingeloggt ist."""
    if st.session_state.get("sb_session") and st.session_state.get("sb_user"):
        return

    st.title("🔐 Bitte anmelden")
    tab_login, tab_signup = st.tabs(["Login", "Registrieren"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        pw = st.text_input("Passwort", type="password", key="login_pw")
        if st.button("Login", key="btn_login"):
            try:
                res = sb().auth.sign_in_with_password({"email": email, "password": pw})
                if res.session is None or res.user is None:
                    st.error(
                        "Login fehlgeschlagen: Keine Session erhalten.\n"
                        "Mögliche Ursache: Email noch nicht bestätigt "
                        "oder Auth-Service nicht korrekt konfiguriert."
                    )
                    st.stop()
                st.session_state["sb_session"] = res.session
                st.session_state["sb_user"] = res.user
                # refresh_token im Cookie speichern -> Login bleibt über Reloads erhalten
                try:
                    if res.session and getattr(res.session, "refresh_token", None):
                        cookies["refresh_token"] = res.session.refresh_token
                        cookies.save()
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(f"Login fehlgeschlagen: {e}")

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        pw = st.text_input("Passwort", type="password", key="signup_pw")
        pw2 = st.text_input("Passwort bestätigen", type="password", key="signup_pw2")

        # Optional: kleine Live-Validierung (ohne Button-Klick)
        if pw and pw2 and pw != pw2:
            st.error("Passwörter stimmen nicht überein.")

        if st.button("Account erstellen", key="btn_signup"):
            if not email:
                st.error("Bitte Email eingeben.")
                st.stop()
            if not pw:
                st.error("Bitte Passwort eingeben.")
                st.stop()
            if pw != pw2:
                st.error("Passwörter stimmen nicht überein.")
                st.stop()

            try:
                sb().auth.sign_up({"email": email, "password": pw})
                st.success("Account erstellt. Bitte jetzt einloggen.")
            except Exception as e:
                st.error(f"Registrierung fehlgeschlagen: {e}")

    st.stop()

def logout_ui():
    u = st.session_state.get("sb_user")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Logout", key="btn_logout"):
            try:
                sb().auth.sign_out()
            except Exception:
                pass
            st.session_state["sb_session"] = None
            st.session_state["sb_user"] = None
            # Cookie löschen
            try:
                cookies.pop("refresh_token", None)
                cookies.save()
            except Exception:
                pass
            st.rerun()
    with col2:
        if u:
            email = u.get("email") if isinstance(u, dict) else getattr(u, "email", "")
            st.caption(f"Eingeloggt als: {email}")

def _sb_headers_user():
    """Headers für Supabase REST-Aufrufe im Kontext des eingeloggten Users."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY fehlt in den Env Vars")

    sess = st.session_state.get("sb_session")
    access_token = None

    # Session kann bei dir entweder ein Supabase Session-Objekt sein (nach Login)
    # oder unser dict (nach Cookie-Restore).
    if isinstance(sess, dict):
        access_token = sess.get("access_token")
    else:
        access_token = getattr(sess, "access_token", None)

    if not access_token:
        raise RuntimeError("Kein eingeloggter User / kein Access Token vorhanden")

    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

def create_stripe_checkout_url() -> str:
    """
    Ruft Supabase Edge Function 'create-checkout-session' auf und gibt die Stripe Checkout URL zurück.
    Nutzt den eingeloggten User (Bearer JWT) aus _sb_headers_user().
    """
    fn_url = f"{SUPABASE_URL}/functions/v1/create-checkout-session"
    r = requests.post(fn_url, headers=_sb_headers_user(), json={}, timeout=30)
    r.raise_for_status()
    data = r.json()
    url = data.get("url")
    if not url:
        raise RuntimeError(f"Keine Checkout-URL erhalten: {data}")
    return url


# Funktion, um lokale PNG in base64 Data-URL zu verwandeln
@st.cache_data(show_spinner=False)
def img_to_base64(img_path):
    try:
        if not os.path.exists(img_path):
            st.warning(f"Bild nicht gefunden: {img_path}. Platzhalter wird verwendet.")
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

        img = Image.open(img_path)

        buffered = BytesIO()

        # WICHTIG: kein PNG mehr erzwingen
        img = img.convert("RGB")
        img.save(buffered, format="WEBP", quality=70)

        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/webp;base64,{img_b64}"

    except Exception as e:
        st.error(f"Fehler beim Laden oder Konvertieren des Bildes {img_path}: {e}")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def image_for_ui(original_path: str) -> str:
    """
    Liefert optimiertes Bild (webp), falls vorhanden,
    sonst das Original.
    """
    p = Path(original_path)
    webp = p.with_suffix(".webp")
    return str(webp if webp.exists() else p)

def load_besitz_from_supabase(user_id: str):
    """Lädt die besessenen Karten-IDs des eingeloggten Users aus der Tabelle user_cards."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_cards"
        params = {"select": "karte_id", "user": f"eq.{user_id}"}
        r = requests.get(url, headers=_sb_headers_user(), params=params, timeout=30)
        r.raise_for_status()
        rows = r.json() or []
        return [row["karte_id"] for row in rows if "karte_id" in row]
    except Exception as e:
        st.warning(f"Fehler beim Laden aus Supabase: {e}")
        return []


def save_besitz_change_to_supabase(user: str, karte_id: str, add: bool) -> None:
    """
    add=True  -> INSERT/UPSERT einer (user, karte_id) Zeile
    add=False -> DELETE dieser Zeile
    """
    base = f"{SUPABASE_URL}/rest/v1/user_cards"

    if add:
        payload = [{"user": user, "karte_id": karte_id}]
        # on_conflict sorgt dafür, dass du keine Duplikate bekommst (PK user+karte_id)
        r = requests.post(
            base,
            headers=_sb_headers_user(),
            params={"on_conflict": "user,karte_id"},
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
    else:
        r = requests.delete(
            base,
            headers=_sb_headers_user(),
            params={"user": f"eq.{user}", "karte_id": f"eq.{karte_id}"},
            timeout=15,
        )
        r.raise_for_status()


def load_or_create_user_plan(user_id: str) -> str:
    """
    Lädt den Plan (basic/pro) aus public.user_profile für den eingeloggten User.
    Legt bei Bedarf einen basic-Eintrag an (RLS erlaubt insert own).
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_profile"
        params = {"select": "plan", "user_id": f"eq.{user_id}", "limit": "1"}
        r = requests.get(url, headers=_sb_headers_user(), params=params, timeout=15)
        r.raise_for_status()
        data = r.json() or []
        if data:
            plan = (data[0].get("plan") or "basic").lower()
            return plan

        # kein Profil vorhanden -> anlegen
        payload = [{"user_id": user_id, "plan": "basic"}]
        r2 = requests.post(url, headers=_sb_headers_user(), json=payload, timeout=15)
        r2.raise_for_status()
        return "basic"
    except Exception as e:
        # Fallback: App soll nicht kaputt gehen
        st.warning(f"Konnte Plan nicht laden/initialisieren (fallback=basic): {e}")
        return "basic"


def render_plan_sidebar(plan: str) -> None:
    """Zeigt Plan-Status + Upgrade via Stripe Checkout (Edge Function)."""
    st.sidebar.markdown(f"**Plan:** `{plan.upper()}`")

    if plan == "pro":
        return

    st.sidebar.caption("Du bist aktuell **Basic** User. Für Pro-Features bitte upgraden.")

    if st.sidebar.button("Upgrade to Pro", key="btn_upgrade_pro"):
        try:
            checkout_url = create_stripe_checkout_url()
            st.sidebar.success("Checkout erstellt. Bitte Zahlungsseite öffnen:")
            # Streamlit link_button ist ideal, weil er sauber eine externe URL öffnet.
            st.sidebar.link_button("➡️ Jetzt bezahlen", checkout_url, use_container_width=True)
            st.sidebar.caption("Nach der Zahlung wirst du automatisch zurückgeleitet.")
        except Exception as e:
            st.sidebar.error(f"Checkout konnte nicht erstellt werden: {e}")


# Filter zurücksetzen bei Benutzerwechsel
def reset_filter_session_state(df):

    if df.empty or df['pokemon_id'].dropna().empty:
        id_min, id_max = 0, 0
    else:
        id_min, id_max = int(df['pokemon_id'].min()), int(df['pokemon_id'].max())

    if df.empty or df['price'].dropna().empty:
        price_min, price_max = 0, 0
    else:
        price_min, price_max = math.floor(df['price'].min()), math.ceil(df['price'].max())

    reset_defaults = {
        "price_min": price_min,
        "price_max": price_max,
        "id_min": id_min,
        "id_max": id_max,
        "Besitzfilter": "Alle Karten",
        "pokemon_name": "",
        "multiselect_set": [],
        "multiselect_generation": [],
        "multiselect_rarity": []
    }

    for key, value in reset_defaults.items():
        st.session_state[key] = value

# CSS Styling
st.markdown("""
    <style>
    .card-box {
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 5px;
        background-color: #f9f9f9;
        display: flex;
        align-items: center;
        margin-bottom: 15px;
        width: 100%;
        box-sizing: border-box;
        color: #000000;
    }
    .card-text {
        margin-left: 15px;
        flex-grow: 1;
    }
    .card-box img {
        max-width: 120px;
        height: auto;
        object-fit: contain;
        margin-right: 10px;
    }
    .owned {
        background-color: #e6ffed !important;
        border: 2px solid #4CAF50 !important;
    }
    .custom-button {
        border-radius: 5px;
        padding: 8px 16px;
        font-size: 14px;
        cursor: pointer;
        width: 100%;
        text-align: center;
        border: 1px solid #444;
        background-color: #f5f5f5;
        color: #000;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }

    .custom-button:hover {
        background-color: #e0e0e0;
        border-color: #000;
        color: #000;
    }

    /* Streamlit-Standard-Button selektieren */
    button.css-19rxjzo.ef3psqc12 {  /* <-- Standardklasse von st.button() */
        border-radius: 5px;
        padding: 6px 12px;
        font-size: 13px;
        text-align: left;
        border: 1px solid #444;
        background-color: #f5f5f5;
        color: #000;
        margin-top: -6px;
        margin-bottom: 12px;
        width: 100%;
    }

    button.css-19rxjzo.ef3psqc12:hover {
        background-color: #e0e0e0;
        border-color: #000;
        color: #000;
    }
            
    @media (prefers-color-scheme: dark) {
        .card-box {
            background-color: #2c2c2c !important;
            border: 1px solid #555;
            color: #ffffff !important;
        }
        .card-text {
            color: #ffffff !important;
        }
    }
    </style>
""", unsafe_allow_html=True)



# Session State Initialisierung
auth_gate()  # muss davor stehen
logout_ui()

sb_user = st.session_state.get("sb_user")
if sb_user is None:
    st.stop()  # zur Sicherheit, falls auth_gate aus irgendeinem Grund nicht gestoppt hat

user = sb_user.id
# Plan (basic/pro) laden – fallback ist basic, damit die App nicht blockiert
plan = load_or_create_user_plan(user)
st.session_state["plan"] = plan

# --- Stripe Redirect Handling ---
# Stripe success_url / cancel_url setzt ?stripe=success oder ?stripe=cancel
stripe_state = st.query_params.get("stripe")

if stripe_state == "success":
    st.success("✅ Zahlung erfolgreich! Pro wird aktiviert …")
    # Plan neu laden (Webhook hat plan=pro gesetzt; falls minimal verzögert, hilft rerun)
    st.session_state["plan"] = load_or_create_user_plan(user)
    st.query_params.clear()
    st.rerun()

elif stripe_state == "cancel":
    st.info("Zahlung abgebrochen.")
    st.query_params.clear()
    st.rerun()


if "besitz" not in st.session_state:
    st.session_state["besitz"] = load_besitz_from_supabase(user)

# Daten einlesen
try:
    df = pd.read_csv("overview_cards.csv")
except FileNotFoundError:
    dummy_data = {
        'pokemon_id': [1, 1, 2],
        'pokemon_name': ['Bisasam', 'Bisasam', 'Glurak'],
        'set_name': ['Base Set', 'Jungle', 'Base Set'],
        'card_number': [1, 2, 3],
        'set_size': [102, 64, 102],
        'price': [40.9, 35.5, 150.0],
        'rarity': ['Rare', 'Uncommon', 'Rare Holo'],
        'img': ['./images/bisasam_1.png', './images/bisasam_2.png', './images/glurak_1.png']
    }
    df = pd.DataFrame(dummy_data)
    os.makedirs("./images", exist_ok=True)
    for img_path in df['img'].unique():
        if not os.path.exists(img_path):
            img = Image.new('RGB', (150, 200), color='lightgray')
            d = ImageDraw.Draw(img)
            d.text((10, 10), os.path.basename(img_path), fill=(0, 0, 0))
            img.save(img_path)
    df.to_csv("overview_cards.csv", index=False)

# Besitz ID vorbereiten
original_df = df.copy()
df["karte_id"] = df["set_name"].astype(str) + "_" + df["card_number"].astype(str)

# Benutzer
st.sidebar.subheader("👤 Benutzer")
sb_user_sidebar = st.session_state.get("sb_user")
if sb_user_sidebar:
    email = sb_user_sidebar.get("email") if isinstance(sb_user_sidebar, dict) else getattr(sb_user_sidebar, "email", "")
    st.sidebar.caption(email)
render_plan_sidebar(st.session_state.get("plan", "basic"))

if st.sidebar.button("Alle Filter zurücksetzen"):
    reset_filter_session_state(original_df)
    st.rerun()

# Besitzfilter (setzt standardmäßig auf "Alle Karten")
if "Besitzfilter" not in st.session_state:
    st.session_state["Besitzfilter"] = "Alle Karten"

besitz_filter = st.sidebar.selectbox(
    "Besitzfilter",
    options=["Alle Karten", "Nur Besitz", "Nur Nicht-Besitz"],
    index=["Alle Karten", "Nur Besitz", "Nur Nicht-Besitz"].index(st.session_state["Besitzfilter"]),
    key="Besitzfilter"
)

besessene_karten = set(st.session_state["besitz"])

# Filter auf Bearbeitungsmodus
if "show_buttons" not in st.session_state:
    st.session_state["show_buttons"] = False  # Standard: sichtbar

is_pro = (st.session_state.get("plan", "basic") == "pro")
st.session_state["show_buttons"] = st.sidebar.checkbox(
    "Kollektion bearbeiten",
    value=st.session_state["show_buttons"],
    disabled=(not is_pro),
)
if not is_pro:
    st.sidebar.caption("🔒 *Kollektion bearbeiten* ist ein Pro-Feature.")

# Filter anwenden auf Kopie von original_df
df = original_df.copy()
df["karte_id"] = df["set_name"].astype(str) + "_" + df["card_number"].astype(str)


if besitz_filter == "Nur Besitz":
    df = df[df["karte_id"].isin(besessene_karten)]
elif besitz_filter == "Nur Nicht-Besitz":
    df = df[~df["karte_id"].isin(besessene_karten)]

st.sidebar.markdown("---")

# Filter Sidebar
st.sidebar.header("🔍 Filter")
search_input = st.sidebar.selectbox("Pokémon suchen", [""] + sorted(df['pokemon_name'].unique()), key="pokemon_name")
if search_input:
    df = df[df['pokemon_name'] == search_input]

generations = df.get("generation", pd.Series(dtype=str)).dropna().unique().tolist()
opts = sorted(generations)

# Initial-Default nur beim ersten Mal setzen
if "multiselect_generation" not in st.session_state:
    st.session_state["multiselect_generation"] = []

# Gespeicherten Wert an aktuelle Optionen anpassen (sonst Exception)
st.session_state["multiselect_generation"] = [
    g for g in st.session_state["multiselect_generation"] if g in opts
]

if opts:
    # Kein default übergeben, wenn key verwendet wird – Streamlit nimmt den Sessionstate
    selected_generation = st.sidebar.multiselect(
        "Generation auswählen",
        options=opts,
        key="multiselect_generation",
    )
    if selected_generation:
        df = df[df["generation"].isin(selected_generation)]


# generations = df.get("generation", pd.Series()).dropna().unique()
# default_generations = [g for g in sorted(generations) if g in ["Karmesin & Purpur", "Mega-Entwicklungen"]]
# if "multiselect_generation" not in st.session_state:
#     st.session_state["multiselect_generation"] = default_generations
    
# if len(generations):
#     selected_generation = st.sidebar.multiselect("Generation auswählen", options=sorted(generations), default=st.session_state["multiselect_generation"], key="multiselect_generation")
#     if selected_generation:
#         df = df[df["generation"].isin(selected_generation)]

sets = df["set_name"].dropna().unique()
selected_set = st.sidebar.multiselect("Set auswählen", sorted(sets), key="multiselect_set")
if selected_set:
    df = df[df["set_name"].isin(selected_set)]

rarities = df["rarity"].dropna().unique()
selected_rarities = st.sidebar.multiselect("Seltenheiten auswählen", sorted(rarities), key="multiselect_rarity")
if selected_rarities:
    df = df[df["rarity"].isin(selected_rarities)]

# Preisfilter
st.sidebar.subheader("Preisbereich (€)")
df['price'] = pd.to_numeric(df['price'], errors='coerce')
if df.empty or df['price'].dropna().empty:
    price_min, price_max = 0, 0
else:
    price_min, price_max = math.floor(df['price'].min()), math.ceil(df['price'].max())
min_input = st.sidebar.number_input("Min €", value=price_min, key="price_min")
max_input = st.sidebar.number_input("Max €", value=price_max, key="price_max")
df = df[(df["price"] >= min_input) & (df["price"] <= max_input)]

# ID Filter
st.sidebar.subheader("🔢Pokémon ID")
df['pokemon_id'] = pd.to_numeric(df['pokemon_id'], errors='coerce')
if df.empty or df['pokemon_id'].dropna().empty:
    id_min, id_max = 0, 0
else:
    id_min, id_max = int(df['pokemon_id'].min()), int(df['pokemon_id'].max())
id_min_input = st.sidebar.number_input("Min ID", value=id_min, key="id_min")
id_max_input = st.sidebar.number_input("Max ID", value=id_max, key="id_max")
df = df[(df["pokemon_id"] >= id_min_input) & (df["pokemon_id"] <= id_max_input)]

st.sidebar.markdown("---")

# --- Statistiken in der Sidebar anzeigen ---
st.sidebar.markdown("### 📊 Zusammenfassung")

anzahl_pokemon = df["pokemon_name"].nunique()
gesamtwert = df["price"].sum()
gruppen = df.groupby("pokemon_name")
min_pro_gruppe = gruppen["price"].min().sum()
max_pro_gruppe = gruppen["price"].max().sum()

st.sidebar.markdown(f"**Anzahl der Karten:** {len(df)}")
st.sidebar.markdown(f"**Abgedeckte Pokémon:** {anzahl_pokemon}")
st.sidebar.markdown(f"**Gesamtwert aller Karten:** {gesamtwert:.0f}€")
st.sidebar.markdown(f"**Range (1 Karte / Pokemon):** {min_pro_gruppe:.0f}€ - {max_pro_gruppe:.0f}€")
if 'update' in df.columns and not df['update'].isnull().all():
    try:
        df['update_parsed'] = pd.to_datetime(df['update'], format='%d.%m.%Y', errors='coerce')
        latest_update = df['update_parsed'].max()
        if pd.notna(latest_update):
            st.sidebar.markdown(f"**Letztes Preisupdate:** {latest_update.strftime('%d.%m.%Y')}")
    except Exception as e:
        st.sidebar.warning(f"Fehler beim Ermitteln des letzten Updates: {e}")

# Berechnung basierend auf der aktuell gefilterten DataFrame "df"
gefilterte_karten = df["karte_id"].unique()
gefilterte_pokemon = df["pokemon_name"].unique()

besessene_karten = set(st.session_state["besitz"]) if user else set()
besessene_aus_filter = [k for k in gefilterte_karten if k in besessene_karten]

# Pokémon-Namen bestimmen, die der User aus dem Filter besitzt
pokemon_mit_besitz = df[df["karte_id"].isin(besessene_aus_filter)]["pokemon_name"].unique()

karten_fortschritt = len(besessene_aus_filter) / len(gefilterte_karten) if len(gefilterte_karten) > 0 else 0
pokemon_fortschritt = len(pokemon_mit_besitz) / len(gefilterte_pokemon) if len(gefilterte_pokemon) > 0 else 0

if True:

    st.sidebar.markdown("**🃏 Karten gesammelt**")
    st.sidebar.progress(karten_fortschritt)
    st.sidebar.caption(f"{len(besessene_aus_filter)} von {len(gefilterte_karten)} Karten ({karten_fortschritt*100:.0f}%)")

    st.sidebar.markdown("**🔢 Pokémon abgedeckt**")
    st.sidebar.progress(pokemon_fortschritt)
    st.sidebar.caption(f"{len(pokemon_mit_besitz)} von {len(gefilterte_pokemon)} Pokémon ({pokemon_fortschritt*100:.0f}%)")

# Gruppierung und Anzeige der Karten
for pokemon_name, gruppe in df.sort_values(by=["pokemon_name", "card_number"]).groupby("pokemon_name"):
    st.markdown(f"## {pokemon_name}")
    for _, row in gruppe.iterrows():
        img_b64 = img_to_base64(image_for_ui(row["img"]))
        karte_id = row["karte_id"]
        owned = karte_id in besessene_karten
        card_class = "card-box owned" if owned else "card-box"
        
        if 'G' in row['card_number']:
            card_number_str = str(row['card_number']) if pd.notna(row['card_number']) else ''
        else:
            card_number_str = str(int(row['card_number'])) if pd.notna(row['card_number']) else ''
        
        set_size_str = str(row['set_size']) if pd.notna(row['set_size']) else ''
        price_str = f"{row['price']:.1f}" if pd.notna(row['price']) else 'N/A'
        rarity_str = row['rarity'] if pd.notna(row['rarity']) else 'Unknown'
        update_str = row.get('update', '-')

        card_html = f"""
        <div class="{card_class}">
            <img src="{img_b64}" />
            <div class="card-text">
                <b>{row['pokemon_name']}</b><br>
                <i>{row['set_name']} #{card_number_str}/{set_size_str}</i><br>
                💰 <b>{price_str}€</b><span> (vom {update_str})</span><br>
                🌟 <span>{rarity_str}</span>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        if st.session_state.get("show_buttons", True):
            button_id = f"btn_{karte_id}"
            button_text = "❌ Aus Kollektion entfernen" if owned else "➕ Zur Kollektion hinzufügen"

            if st.button(button_text, key=f"button_{karte_id}"):
                try:

                    if owned:
                        st.session_state["besitz"].remove(karte_id)
                        save_besitz_change_to_supabase(user, karte_id, add=False)
                    else:
                        st.session_state["besitz"].append(karte_id)
                        save_besitz_change_to_supabase(user, karte_id, add=True)

                    st.rerun()

                except Exception as e:
                    st.warning(f"Speichern fehlgeschlagen: {e}")


