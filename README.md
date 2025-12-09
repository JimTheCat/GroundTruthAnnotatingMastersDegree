# Text Annotation App - Setup Guide

A Streamlit application for annotating text corpus with categories, supporting local storage and Google Drive synchronization.

## 📁 Project Structure

```
your-project/
├── app.py                          # Main application (run this)
├── config.py                       # Configuration and constants
├── data_manager.py                 # Annotation storage logic
├── drive_service.py                # Google Drive integration
├── zloty-standard-badanie2.txt     # Your texts file
├── categories.json                 # Your categories file
├── outputs/
│   └── anotacje.csv               # Generated annotations (auto-created)
└── .streamlit/
    └── secrets.toml               # Google Drive credentials (optional)
```

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Your Data Files

**zloty-standard-badanie2.txt** - Format:
```
id text
1 First text content here
```

**categories.json** - Format:
```json
[
  "KATEGORIA1",
  "KATEGORIA2"
]
```

### 3. Configure Google Drive (Optional)

Create `.streamlit/secrets.toml`:

```toml
# Google Service Account credentials (full JSON)
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"

# Google Drive folder ID
[gdrive]
folder_id = "your-google-drive-folder-id"
```

**To get your folder ID:**
1. Open the folder in Google Drive
2. Copy the ID from URL: `https://drive.google.com/drive/folders/[FOLDER_ID_HERE]`

**Service Account Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google Drive API
4. Create Service Account credentials
5. Share your Drive folder with the service account email
6. Download JSON key and paste into `secrets.toml`

## 💻 Running the App

### Locally
```bash
streamlit run app.py
```

### On Streamlit Cloud
1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy from your repository
4. Add secrets in the app settings (paste `secrets.toml` content)

## 🎯 Usage

### Workflow

1. **Navigate** - Use "Poprzedni" / "Następny" buttons to move between texts
2. **Annotate** - Select categories from the multiselect dropdown
3. **Save Locally** - Click "💾 Zapisz lokalnie" to save to disk
4. **Sync to Drive** - Click "🔼 Zapisz na Drive" to upload (end of session)

### Key Features

- ✅ **Auto-save** - Current selection is captured before navigation
- ✅ **Progress tracking** - Visual progress bar shows completion
- ✅ **Font customization** - Change size and family in sidebar
- ✅ **Local-first** - Works offline, Drive sync is optional
- ✅ **Smart sync** - Only downloads from Drive if local file missing

### Tips

- Press `R` to reload the app (useful after errors)
- Use "🔧 Informacje techniczne" to debug issues
- Download CSV anytime with "📥 Pobierz CSV"
- Use "🔄 Pobierz ponownie z Drive" to force refresh from cloud

## 🐛 Troubleshooting

### "Drive niedostępne"
- Check if `secrets.toml` exists and is properly formatted
- Verify service account email has access to Drive folder
- Ensure Google Drive API is enabled in GCP

### "Plik nie istnieje na Google Drive"
- Create `anotacje.csv` manually in your Drive folder
- Share folder with service account email
- Check folder ID is correct

### Changes Don't Persist
- Click "💾 Zapisz lokalnie" before closing
- Check debug panel to verify file was written
- On Streamlit Cloud, you MUST use "🔼 Zapisz na Drive" (local storage is ephemeral)

## 📝 License

MIT License - feel free to use and modify!