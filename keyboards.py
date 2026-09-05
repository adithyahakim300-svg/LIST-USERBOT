import csv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Kode singkat dipakai di callback_data supaya tidak kepanjangan (limit 64 byte)
CATEGORY_CODES = {
    "Kpop Boygroup": "BG",
    "Kpop Girlgroup": "GG",
    "Aktor": "AK",
    "Aktris": "AS",
    "Multi Character": "MC",
    "Trainee": "TR",
    "2D/Anime": "AN",
}
CODE_TO_CATEGORY = {v: k for k, v in CATEGORY_CODES.items()}
CATEGORIES = list(CATEGORY_CODES.keys())
KPOP_CATEGORIES = {"Kpop Boygroup", "Kpop Girlgroup"}
TEXT_INPUT_CATEGORIES = {"Aktor", "Aktris", "Multi Character", "Trainee", "2D/Anime"}

# Gallery tujuan rekap. Kode singkat juga dipakai di callback_data.
GALLERY_CODES = {
    "valoroum": "VL",
    "iddistrict": "ID",
    "bomnax": "BX",
}
CODE_TO_GALLERY = {v: k for k, v in GALLERY_CODES.items()}
GALLERY_LIST = list(GALLERY_CODES.keys())

BACK_LABEL = "⬅️ Kembali"


def load_groups(path="groups.csv"):
    """Baca groups.csv jadi dict: {kategori: {grup: [member, ...]}}"""
    groups: dict[str, dict[str, list[str]]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kategori = row["kategori"].strip()
            grup = row["grup"].strip()
            member = row["member"].strip()
            groups.setdefault(kategori, {}).setdefault(grup, []).append(member)
    return groups


def _chunk(buttons, per_row=2):
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def _with_back(rows, back_data):
    """Tambahkan 1 baris tombol 'Kembali' di bagian bawah keyboard."""
    rows = list(rows)
    rows.append([InlineKeyboardButton(BACK_LABEL, callback_data=back_data)])
    return rows


def back_only_keyboard(back_data):
    """Keyboard cuma berisi 1 tombol back. Dipakai di layar hasil akhir."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(BACK_LABEL, callback_data=back_data)]])


# ---------- Alur input (index = posisi username, angka) ----------


def category_keyboard(index):
    """Tombol pilih kategori. Step pertama alur input, jadi tanpa tombol back."""
    buttons = [
        InlineKeyboardButton(cat, callback_data=f"cat|{index}|{code}")
        for cat, code in CATEGORY_CODES.items()
    ]
    return InlineKeyboardMarkup(_chunk(buttons))


def group_keyboard(index, kategori, groups):
    code = CATEGORY_CODES[kategori]
    grup_list = list(groups.get(kategori, {}).keys())
    buttons = [
        InlineKeyboardButton(g, callback_data=f"grp|{index}|{code}|{g}") for g in grup_list
    ]
    rows = _with_back(_chunk(buttons), f"back|cat|{index}")
    return InlineKeyboardMarkup(rows)


def member_keyboard(index, kategori, grup, groups):
    code = CATEGORY_CODES[kategori]
    member_list = groups.get(kategori, {}).get(grup, [])
    buttons = [
        InlineKeyboardButton(m, callback_data=f"mem|{index}|{code}|{grup}|{m}")
        for m in member_list
    ]
    rows = _with_back(_chunk(buttons), f"back|grp|{index}|{code}")
    return InlineKeyboardMarkup(rows)


def gallery_keyboard_kpop(index, kategori, grup, member):
    """Keyboard pilih gallery, dipanggil setelah member dipilih (kategori kpop)."""
    code = CATEGORY_CODES[kategori]
    buttons = [
        InlineKeyboardButton(f"@{g}", callback_data=f"gal|{index}|{code}|{grup}|{member}|{gcode}")
        for g, gcode in GALLERY_CODES.items()
    ]
    rows = _with_back(_chunk(buttons), f"back|mem|{index}|{code}|{grup}")
    return InlineKeyboardMarkup(rows)


def gallery_keyboard_text(index, kategori):
    """Keyboard pilih gallery, dipanggil setelah user balas teks nama (kategori non-kpop)."""
    code = CATEGORY_CODES[kategori]
    buttons = [
        InlineKeyboardButton(f"@{g}", callback_data=f"galtxt|{index}|{code}|{gcode}")
        for g, gcode in GALLERY_CODES.items()
    ]
    rows = _with_back(_chunk(buttons), f"back|cat|{index}")
    return InlineKeyboardMarkup(rows)


# ---------- Alur /lihat (gallery -> kategori -> [grup] -> hasil) ----------


def gallery_keyboard_lihat():
    """Step pertama alur /lihat, jadi tanpa tombol back."""
    buttons = [
        InlineKeyboardButton(f"@{g}", callback_data=f"gal|lihat|{gcode}")
        for g, gcode in GALLERY_CODES.items()
    ]
    return InlineKeyboardMarkup(_chunk(buttons))


def category_keyboard_lihat(gallery):
    gcode = GALLERY_CODES[gallery]
    buttons = [
        InlineKeyboardButton(cat, callback_data=f"cat|lihat|{gcode}|{code}")
        for cat, code in CATEGORY_CODES.items()
    ]
    rows = _with_back(_chunk(buttons), "back|gallihat")
    return InlineKeyboardMarkup(rows)


def group_keyboard_lihat(gallery, kategori, groups):
    gcode = GALLERY_CODES[gallery]
    code = CATEGORY_CODES[kategori]
    grup_list = list(groups.get(kategori, {}).keys())
    buttons = [
        InlineKeyboardButton(g, callback_data=f"grp|lihat|{gcode}|{code}|{g}") for g in grup_list
    ]
    rows = _with_back(_chunk(buttons), f"back|catlihat|{gcode}")
    return InlineKeyboardMarkup(rows)
