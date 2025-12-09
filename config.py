"""
Configuration file for the Text Annotation App
Contains all constants and settings
"""

import os

# ============================================================================
# FILE PATHS
# ============================================================================

TEXTS_FILE = "zloty-standard-badanie2.txt"
CATEGORIES_FILE = "categories.json"
OUTPUT_DIR = "outputs"
LOCAL_CSV = os.path.join(OUTPUT_DIR, "anotacje.csv")
REMOTE_CSV = "anotacje.csv"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# STREAMLIT CONFIG
# ============================================================================

PAGE_TITLE = "Anotator korpusu"
PAGE_LAYOUT = "wide"

# ============================================================================
# UI SETTINGS
# ============================================================================

FONT_SIZES = ["12px", "14px", "16px", "18px", "20px", "22px", "24px"]
DEFAULT_FONT_SIZE = "16px"

FONT_FAMILIES = [
    "Arial",
    "Georgia",
    "Verdana",
    "Tahoma",
    "Trebuchet MS",
]
DEFAULT_FONT_FAMILY = "Arial"

# ============================================================================
# GOOGLE DRIVE CONFIG
# ============================================================================

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Secret keys expected in st.secrets
SECRET_SERVICE_ACCOUNT = "gcp_service_account"
SECRET_FOLDER_ID = "gdrive"