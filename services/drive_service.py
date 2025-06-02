from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import Config

SCOPES = ['https://www.googleapis.com/auth/drive.file']
creds = None

def get_drive_service():
    global creds
    if not creds:
        flow = InstalledAppFlow.from_client_config({
            "installed": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
            }
        }, SCOPES)
        creds = flow.run_local_server(port=0)
    return build('drive', 'v3', credentials=creds)

def upload_video(file_path, file_name):
    service = get_drive_service()
    file_metadata = {'name': file_name, 'parents': ['root']}
    media = MediaFileUpload(file_path)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')