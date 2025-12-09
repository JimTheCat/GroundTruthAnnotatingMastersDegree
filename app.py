"""
Text Annotation App - Main Application File

A Streamlit app for annotating text corpus with categories.
Supports local storage and Google Drive synchronization.

Run with: streamlit run app.py
"""

import streamlit as st
import os
from typing import Dict, List
from dataclasses import dataclass
from functools import wraps

# Import our modules
from config import (
    LOCAL_CSV, PAGE_TITLE, PAGE_LAYOUT,
    FONT_SIZES, DEFAULT_FONT_SIZE,
    FONT_FAMILIES, DEFAULT_FONT_FAMILY
)
from data_manager import (
    load_texts, load_categories, AnnotationsManager
)
from drive_service import DriveService

# Configure Streamlit
st.set_page_config(page_title=PAGE_TITLE, layout=PAGE_LAYOUT)


# ============================================================================
# APP STATE MANAGEMENT
# ============================================================================

@dataclass
class AppState:
    """
    Centralized application state.
    Provides clean interface to session state data.
    """

    @classmethod
    def get(cls):
        """Get current app state from session state"""
        return cls()

    @property
    def annotations(self) -> Dict[str, List[str]]:
        return st.session_state.annotations

    @property
    def current_index(self) -> int:
        return st.session_state.current_index

    @current_index.setter
    def current_index(self, value: int):
        st.session_state.current_index = value

    @property
    def texts(self):
        return st.session_state.texts

    @property
    def categories(self) -> List[str]:
        return st.session_state.categories

    @property
    def drive(self) -> DriveService:
        return st.session_state.drive

    @property
    def current_text_id(self) -> str:
        """Get ID of currently displayed text"""
        return str(self.texts.iloc[self.current_index]["id"])

    @property
    def current_text(self) -> str:
        """Get content of currently displayed text"""
        return self.texts.iloc[self.current_index]["tekst"]

    @property
    def annotation_count(self) -> int:
        """Count how many texts have been annotated"""
        return AnnotationsManager.count_annotated(self.annotations)

    @property
    def progress_percent(self) -> float:
        """Calculate annotation progress percentage"""
        total = len(self.texts)
        return (self.annotation_count / total * 100) if total > 0 else 0

    @property
    def total_texts(self) -> int:
        """Total number of texts in corpus"""
        return len(self.texts)


# ============================================================================
# DECORATOR: Auto-save Current Selection
# ============================================================================

def autosave_selection(func):
    """
    Decorator that automatically saves current multiselect value
    to annotations before executing the decorated function.

    This prevents losing changes when navigating between texts.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        state = AppState.get()
        multiselect_key = f"cat_{state.current_text_id}"

        # Check if user has made changes in the multiselect
        if multiselect_key in st.session_state:
            new_selection = st.session_state[multiselect_key]
            current_saved = state.annotations.get(state.current_text_id, [])

            # Update annotations if changed
            if current_saved != new_selection:
                state.annotations[state.current_text_id] = new_selection

        return func(*args, **kwargs)

    return wrapper


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

@autosave_selection
def navigate_to(index: int):
    """
    Navigate to specific text by index.

    Args:
        index: Text index to navigate to (0-based)
    """
    state = AppState.get()
    state.current_index = max(0, min(index, state.total_texts - 1))


@autosave_selection
def save_local() -> bool:
    """
    Save all annotations to local CSV file.

    Returns:
        True if save succeeded, False otherwise
    """
    state = AppState.get()
    success = AnnotationsManager.save_to_csv(state.annotations, LOCAL_CSV)

    if success:
        file_size = os.path.getsize(LOCAL_CSV) if os.path.exists(LOCAL_CSV) else 0
        st.success(
            f"✅ Zapisano lokalnie "
            f"({state.annotation_count} tekstów, {file_size} bytes)"
        )
    else:
        st.error("❌ Błąd zapisu lokalnego")

    return success


@autosave_selection
def save_drive() -> bool:
    """
    Save annotations to Google Drive.
    First saves locally, then uploads to Drive.

    Returns:
        True if save succeeded, False otherwise
    """
    state = AppState.get()

    # First ensure local file is up to date
    if not save_local():
        return False

    # Check if Drive is available
    if not state.drive.is_available:
        st.error("❌ Google Drive niedostępne")
        return False

    # Upload to Drive
    if state.drive.upload(LOCAL_CSV):
        st.success("✅ Zapisano na Google Drive")
        return True

    return False


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render sidebar with appearance settings"""
    with st.sidebar:
        st.header("⚙️ Ustawienia")

        # Font size selector
        font_size = st.select_slider(
            "Rozmiar czcionki",
            options=FONT_SIZES,
            value=DEFAULT_FONT_SIZE
        )

        # Font family selector
        font_family = st.selectbox(
            "Krój czcionki",
            options=FONT_FAMILIES,
            index=FONT_FAMILIES.index(DEFAULT_FONT_FAMILY)
        )

        # Apply custom CSS - target text content, preserve icons
        st.markdown(f"""
        <style>
            /* Apply font family broadly but exclude icon elements */
            body, p, div, span, label, input, textarea, select, 
            h1, h2, h3, h4, h5, h6,
            .stMarkdown, .stText, .stAlert, .stButton {{
                font-family: "{font_family}", sans-serif;
            }}

            /* Preserve icon fonts - override above rule */
            button span[data-testid*="Icon"],
            [class*="material-icons"],
            svg {{
                font-family: inherit !important;
            }}

            /* Font sizes for text content */
            html, body, p, div, span, label, input, textarea, select {{
                font-size: {font_size};
            }}
            .stMarkdown, .stText, .stAlert {{
                font-size: {font_size};
            }}
        </style>
        """, unsafe_allow_html=True)

def render_text_display():
    """Render current text information"""
    state = AppState.get()

    st.markdown(f"### 🔢 ID: `{state.current_text_id}`")
    st.markdown(
        f"###### 📊 Tekst: `{state.current_index + 1}` / `{state.total_texts}`"
    )
    st.markdown("### 📄 Tekst:")
    st.info(state.current_text)


def render_category_selector():
    """Render category multiselect widget"""
    state = AppState.get()
    text_id = state.current_text_id
    default_cats = state.annotations.get(text_id, [])

    st.multiselect(
        "Wybierz kategorie:",
        options=state.categories,
        default=default_cats,
        key=f"cat_{text_id}"
    )


def render_navigation_buttons():
    """Render navigation and save buttons"""
    state = AppState.get()

    col1, col2, col3, _ = st.columns([1, 1, 1, 1])

    with col1:
        st.button(
            "💾 Zapisz lokalnie",
            on_click=save_local,
            use_container_width=True
        )

    with col2:
        st.button(
            "⬅ Poprzedni",
            on_click=navigate_to,
            args=(state.current_index - 1,),
            disabled=(state.current_index == 0),
            use_container_width=True
        )

    with col3:
        st.button(
            "Następny ➡",
            on_click=navigate_to,
            args=(state.current_index + 1,),
            disabled=(state.current_index >= state.total_texts - 1),
            use_container_width=True
        )


def render_drive_sync():
    """Render Google Drive synchronization section"""
    state = AppState.get()

    st.markdown("---")
    st.markdown("### ☁️ Synchronizacja z Google Drive")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.write(state.drive.status_message)

    with col2:
        st.button(
            "🔼 Zapisz na Drive",
            on_click=save_drive,
            disabled=not state.drive.is_available,
            use_container_width=True
        )


def render_progress():
    """Render progress bar and statistics"""
    state = AppState.get()

    st.markdown("---")
    st.subheader("📊 Postęp anotacji")

    col1, col2 = st.columns([4, 1])

    with col1:
        st.progress(state.progress_percent / 100)

    with col2:
        st.markdown(f"**{state.progress_percent:.1f}%**")

    st.write(
        f"✅ {state.annotation_count} / {state.total_texts} tekstów oznaczonych"
    )


def render_debug_panel():
    """Render debug information panel"""
    state = AppState.get()

    with st.expander("⚙️ Informacje techniczne"):
        st.write("### 📁 Pliki")
        st.write(f"**Plik lokalny:** `{LOCAL_CSV}`")
        st.write(f"**Istnieje:** {os.path.exists(LOCAL_CSV)}")

        if os.path.exists(LOCAL_CSV):
            import pandas as pd
            file_size = os.path.getsize(LOCAL_CSV)
            mod_time = pd.Timestamp.fromtimestamp(os.path.getmtime(LOCAL_CSV))
            st.write(f"**Rozmiar:** {file_size} bytes")
            st.write(f"**Ostatnia modyfikacja:** {mod_time}")

        st.write("### ☁️ Google Drive")
        st.write(f"**Status:** {state.drive.status_message}")
        # Download button
        if os.path.exists(LOCAL_CSV):
            with open(LOCAL_CSV, "rb") as f:
                st.download_button(
                    "📥 Pobierz CSV",
                    data=f,
                    file_name="anotacje.csv",
                    mime="text/csv"
                )

        # Manual Drive download button
        if state.drive.is_available:
            if st.button("🔄 Pobierz ponownie z Drive"):
                if state.drive.download(LOCAL_CSV):
                    # Reload annotations from downloaded file
                    st.session_state.annotations = (
                        AnnotationsManager.load_from_csv(LOCAL_CSV)
                    )
                    st.success("✅ Pobrano z Drive")
                    st.rerun()


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_app():
    """
    Initialize application on first run.
    Loads data, sets up Drive, and restores session.
    """
    if "initialized" in st.session_state:
        return

    # Load static data (cached)
    st.session_state.texts = load_texts()
    st.session_state.categories = load_categories()

    # Initialize Google Drive service
    st.session_state.drive = DriveService()

    # Download from Drive only if local file doesn't exist
    # This prevents overwriting local changes on reload
    if not os.path.exists(LOCAL_CSV) and st.session_state.drive.is_available:
        st.session_state.drive.download(LOCAL_CSV)

    # Load annotations from local file
    st.session_state.annotations = AnnotationsManager.load_from_csv(LOCAL_CSV)

    # Set initial position to first unannotated text
    st.session_state.current_index = AnnotationsManager.find_first_unannotated(
        st.session_state.texts,
        st.session_state.annotations
    )

    # Mark as initialized
    st.session_state.initialized = True


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""

    # Initialize app state
    initialize_app()

    # Render UI components
    render_sidebar()

    st.title("📑 Anotator tekstów")

    render_text_display()
    render_category_selector()
    render_navigation_buttons()
    render_drive_sync()
    render_progress()
    render_debug_panel()


if __name__ == "__main__":
    main()