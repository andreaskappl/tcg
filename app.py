import streamlit as st
import pandas as pd
from PIL import Image
import base64
from io import BytesIO
import os
import math
from google.oauth2.service_account import Credentials
import gspread

# Funktion, um lokale PNG in base64 Data-URL zu verwandeln
def img_to_base64(img_path):
    try:
        if not os.path.exists(img_path):
            st.warning(f"Bild nicht gefunden: {img_path}. Platzhalter wird verwendet.")
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        img = Image.open(img_path)
        buffered = BytesIO()
        if img.mode != 'RGB' and img.mode != 'RGBA':
            img = img.convert('RGBA')
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_b64}"
    except Exception as e:
        st.error(f"Fehler beim Laden oder Konvertieren des Bildes {img_path}: {e}")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def load_besitz_from_gsheet():
    try:
        records = worksheet.get_all_records()
        if not records:
            return ["andi"], {"andi": []}

        df_sheet = pd.DataFrame(records)

        users = df_sheet['user'].unique().tolist()
        besitz = {user: df_sheet[df_sheet['user'] == user]['karte_id'].tolist() for user in users}

        return users, besitz
    except Exception as e:
        st.warning(f"Fehler beim Laden aus Google Sheet: {e}")
        return ["andi"], {"andi": []}

def save_besitz_to_gsheet():
    data = []
    for user, cards in st.session_state["besitz"].items():
        for karte_id in cards:
            data.append([user, karte_id])

    worksheet.clear()
    worksheet.update([['user', 'karte_id']] + data)
    # st.success("Besitzdaten erfolgreich gespeichert!")

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

# Google Sheets Setup
# Erst versuchen, aus Environment-Variable zu lesen (z. B. bei Deployment)
service_account_info = os.environ.get("GCP_SERVICE_ACCOUNT")

if service_account_info:
    # Temporär schreiben
    with open("service_account.json", "w") as f:
        f.write(service_account_info)
    print("🔐 Service Account aus Umgebungsvariable geladen.")
elif os.path.exists("service_account.json"):
    # Lokale Datei ist vorhanden
    print("📁 Lokale service_account.json wird verwendet.")
else:
    raise FileNotFoundError("❌ Kein gültiger Service Account gefunden.")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(credentials)

# Lösche temporäre Datei
if service_account_info:
    os.remove("service_account.json")

sheet_url = "https://docs.google.com/spreadsheets/d/16k-71_UMxxGVtQSVb4VSyEczJcmj_ldoC5iJG69-zFY/edit"
spreadsheet = client.open_by_url(sheet_url)
worksheet = spreadsheet.sheet1

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
if "users" not in st.session_state or "besitz" not in st.session_state:
    users, besitz = load_besitz_from_gsheet()
    st.session_state["users"] = users
    st.session_state["besitz"] = besitz

if "selected_user" not in st.session_state:
    st.session_state["selected_user"] = ""

if "adding_user" not in st.session_state:
    st.session_state["adding_user"] = False

if "last_user" not in st.session_state:
    st.session_state["last_user"] = st.session_state["selected_user"]

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

# Benutzerverwaltung
st.sidebar.subheader("👤 Benutzer")
user_options = [""] + st.session_state["users"] + ["➕ Neuen Benutzer anlegen..."]
user_labels = {"": "– Kein Benutzer ausgewählt –", "➕ Neuen Benutzer anlegen...": "➕ Neuen Benutzer anlegen..."}

selected = st.sidebar.selectbox(
    "Benutzer wählen",
    options=user_options,
    format_func=lambda x: user_labels.get(x, x),
    key="benutzerwahl"
)

if selected == "➕ Neuen Benutzer anlegen...":
    st.session_state["adding_user"] = True
    reset_filter_session_state(df)

elif selected != st.session_state["selected_user"]:
    st.session_state["selected_user"] = selected
    reset_filter_session_state(df)
    st.rerun()
else:
    st.session_state["adding_user"] = False

user = st.session_state["selected_user"]

if st.session_state["adding_user"]:
    with st.sidebar:
        new_name = st.text_input("Benutzername", key="new_user_name_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Erstellen"):
                if new_name.strip() and new_name not in st.session_state["users"]:
                    st.session_state["users"].append(new_name.strip())
                    st.session_state["besitz"][new_name.strip()] = []
                    st.session_state["selected_user"] = new_name.strip()
                    st.session_state["adding_user"] = False
                    st.rerun()
        with col2:
            if st.button("Abbrechen"):
                st.session_state["adding_user"] = False
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

besessene_karten = set(st.session_state["besitz"].get(user, []))

# Filter auf Bearbeitungsmodus
if "show_buttons" not in st.session_state:
    st.session_state["show_buttons"] = False  # Standard: sichtbar

st.session_state["show_buttons"] = st.sidebar.checkbox(
    "Kollektion bearbeiten", 
    value=st.session_state["show_buttons"]
)

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

generations = df.get("generation", pd.Series()).dropna().unique()
default_generations = [g for g in sorted(generations) if g in ["Karmesin & Purpur", "Mega-Entwicklungen"]]
if "multiselect_generation" not in st.session_state:
    st.session_state["multiselect_generation"] = default_generations
    
if len(generations):
    selected_generation = st.sidebar.multiselect("Generation auswählen", options=sorted(generations), default=st.session_state["multiselect_generation"], key="multiselect_generation")
    if selected_generation:
        df = df[df["generation"].isin(selected_generation)]

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

besessene_karten = set(st.session_state["besitz"].get(user, [])) if user else set()
besessene_aus_filter = [k for k in gefilterte_karten if k in besessene_karten]

# Pokémon-Namen bestimmen, die der User aus dem Filter besitzt
pokemon_mit_besitz = df[df["karte_id"].isin(besessene_aus_filter)]["pokemon_name"].unique()

karten_fortschritt = len(besessene_aus_filter) / len(gefilterte_karten) if len(gefilterte_karten) > 0 else 0
pokemon_fortschritt = len(pokemon_mit_besitz) / len(gefilterte_pokemon) if len(gefilterte_pokemon) > 0 else 0

if user and user.strip():

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
        img_b64 = img_to_base64(row["img"])
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

        if user and user.strip() and user in st.session_state["besitz"] and st.session_state.get("show_buttons", True):
            button_id = f"btn_{karte_id}"
            button_text = "❌ Aus Kollektion entfernen" if owned else "➕ Zur Kollektion hinzufügen"

            if st.button(button_text, key=f"button_{karte_id}"):
                if owned:
                    st.session_state["besitz"][user].remove(karte_id)
                else:
                    st.session_state["besitz"][user].append(karte_id)
                save_besitz_to_gsheet()
                st.rerun()
