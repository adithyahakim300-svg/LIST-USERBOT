import os
import json
import re

from google.cloud import vision
from google.oauth2.service_account import Credentials

_client = None

# Ambil kata setelah "t.me/" sebagai username
USERNAME_PATTERN = re.compile(r"t\.me/([A-Za-z0-9_]+)", re.IGNORECASE)


def _get_client():
    global _client
    if _client is not None:
        return _client
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict)
    _client = vision.ImageAnnotatorClient(credentials=creds)
    return _client


def extract_usernames_from_image(image_bytes: bytes) -> list[str]:
    """Baca semua teks di gambar, ambil yang berpola 't.me/<username>'.

    Ini fungsi sinkron/blocking (pakai library resmi Google), jadi
    dipanggil lewat asyncio.to_thread() di sisi bot supaya tidak
    ngeblok event loop Telegram.
    """
    client = _get_client()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Google Vision error: {response.error.message}")

    full_text = response.text_annotations[0].description if response.text_annotations else ""
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
