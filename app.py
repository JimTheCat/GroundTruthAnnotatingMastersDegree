import streamlit as st
import pandas as pd
import json
import math
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

# ==========================================
# KONFIGURACJA POD STREAMLIT CLOUD
# ==========================================

os.makedirs("outputs", exist_ok=True)

TEXTS_FILE = "zloty-standard-badanie2.txt"
CATEGORIES_FILE = "categories.json"
LOCAL_OUTPUT = "outputs/anotacje.csv"   # lokalna kopia pliku
REMOTE_FILENAME = "anotacje.csv"        # nazwa pliku na Drive

st.set_page_config(page_title="Anotator korpusu", layout="wide")


# ==========================================
# GOOGLE DRIVE – AUTORYZACJA
# ==========================================

@st.cache_resource
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=creds)


service = get_drive_service()
FOLDER_ID = st.secrets["gdrive"]["folder_id"]


# ==========================================
# GOOGLE DRIVE – LOGIKA PLIKU
# ==========================================

def find_or_create_remote_file():
    """Znajduje plik anotacji w folderze lub tworzy nowy pusty."""
    query = f"'{FOLDER_ID}' in parents and name = '{REMOTE_FILENAME}' and trashed = false"
    results = service.files().list(q=query, spaces="drive", fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # nie ma pliku → tworzymy pusty
    df = pd.DataFrame(columns=["id", "kategorie"])
    df.to_csv(LOCAL_OUTPUT, sep=";", index=False)

    media = MediaFileUpload(LOCAL_OUTPUT, mimetype="text/csv", resumable=False)
    file_metadata = {"name": REMOTE_FILENAME, "parents": [FOLDER_ID]}

    created = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    return created["id"]


REMOTE_FILE_ID = find_or_create_remote_file()


def download_from_drive():
    """Pobiera plik z Drive i zapisuje lokalnie."""
    request = service.files().get_media(fileId=REMOTE_FILE_ID)
    fh = io.BytesIO()

    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    with open(LOCAL_OUTPUT, "wb") as f:
        f.write(fh.read())


def upload_to_drive():
    """Nadpisuje istniejący plik na Drive."""
    media = MediaFileUpload(LOCAL_OUTPUT, mimetype="text/csv", resumable=False)
    service.files().update(
        fileId=REMOTE_FILE_ID,
        media_body=media
    ).execute()


# ==========================================
# WCZYTYWANIE LOKALNYCH PLIKÓW Z DANYMI
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


# ==========================================
# WCZYTYWANIE ANOTACJI Z DRIVE
# ==========================================

def load_annotations():
    # pobranie aktualnej wersji z Google Drive
    download_from_drive()

    if os.path.exists(LOCAL_OUTPUT):
        return pd.read_csv(LOCAL_OUTPUT, sep=";")
    return pd.DataFrame(columns=["id", "kategorie"])


texts = load_texts()
categories = sorted(load_categories())
annotations = load_annotations()


# ==========================================
# FUNKCJE APLIKACJI
# ==========================================

def save_annotation(idx, selected_categories):
    global annotations

    record = {"id": idx, "kategorie": ",".join(selected_categories)}

    annotations = annotations[annotations["id"] != idx]
    annotations = pd.concat([annotations, pd.DataFrame([record])], ignore_index=True)

    # zapis lokalny
    annotations.to_csv(LOCAL_OUTPUT, sep=";", index=False)

    # wysyłka na Drive
    upload_to_drive()


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
# UI – INTERFEJS
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
