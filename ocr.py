import os
import json
import re
import time
from io import BytesIO

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/drive"]

_drive_service = None

# Ambil kata setelah "t.me/" sebagai username
USERNAME_PATTERN = re.compile(r"t\.me/([A-Za-z0-9_]+)", re.IGNORECASE)


def _get_drive_service():
    global _drive_service
    if _drive_service is not None:
        return _drive_service
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def _ocr_via_drive(image_bytes: bytes) -> str:
    """Upload gambar ke Drive sebagai Google Docs (auto-OCR), ambil teksnya, lalu hapus filenya.

    Butuh GOOGLE_DRIVE_FOLDER_ID: folder di Drive akun Gmail biasa yang
    sudah di-share ke service account (role Editor). Ini supaya file
    numpang kuota penyimpanan akun Gmail tsb, karena service account
    sendiri tidak punya kuota Drive.
    """
    service = _get_drive_service()
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

    file_metadata = {
        "name": f"ocr-temp-{int(time.time() * 1000)}",
        "parents": [folder_id],
        "mimeType": "application/vnd.google-apps.document",
    }
    media = MediaIoBaseUpload(BytesIO(image_bytes), mimetype="image/png", resumable=False)

    file_id = None
    try:
        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()
        file_id = uploaded["id"]

        exported = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        if isinstance(exported, bytes):
            text = exported.decode("utf-8")
        else:
            text = exported
        return text
    except HttpError as e:
        raise RuntimeError(f"Drive OCR error: {e}")
    finally:
        if file_id:
            try:
                service.files().delete(fileId=file_id).execute()
            except HttpError:
                pass  # gagal hapus file temp bukan hal fatal, cuma numpuk sampah di folder


def extract_usernames_from_image(image_bytes: bytes) -> list[str]:
    """Baca semua teks di gambar (via Drive OCR), ambil yang berpola 't.me/<username>'.

    Ini fungsi sinkron/blocking, jadi dipanggil lewat asyncio.to_thread()
    di sisi bot supaya tidak ngeblok event loop Telegram.
    """
    full_text = _ocr_via_drive(image_bytes)
    found = USERNAME_PATTERN.findall(full_text)

    # Hilangkan duplikat, urutan tetap dipertahankan
    seen = set()
    usernames = []
    for u in found:
        key = u.lower()
        if key not in seen:
            seen.add(key)
            usernames.append(u)
    return usernames
