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


def category_keyboard(index):
    """Tombol pilih kategori. `index` = posisi username di list (int) atau 'lihat' untuk mode browsing."""
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
    return InlineKeyboardMarkup(_chunk(buttons))


def member_keyboard(index, kategori, grup, groups):
    code = CATEGORY_CODES[kategori]
    member_list = groups.get(kategori, {}).get(grup, [])
    buttons = [
        InlineKeyboardButton(m, callback_data=f"mem|{index}|{code}|{grup}|{m}")
        for m in member_list
    ]
    return InlineKeyboardMarkup(_chunk(buttons))
