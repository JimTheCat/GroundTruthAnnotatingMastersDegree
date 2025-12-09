"""
Google Drive Service
Handles all Google Drive operations for file sync
"""

import streamlit as st
from typing import Optional
from config import DRIVE_SCOPES, REMOTE_CSV, SECRET_SERVICE_ACCOUNT, SECRET_FOLDER_ID

# Google API (optional - only if libraries are installed)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    import io

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


# ============================================================================
# GOOGLE DRIVE SERVICE
# ============================================================================

class DriveService:
    """
    Manages Google Drive operations for annotation file sync.

    Initializes from Streamlit secrets and provides simple upload/download.
    """

    def __init__(self):
        """Initialize Drive service from Streamlit secrets"""
        self.service = None
        self.folder_id = None
        self.file_id = None
        self._init_error = None

        self._initialize()

    def _initialize(self):
        """
        Initialize Google Drive connection.

        Reads credentials from st.secrets:
        - gcp_service_account: Service account JSON
        - gdrive.folder_id: Folder ID where files are stored
        """
        if not GOOGLE_AVAILABLE:
            self._init_error = "Google libraries not installed"
            return

        try:
            # Get credentials from secrets
            sa_info = st.secrets.get(SECRET_SERVICE_ACCOUNT)
            drive_config = st.secrets.get(SECRET_FOLDER_ID, {})
            folder_id = drive_config.get("folder_id")

            if not sa_info or not folder_id:
                self._init_error = "Missing secrets configuration"
                return

            # Create credentials and build service
            creds = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=DRIVE_SCOPES
            )
            self.service = build("drive", "v3", credentials=creds)
            self.folder_id = folder_id

            # Find the remote file
            self.file_id = self._find_file()

            if not self.file_id:
                self._init_error = f"File '{REMOTE_CSV}' not found in Drive folder"

        except Exception as e:
            self._init_error = str(e)
            st.warning(f"Google Drive initialization failed: {e}")

    def _find_file(self) -> Optional[str]:
        """
        Find the annotation file in the configured Drive folder.

        Returns:
            File ID if found, None otherwise
        """
        if not self.service or not self.folder_id:
            return None

        try:
            # Query for file by name in specific folder
            query = (
                f"'{self.folder_id}' in parents "
                f"and name = '{REMOTE_CSV}' "
                f"and trashed = false"
            )

            result = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)"
            ).execute()

            files = result.get("files", [])
            return files[0]["id"] if files else None

        except Exception as e:
            st.error(f"Error finding file in Drive: {e}")
            return None

    def download(self, local_path: str) -> bool:
        """
        Download annotation file from Google Drive.

        Args:
            local_path: Where to save the downloaded file

        Returns:
            True if download succeeded, False otherwise
        """
        if not self.is_available:
            return False

        try:
            # Get file content
            request = self.service.files().get_media(fileId=self.file_id)

            # Download to memory
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            # Write to disk
            with open(local_path, "wb") as f:
                f.write(fh.getvalue())

            return True

        except Exception as e:
            st.error(f"Download from Drive failed: {e}")
            return False

    def upload(self, local_path: str) -> bool:
        """
        Upload annotation file to Google Drive.

        Args:
            local_path: Path to file to upload

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.is_available:
            return False

        try:
            # Create media upload
            media = MediaFileUpload(
                local_path,
                mimetype="text/csv",
                resumable=False
            )

            # Update existing file
            self.service.files().update(
                fileId=self.file_id,
                media_body=media
            ).execute()

            return True

        except Exception as e:
            st.error(f"Upload to Drive failed: {e}")
            return False

    @property
    def is_available(self) -> bool:
        """
        Check if Drive service is fully initialized and ready.

        Returns:
            True if service can be used, False otherwise
        """
        return (
                self.service is not None
                and self.file_id is not None
        )

    @property
    def status_message(self) -> str:
        """
        Get human-readable status message.

        Returns:
            Status description string
        """
        if self.is_available:
            return f"🟢 Połączono"
        elif self._init_error:
            return f"🔴 Niedostępne: {self._init_error}"
        else:
            return "🔵 Niedostępne (brak konfiguracji)"