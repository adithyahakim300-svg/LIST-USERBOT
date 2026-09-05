import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = ["Username", "Kategori", "Grup", "Nama", "Tanggal", "Gallery"]

_worksheet = None  # cache supaya tidak auth berulang-ulang tiap request


def _get_client():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    global _worksheet
    if _worksheet is not None:
        return _worksheet
    client = _get_client()
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sheet_name = os.environ.get("GOOGLE_SHEET_NAME", "Rekap")
    sh = client.open_by_key(sheet_id)
    try:
        worksheet = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_name, rows=2000, cols=len(HEADER))
        worksheet.append_row(HEADER)

    _ensure_gallery_header(worksheet)
    _worksheet = worksheet
    return worksheet


def _ensure_gallery_header(worksheet):
    """Pastikan header kolom terakhir ('Gallery') selalu terisi.

    Sheet lama (dibuat sebelum kolom Gallery ada) tidak otomatis punya
    header ini, walau datanya sudah tersimpan di kolom F. Cek dan
    perbaiki sendiri di sini supaya tidak bergantung pada edit manual.
    """
    gallery_col = len(HEADER)  # posisi kolom "Gallery"
    current_header = worksheet.row_values(1)
    if len(current_header) < gallery_col or current_header[gallery_col - 1] != "Gallery":
        worksheet.update_cell(1, gallery_col, "Gallery")


def add_entry(username: str, kategori: str, grup: str, nama: str, gallery: str):
    ws = get_sheet()
    tanggal = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.append_row([username, kategori, grup, nama, tanggal, gallery])


def find_entry(username: str):
    """Cari baris berdasarkan username. Return (row_index, row_dict) atau (None, None).
    Kalau usernamenya ada di lebih dari 1 baris (misal beda gallery), ini cuma
    kasih yang PERTAMA ketemu — pakai find_entries() kalau butuh semuanya."""
    ws = get_sheet()
    records = ws.get_all_records()
    for offset, row in enumerate(records):
        if str(row.get("Username", "")).strip().lower() == username.strip().lower():
            row_index = offset + 2  # +2: baris 1 header, get_all_records index dari 0
            return row_index, row
    return None, None


def find_entries(username: str):
    """Cari SEMUA baris yang match username (bisa lebih dari 1, misal beda gallery/kategori).
    Return list of (row_index, row_dict), urut sesuai urutan baris di sheet."""
    ws = get_sheet()
    records = ws.get_all_records()
    target = username.strip().lower()
    result = []
    for offset, row in enumerate(records):
        if str(row.get("Username", "")).strip().lower() == target:
            row_index = offset + 2
            result.append((row_index, row))
    return result


def delete_entry(row_index: int):
    ws = get_sheet()
    ws.delete_rows(row_index)


def get_entries_by_category(kategori: str, grup: str | None = None, gallery: str | None = None):
    ws = get_sheet()
    records = ws.get_all_records()
    result = []
    for row in records:
        if row.get("Kategori") != kategori:
            continue
        if grup is not None and row.get("Grup") != grup:
            continue
        if gallery is not None and row.get("Gallery") != gallery:
            continue
        result.append(row)
    return result
