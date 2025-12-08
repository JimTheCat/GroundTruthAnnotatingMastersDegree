import streamlit as st
import pandas as pd
import math
import json
import os

# ==========================================
# KONFIGURACJA POD STREAMLIT CLOUD
# ==========================================

os.makedirs("outputs", exist_ok=True)

TEXTS_FILE = "zloty-standard-badanie2.txt"
CATEGORIES_FILE = "categories.json"
OUTPUT_FILE = "outputs/anotacje.csv"

st.set_page_config(page_title="Anotator korpusu", layout="wide")


# ==========================================
# SIDEBAR – USTAWIENIA WYGLĄDU
# ==========================================

with st.sidebar:
    st.header("⚙️ Ustawienia wyglądu")

    font_size = st.select_slider(
        "Rozmiar czcionki",
        options=["12px", "14px", "16px", "18px", "20px", "22px", "24px"],
        value="16px"
    )

    font_family = st.selectbox(
        "Krój czcionki",
        [
            "Arial", "Georgia", "Times New Roman", "Verdana", "Tahoma",
            "Trebuchet MS", "Courier New", "Roboto", "Open Sans", "Lato"
        ],
        index=0
    )

custom_style = f"""
<style>
    html, body, [class*="css"] {{
        font-size: {font_size} !important;
        font-family: '{font_family}', sans-serif !important;
    }}
    .stAlert {{
        font-size: {font_size} !important;
        font-family: '{font_family}', sans-serif !important;
    }}
</style>
"""
st.markdown(custom_style, unsafe_allow_html=True)


# ==========================================
# WCZYTYWANIE DANYCH
# ==========================================

@st.cache_data
def load_texts():
    rows = []
    with open(TEXTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            idx = parts[0]
            tekst = parts[1] if len(parts) == 2 else ""
            rows.append({"id": idx, "tekst": tekst})

    return pd.DataFrame(rows)


@st.cache_data
def load_categories():
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_annotations():
    if os.path.exists(OUTPUT_FILE):
        return pd.read_csv(OUTPUT_FILE, sep=";")
    return pd.DataFrame(columns=["id", "kategorie"])


texts = load_texts()
categories = sorted(load_categories())
annotations = load_annotations()


# ==========================================
# FUNKCJE POMOCNICZE
# ==========================================

def save_annotation(idx, selected_categories):
    global annotations

    record = {"id": idx, "kategorie": ",".join(selected_categories)}
    annotations = annotations[annotations["id"] != idx]
    annotations = pd.concat([annotations, pd.DataFrame([record])], ignore_index=True)
    annotations.to_csv(OUTPUT_FILE, sep=";", index=False)


def get_categories_for_id(idx):
    rows = annotations[annotations["id"] == idx]
    if len(rows) == 0:
        return []

    val = rows.iloc[0]["kategorie"]
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == "":
        return []

    return str(val).split(",")


def find_first_unannotated():
    annotated_ids = set(annotations["id"].astype(str))
    for i, row in texts.iterrows():
        if str(row["id"]) not in annotated_ids:
            return i
    return 0


# ==========================================
# STAN SESJI
# ==========================================

if "current_index" not in st.session_state:
    st.session_state.current_index = find_first_unannotated()


# ==========================================
# UI – GŁÓWNY EKRAN
# ==========================================

st.title("📑 Anotator tekstów")

current_index = st.session_state.current_index
row = texts.iloc[current_index]

st.markdown(f"### 🔢 ID: `{row.id}`")
st.markdown(f"###### 🔢 Numer porządkowy: `{current_index+1}` z `{len(texts)}`")

st.markdown("### 📄 Tekst:")
st.info(row.tekst)

selected = st.multiselect(
    "Wybierz kategorie:",
    options=categories,
    default=get_categories_for_id(row.id),
    key=f"cat_{row.id}"
)


# ==========================================
# NAWIGACJA
# ==========================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("💾 Zapisz"):
        save_annotation(row.id, selected)
        st.success("Zapisano.")

with col2:
    if st.button("⬅ Poprzedni"):
        if st.session_state.current_index > 0:
            st.session_state.current_index -= 1
            st.rerun()

with col3:
    if st.button("Następny ➡"):
        save_annotation(row.id, selected)
        if st.session_state.current_index < len(texts) - 1:
            st.session_state.current_index += 1
        st.rerun()

with col4:
    if st.button("⏭ Pomiń"):
        if st.session_state.current_index < len(texts) - 1:
            st.session_state.current_index += 1
        st.rerun()


# ==========================================
# POSTĘP
# ==========================================

st.markdown("---")
st.subheader("📊 Postęp anotacji:")

done = len(annotations)
total = len(texts)
progress_value = done / total if total > 0 else 0
percent = round(progress_value * 100, 2)

col_p1, col_p2 = st.columns([4, 1])

with col_p1:
    st.progress(progress_value)

with col_p2:
    st.markdown(f"**{percent}%**")

st.write(f"{done}/{total} tekstów oznaczonych.")
