
import re
from io import BytesIO
 
import pytesseract
from PIL import Image
 
# Ambil kata setelah "t.me/" sebagai username
USERNAME_PATTERN = re.compile(r"t\.me/([A-Za-z0-9_]+)", re.IGNORECASE)
 
 
def extract_usernames_from_image(image_bytes: bytes) -> list[str]:
    """Baca semua teks di gambar pakai Tesseract (OCR lokal, gratis, tanpa API),
    ambil yang berpola 't.me/<username>'.
 
    Ini fungsi sinkron/blocking, jadi dipanggil lewat asyncio.to_thread()
    di sisi bot supaya tidak ngeblok event loop Telegram.
    """
    image = Image.open(BytesIO(image_bytes))
 
    # Convert ke grayscale membantu akurasi Tesseract di kebanyakan screenshot
    image = image.convert("L")
 
    full_text = pytesseract.image_to_string(image)
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
