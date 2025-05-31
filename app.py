

import streamlit as st
import pandas as pd
from PIL import Image
import base64
from io import BytesIO
import os

# Funktion, um lokale PNG in base64 Data-URL zu verwandeln
def img_to_base64(img_path):
    try:
        # Check if the file exists before opening
        if not os.path.exists(img_path):
            st.warning(f"Bild nicht gefunden: {img_path}. Platzhalter wird verwendet.")
            # Return a base64 of a placeholder image (1x1 transparent PNG)
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        
        img = Image.open(img_path)
        buffered = BytesIO()
        # Ensure the image is in a format that can be saved as PNG
        if img.mode != 'RGB' and img.mode != 'RGBA':
            img = img.convert('RGBA') # Convert to RGBA for consistency
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_b64}"
    except Exception as e:
        st.error(f"Fehler beim Laden oder Konvertieren des Bildes {img_path}: {e}")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

# CSS für den Kasten mit Bild links, Text rechts
st.markdown("""
    <style>
    .card-box {
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 5px;
        background-color: #f9f9f9;
        display: flex; /* Keep flex for image and text alignment within the card */
        align-items: center;
        margin-bottom: 15px; /* Add some space between stacked cards */
        width: 100%; /* Make each card take full width of its container */
        box-sizing: border-box; /* Include padding and border in the element's total width */
    }
    .card-text {
        margin-left: 15px;
        flex-grow: 1; /* Allow text to grow and take available space */
    }
    /* The .card-row CSS is no longer needed as cards are stacked */
    /* .card-row {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        margin-bottom: 25px;
        justify-content: flex-start;
    } */
    .card-box img {
        max-width: 120px; /* Adjust max width of image within the card */
        height: auto;
        object-fit: contain; /* Ensure image fits without distortion */
        margin-right: 10px; /* Space between image and text */
    }
    </style>
""", unsafe_allow_html=True)

# Beispiel: Daten laden (hier anpassen)
# Erstelle eine Dummy-CSV-Datei, falls sie nicht existiert, um den Code testbar zu machen
try:
    df = pd.read_csv("overview_cards.csv")
except FileNotFoundError:
    st.error("overview_cards.csv nicht gefunden. Erstelle eine Dummy-Datei.")
    dummy_data = {
        'pokemon_id': [1, 1, 1, 1, 2, 2, 3],
        'pokemon_name': ['Bisasam', 'Bisasam', 'Bisasam', 'Bisasam', 'Bisaknosp', 'Bisaknosp', 'Glurak'],
        'set_name': ['Base Set', 'Jungle', 'Fossil', 'Base Set', 'Base Set', 'Jungle', 'Base Set'],
        'card_number': [1, 2, 3, 4, 5, 6, 7],
        'set_size': [102, 64, 62, 102, 102, 64, 102],
        'price': [40.9, 35.5, 20.0, 50.0, 33.0, 28.0, 150.0],
        'rarity': ['Rare', 'Uncommon', 'Common', 'Rare Holo', 'Rare', 'Uncommon', 'Rare Holo'],
        'img': ['./images/bisasam_1.png', './images/bisasam_2.png', './images/bisasam_3.png', './images/bisasam_4.png', './images/bisaknosp_1.png', './images/bisaknosp_2.png', './images/glurak_1.png']
    }
    df = pd.DataFrame(dummy_data)
    # Erstelle Dummy-Bilder für Testzwecke
    os.makedirs("./images", exist_ok=True)
    # Create simple dummy PNG files
    from PIL import Image, ImageDraw
    for img_path in df['img'].unique():
        if not os.path.exists(img_path):
            img = Image.new('RGB', (150, 200), color = 'lightgray')
            d = ImageDraw.Draw(img)
            d.text((10,10), os.path.basename(img_path), fill=(0,0,0))
            img.save(img_path)
    df.to_csv("overview_cards.csv", index=False)


# Sidebar: Filteroptionen (dein bisheriger Filtercode)
st.sidebar.header("🔍 Filter")

generations = df["generation"].unique()
selected_generation = st.sidebar.selectbox("Generation auswählen", ["Alle"] + list(generations))
if selected_generation != "Alle":
    df = df[df["generation"] == selected_generation]

sets = df["set_name"].unique()
selected_set = st.sidebar.selectbox("Set auswählen", ["Alle"] + list(sets))
if selected_set != "Alle":
    df = df[df["set_name"] == selected_set]

rarities = df["rarity"].dropna().unique()
selected_rarities = st.sidebar.multiselect("Seltenheiten auswählen", sorted(rarities))
if selected_rarities:
    df = df[df["rarity"].isin(selected_rarities)]

# Ensure price and id are numeric for min/max calculations
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['pokemon_id'] = pd.to_numeric(df['pokemon_id'], errors='coerce')
df.dropna(subset=['price', 'pokemon_id'], inplace=True)

# --- Preisbereich ---
st.sidebar.subheader("💰 Preisbereich (€)")

price_min_val = int(df["price"].min()) if not df["price"].empty else 0
price_max_val = int(df["price"].max()) if not df["price"].empty else 1000

col1, col2 = st.sidebar.columns(2)
with col1:
    price_min = st.number_input("Min €", min_value=price_min_val, max_value=price_max_val,
                                value=price_min_val, step=1, key="price_min")
with col2:
    price_max = st.number_input("Max €", min_value=price_min_val, max_value=price_max_val,
                                value=price_max_val, step=1, key="price_max")

df = df[(df["price"] >= price_min) & (df["price"] <= price_max)]

# --- Pokémon ID Bereich ---
st.sidebar.subheader("🔢 Pokémon ID")

id_min_val = int(df["pokemon_id"].min()) if not df["pokemon_id"].empty else 0
id_max_val = int(df["pokemon_id"].max()) if not df["pokemon_id"].empty else 999

col3, col4 = st.sidebar.columns(2)
with col3:
    id_min = st.number_input("Min ID", min_value=id_min_val, max_value=id_max_val,
                             value=id_min_val, step=1, key="id_min")
with col4:
    id_max = st.number_input("Max ID", min_value=id_min_val, max_value=id_max_val,
                             value=id_max_val, step=1, key="id_max")

df = df[(df["pokemon_id"] >= id_min) & (df["pokemon_id"] <= id_max)]
# Filter anwenden

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

gruppen = df.groupby("pokemon_name")

for pokemon_name, gruppe in gruppen:
    st.markdown(f"## {pokemon_name}")
    
    # Sortiere die Gruppe nach Kartennummer für eine konsistente Anzeige
    gruppe = gruppe.sort_values(by='card_number').reset_index(drop=True)

    # Iteriere über jede Karte in der Gruppe und zeige sie einzeln an
    for _, row in gruppe.iterrows():
        img_b64 = img_to_base64(row["img"])  # img ist der Pfad zum PNG

        # Ensure card_number and set_size are integers before formatting
        card_number_str = str(int(row['card_number'])) if pd.notna(row['card_number']) else ''
        set_size_str = str((row['set_size'])) if pd.notna(row['set_size']) else ''
        price_str = f"{row['price']:.1f}" if pd.notna(row['price']) else 'N/A'
        rarity_str = row['rarity'] if pd.notna(row['rarity']) else 'Unknown'

        card_html = f"""
        <div class="card-box">
            <img src="{img_b64}" />
            <div class="card-text">
                <b>{row['pokemon_name']}</b><br>
                <i>{row['set_name']} #{card_number_str}/{set_size_str}</i><br>
                💰 <b>{price_str} €</b><br>
                🌟 <i>{rarity_str}</i>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)