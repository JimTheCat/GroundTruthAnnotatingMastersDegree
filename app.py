import streamlit as st
import pandas as pd
import json
import os
import io
from typing import Optional, Dict, List

# Google API (optional - only if secrets are configured)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

    GOOGLE_LIBS_AVAILABLE = True
except Exception:
    GOOGLE_LIBS_AVAILABLE = False

# ----------------------------
# CONFIGURATION
# ----------------------------
os.makedirs("outputs", exist_ok=True)

TEXTS_FILE = "zloty-standard-badanie2.txt"
CATEGORIES_FILE = "categories.json"
LOCAL_OUTPUT = "outputs/anotacje.csv"
REMOTE_FILENAME = "anotacje.csv"

st.set_page_config(page_title="Anotator korpusu", layout="wide")


# ----------------------------
# CACHED DATA LOADERS (run once)
# ----------------------------
@st.cache_data
def load_texts() -> pd.DataFrame:
    """Load texts from file - cached, runs once per session."""
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
def load_categories() -> List[str]:
    """Load categories from JSON - cached, runs once per session."""
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return sorted(json.load(f))


# ----------------------------
# GOOGLE DRIVE SETUP
# ----------------------------
def init_google_drive():
    """Initialize Google Drive connection if secrets are configured."""
    if not GOOGLE_LIBS_AVAILABLE:
        return None, None, None

    try:
        sa_info = st.secrets.get("gcp_service_account")
        drive_cfg = st.secrets.get("gdrive", {})
        folder_id = drive_cfg.get("folder_id")

        if not sa_info or not folder_id:
            return None, None, None

        creds = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds)

        # Find existing file in folder
        query = f"'{folder_id}' in parents and name = '{REMOTE_FILENAME}' and trashed = false"
        res = service.files().list(q=query, spaces="drive", fields="files(id,name)").execute()
        files = res.get("files", [])
        file_id = files[0]["id"] if files else None

        return service, folder_id, file_id

    except Exception as e:
        st.warning(f"Google Drive initialization failed: {e}")
        return None, None, None


def download_from_drive(service, file_id: str, local_path: str) -> bool:
    """Download file from Google Drive to local path."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        with open(local_path, "wb") as f:
            f.write(fh.read())
        return True
    except Exception as e:
        st.error(f"Download failed: {e}")
        return False


def upload_to_drive(service, file_id: str, local_path: str) -> bool:
    """Upload local file to Google Drive."""
    try:
        media = MediaFileUpload(local_path, mimetype="text/csv", resumable=False)
        service.files().update(fileId=file_id, media_body=media).execute()
        return True
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return False


# ----------------------------
# ANNOTATIONS MANAGEMENT
# ----------------------------
def load_annotations_from_csv(filepath: str) -> Dict[str, List[str]]:
    """Load annotations from CSV into a dictionary: {id: [category1, category2, ...]}"""
    if not os.path.exists(filepath):
        return {}

    try:
        df = pd.read_csv(filepath, sep=";")
        annotations = {}
        for _, row in df.iterrows():
            text_id = str(row["id"])
            cats = row.get("kategorie", "")
            if pd.isna(cats) or cats == "":
                annotations[text_id] = []
            else:
                annotations[text_id] = str(cats).split(",")
        return annotations
    except Exception as e:
        st.error(f"Error loading annotations: {e}")
        return {}


def save_annotations_to_csv(annotations: Dict[str, List[str]], filepath: str) -> bool:
    """Save annotations dictionary to CSV file."""
    try:
        rows = [
            {"id": text_id, "kategorie": ",".join(cats)}
            for text_id, cats in annotations.items()
        ]
        df = pd.DataFrame(rows)
        df.to_csv(filepath, sep=";", index=False)
        return True
    except Exception as e:
        st.error(f"Error saving annotations: {e}")
        return False


def find_first_unannotated(texts_df: pd.DataFrame, annotations: Dict[str, List[str]]) -> int:
    """Find index of first unannotated text."""
    for i, row in texts_df.iterrows():
        text_id = str(row["id"])
        if text_id not in annotations or len(annotations[text_id]) == 0:
            return i
    return 0


# ----------------------------
# INITIALIZE SESSION STATE
# ----------------------------
def init_session_state():
    """Initialize all session state variables on first run."""

    # Load static data (cached)
    texts = load_texts()
    categories = load_categories()

    # Initialize Drive connection (once per session)
    if "drive_initialized" not in st.session_state:
        drive_service, folder_id, file_id = init_google_drive()
        st.session_state.drive_service = drive_service
        st.session_state.drive_folder_id = folder_id
        st.session_state.drive_file_id = file_id
        st.session_state.drive_initialized = True

        # Try to download from Drive ONLY if local file doesn't exist
        # This prevents overwriting local changes on every reload
        if drive_service and file_id:
            st.session_state.drive_download_attempted = True
            if not os.path.exists(LOCAL_OUTPUT):
                # Local file missing - download from Drive
                download_success = download_from_drive(drive_service, file_id, LOCAL_OUTPUT)
                st.session_state.drive_download_success = download_success
                st.session_state.drive_download_reason = "local_file_missing"
                if download_success:
                    st.session_state.drive_last_download = pd.Timestamp.now()
            else:
                # Local file exists - don't overwrite it
                st.session_state.drive_download_success = False
                st.session_state.drive_download_reason = "local_file_exists_skipped"
        else:
            st.session_state.drive_download_attempted = False
            st.session_state.drive_download_success = False
            st.session_state.drive_download_reason = "drive_not_available"

    # Load annotations into memory (dictionary for fast access)
    if "annotations" not in st.session_state:
        st.session_state.annotations = load_annotations_from_csv(LOCAL_OUTPUT)
        st.session_state.annotations_loaded_from = "local_file"
        st.session_state.initial_annotation_count = len(st.session_state.annotations)

    # Current text index
    if "current_index" not in st.session_state:
        st.session_state.current_index = find_first_unannotated(texts, st.session_state.annotations)

    # Track unsaved changes
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = False

    return texts, categories


# ----------------------------
# UI STYLING
# ----------------------------
def apply_custom_styles():
    """Apply custom CSS styles based on sidebar settings."""
    with st.sidebar:
        st.header("⚙️ Ustawienia wyglądu")
        font_size = st.select_slider(
            "Rozmiar czcionki",
            options=["12px", "14px", "16px", "18px", "20px", "22px", "24px"],
            value="16px"
        )
        font_family = st.selectbox(
            "Krój czcionki",
            ["Arial", "Georgia", "Times New Roman", "Verdana", "Tahoma",
             "Trebuchet MS", "Courier New", "Roboto", "Open Sans", "Lato"],
            index=0
        )

    custom_style = f"""
    <style>
        * {{
            font-family: "{font_family}", sans-serif !important;
        }}
        html, body, [class*="css"], p, div, span, label, input, textarea, select {{
            font-size: {font_size} !important;
            font-family: "{font_family}", sans-serif !important;
        }}
        .stMarkdown, .stText, .stAlert, .stInfo, .stWarning, .stError, .stSuccess {{
            font-size: {font_size} !important;
            font-family: "{font_family}", sans-serif !important;
        }}
        .stButton > button {{
            margin-top: 6px;
            font-family: "{font_family}", sans-serif !important;
        }}
    </style>
    """
    st.markdown(custom_style, unsafe_allow_html=True)


# ----------------------------
# HELPER: Capture current selection to memory
# ----------------------------
def capture_current_selection(text_id: str):
    """Save the current multiselect value to annotations dict in memory."""
    selected_key = f"cat_{text_id}"
    if selected_key in st.session_state:
        current_selection = st.session_state[selected_key]
        # Only update if changed
        if st.session_state.annotations.get(text_id, []) != current_selection:
            st.session_state.annotations[text_id] = current_selection
            st.session_state.unsaved_changes = True


# ----------------------------
# NAVIGATION FUNCTIONS
# ----------------------------
def navigate_previous(current_text_id: str):
    """Navigate to previous text."""
    # Save current selection before moving
    capture_current_selection(current_text_id)

    if st.session_state.current_index > 0:
        st.session_state.current_index -= 1


def navigate_next(texts_df: pd.DataFrame, current_text_id: str):
    """Navigate to next text and save current annotation to memory."""
    # Save current selection before moving
    capture_current_selection(current_text_id)

    # Move to next
    if st.session_state.current_index < len(texts_df) - 1:
        st.session_state.current_index += 1


def save_to_local_file(current_text_id: str):
    """Save all annotations from memory to local CSV file."""
    # CRITICAL: Capture current selection before saving!
    capture_current_selection(current_text_id)

    success = save_annotations_to_csv(st.session_state.annotations, LOCAL_OUTPUT)
    if success:
        st.session_state.unsaved_changes = False
        # Verify the file was written
        if os.path.exists(LOCAL_OUTPUT):
            file_size = os.path.getsize(LOCAL_OUTPUT)
            st.success(f"✅ Zapisano lokalnie ({file_size} bytes, {len(st.session_state.annotations)} tekstów)")
        else:
            st.error("⚠️ Plik nie został utworzony!")
    else:
        st.error("❌ Błąd zapisu!")
    return success


def save_to_drive(current_text_id: str):
    """Upload local CSV file to Google Drive."""
    # First ensure current selection is captured and saved locally
    save_to_local_file(current_text_id)

    service = st.session_state.drive_service
    file_id = st.session_state.drive_file_id

    if not service:
        st.error("❌ Integracja z Google Drive niedostępna")
        return False

    if not file_id:
        st.error("❌ Plik nie istnieje na Google Drive. Utwórz go ręcznie i upewnij się, że konto serwisowe ma dostęp.")
        return False

    success = upload_to_drive(service, file_id, LOCAL_OUTPUT)
    if success:
        st.success("✅ Zapisano na Google Drive")
    return success


# ----------------------------
# MAIN APP
# ----------------------------
def main():
    # Initialize everything
    texts, categories = init_session_state()
    apply_custom_styles()

    # Title
    st.title("📑 Anotator tekstów")

    # Get current text
    current_index = st.session_state.current_index
    row = texts.iloc[current_index]
    text_id = str(row["id"])

    # Display text info
    st.markdown(f"### 🔢 ID: `{text_id}`")
    st.markdown(f"###### 📊 Tekst: `{current_index + 1}` z `{len(texts)}`")

    st.markdown("### 📄 Tekst:")
    st.info(row["tekst"])

    # Category selection
    default_categories = st.session_state.annotations.get(text_id, [])
    selected_key = f"cat_{text_id}"

    selected = st.multiselect(
        "Wybierz kategorie:",
        options=categories,
        default=default_categories,
        key=selected_key
    )

    # Mark as changed if selection differs from saved
    if selected != default_categories:
        st.session_state.unsaved_changes = True

    # Navigation and save buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        st.button(
            "💾 Zapisz lokalnie",
            on_click=save_to_local_file,
            args=(text_id,),
            use_container_width=True
        )

    with col2:
        st.button(
            "⬅ Poprzedni",
            on_click=navigate_previous,
            args=(text_id,),
            use_container_width=True
        )

    with col3:
        st.button(
            "Następny ➡",
            on_click=navigate_next,
            args=(texts, text_id),
            use_container_width=True
        )

    with col4:
        # Empty column (removed "Pomiń" button)
        pass

    # Warning for unsaved changes
    if st.session_state.unsaved_changes:
        st.warning("⚠️ Masz niezapisane zmiany w pamięci. Kliknij 'Zapisz lokalnie' aby zapisać na dysk.")

    # Global Drive save
    st.markdown("---")
    st.markdown("### ☁️ Synchronizacja z Google Drive")

    col_drive1, col_drive2 = st.columns([3, 1])
    with col_drive1:
        st.write("Po zakończeniu pracy wyślij plik na Google Drive:")
    with col_drive2:
        st.button(
            "🔼 Zapisz na Drive",
            on_click=save_to_drive,
            args=(text_id,),
            use_container_width=True
        )

    # Progress
    st.markdown("---")
    st.subheader("📊 Postęp anotacji")

    done = len([a for a in st.session_state.annotations.values() if len(a) > 0])
    total = len(texts)
    progress_value = done / total if total > 0 else 0
    percent = round(progress_value * 100, 2)

    col_p1, col_p2 = st.columns([4, 1])
    with col_p1:
        st.progress(progress_value)
    with col_p2:
        st.markdown(f"**{percent}%**")

    st.write(f"✅ {done}/{total} tekstów oznaczonych")

    # Drive status
    if st.session_state.drive_service:
        st.info(
            f"🟢 Google Drive: połączono | Folder: `{st.session_state.drive_folder_id}` | Plik: `{st.session_state.drive_file_id or 'nie znaleziono'}`")
        reason = st.session_state.get("drive_download_reason", "unknown")
        if reason == "local_file_missing":
            st.success("✅ Pobrano z Drive przy starcie (plik lokalny nie istniał)")
        elif reason == "local_file_exists_skipped":
            st.info("ℹ️ Używam lokalnego pliku (nie pobierano z Drive aby nie nadpisać zmian)")
        elif st.session_state.get("drive_download_success"):
            st.success(f"✅ Pobrano z Drive przy starcie")
        elif st.session_state.get("drive_download_attempted"):
            st.warning("⚠️ Próba pobrania z Drive nie powiodła się przy starcie")
    else:
        st.info("🔵 Google Drive: niedostępne (praca lokalna)")

    # Debug panel
    with st.expander("🔧 Informacje techniczne"):
        st.write("### 📁 Stan plików")
        st.write(f"**Plik lokalny:** `{LOCAL_OUTPUT}`")
        st.write(f"**Istnieje:** {os.path.exists(LOCAL_OUTPUT)}")
        if os.path.exists(LOCAL_OUTPUT):
            st.write(f"**Rozmiar pliku:** {os.path.getsize(LOCAL_OUTPUT)} bytes")
            st.write(f"**Ostatnia modyfikacja:** {pd.Timestamp.fromtimestamp(os.path.getmtime(LOCAL_OUTPUT))}")

        st.write("### 💾 Stan pamięci")
        st.write(f"**Tekstów w pamięci:** {len(st.session_state.annotations)}")
        st.write(f"**Załadowano z:** {st.session_state.get('annotations_loaded_from', 'unknown')}")
        st.write(f"**Początkowa liczba:** {st.session_state.get('initial_annotation_count', 'unknown')}")
        st.write(f"**Niezapisane zmiany:** {st.session_state.unsaved_changes}")
        st.write(f"**Bieżąca selekcja (w multiselect):** {st.session_state.get(selected_key, [])}")
        st.write(f"**Zapisana selekcja (w annotations):** {st.session_state.annotations.get(text_id, [])}")

        st.write("### ☁️ Stan Drive")
        st.write(f"**Drive dostępne:** {st.session_state.drive_service is not None}")
        st.write(f"**Próba pobrania:** {st.session_state.get('drive_download_attempted', False)}")
        st.write(f"**Pobrano pomyślnie:** {st.session_state.get('drive_download_success', False)}")
        st.write(f"**Powód decyzji:** {st.session_state.get('drive_download_reason', 'unknown')}")
        if st.session_state.get('drive_last_download'):
            st.write(f"**Czas ostatniego pobrania:** {st.session_state.drive_last_download}")

        # Show what's actually in the CSV file
        if os.path.exists(LOCAL_OUTPUT):
            st.write("### 📄 Zawartość pliku CSV (ostatnie 10 wpisów):")
            try:
                df_check = pd.read_csv(LOCAL_OUTPUT, sep=";")
                st.dataframe(df_check.tail(10))
                st.write(f"**Razem wpisów w pliku:** {len(df_check)}")
            except Exception as e:
                st.error(f"Nie można odczytać CSV: {e}")

        if os.path.exists(LOCAL_OUTPUT):
            with open(LOCAL_OUTPUT, "rb") as f:
                st.download_button(
                    "📥 Pobierz CSV",
                    data=f,
                    file_name="anotacje.csv",
                    mime="text/csv"
                )

        if st.button("🔄 Pobierz ponownie z Drive"):
            if st.session_state.drive_service and st.session_state.drive_file_id:
                success = download_from_drive(
                    st.session_state.drive_service,
                    st.session_state.drive_file_id,
                    LOCAL_OUTPUT
                )
                if success:
                    # Reload annotations from downloaded file
                    st.session_state.annotations = load_annotations_from_csv(LOCAL_OUTPUT)
                    st.success("✅ Pobrano z Drive i odświeżono dane")
                    st.rerun()
            else:
                st.error("❌ Drive niedostępne")


if __name__ == "__main__":
    main()