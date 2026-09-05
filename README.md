# Telegram Username Categorizer Bot

Bot Telegram buat kategorisasi manual username jualan (kpop boygroup,
girlgroup, aktor, aktris, multi character, trainee, 2D/anime) dari
screenshot, dengan tombol interaktif, disimpan ke Google Spreadsheet.

## Alur pemakaian

1. Kirim screenshot daftar username (t.me/username) ke bot.
2. Bot baca teksnya lewat Google Cloud Vision (OCR), lalu kirim
   username **satu per satu** dengan tombol kategori: Kpop Boygroup,
   Kpop Girlgroup, Aktor, Aktris, Multi Character, Trainee, 2D/Anime.
3. Kalau pilih **Boygroup/Girlgroup** → muncul tombol pilih grup →
   lanjut tombol pilih member → tersimpan otomatis.
4. Kalau pilih **Aktor/Aktris/Multi Character/Trainee/2D-Anime** →
   bot minta balas teks "based on"-nya → tersimpan.
5. Ketik `/lihat` kapan saja → pilih kategori → (kalau kpop) pilih
   grup → bot tampilkan semua username yang sudah direkap di situ.
6. Ketik `@username` → bot cari di rekap, kasih tau lokasinya, dan
   kasih tombol **Hapus dari rekap** (misal karena sudah laku).

Semua data disimpan di **Google Spreadsheet**, jadi bisa kamu buka
dan edit langsung dari HP/PC kapan saja, di luar bot juga.

## File dalam folder ini

- `bot.py` — logic utama bot & semua handler tombol.
- `keyboards.py` — pembuat tombol kategori/grup/member.
- `sheets.py` — koneksi & operasi ke Google Sheets.
- `ocr.py` — baca teks dari screenshot pakai Google Cloud Vision.
- `groups.csv` — **contoh** daftar grup + member buat tombol. Tambah
  baris baru sendiri untuk grup/member lain (format:
  `kategori,grup,member`). Kategori harus persis salah satu dari:
  `Kpop Boygroup`, `Kpop Girlgroup` (kategori lain tidak perlu ada di
  sini karena alurnya minta teks langsung, bukan tombol member).
- `requirements.txt`, `Procfile` — buat deploy ke Railway.
- `.env.example` — contoh environment variable yang perlu diisi.

## Setup Google Cloud (sekali saja — dipakai buat Spreadsheet & OCR)

1. Buka https://console.cloud.google.com, buat project baru (atau
   pakai yang sudah ada).
2. Di **APIs & Services > Library**, cari dan aktifkan dua API ini:
   - **Google Sheets API**
   - **Cloud Vision API**
3. Di **APIs & Services > Credentials** → **Create Credentials** →
   **Service Account**. Kasih nama bebas, lanjut sampai selesai.
4. Buka service account yang baru dibuat → tab **Keys** → **Add Key**
   → **Create new key** → pilih **JSON** → file JSON otomatis
   terdownload. Isi file ini yang nanti dipakai sebagai
   `GOOGLE_CREDENTIALS_JSON` (dipakai bareng buat Sheets & Vision,
   nggak perlu bikin key terpisah).
5. Di dalam file JSON itu ada field `client_email` (contoh:
   `nama-bot@project-id.iam.gserviceaccount.com`).
6. Buat Google Spreadsheet baru di https://sheets.google.com, lalu
   **Share** spreadsheet itu ke email `client_email` tadi dengan akses
   **Editor**.
7. Ambil `GOOGLE_SHEET_ID` dari URL spreadsheet:
   `https://docs.google.com/spreadsheets/d/INI_ID_NYA/edit`.

Bot akan otomatis bikin sheet/tab bernama `Rekap` (atau sesuai
`GOOGLE_SHEET_NAME`) beserta header kolomnya saat pertama kali jalan.

**Soal biaya:** Cloud Vision API gratis sampai 1.000 gambar per bulan
(text detection). Kalau jualan username kamu nggak sampai ribuan
screenshot per bulan, ini nggak akan kena biaya sama sekali. Google
tetap minta kartu kredit/debit buat verifikasi akun Cloud Billing,
tapi nggak otomatis kecharge kalau masih di bawah limit gratis.

## Setup lokal (VS Code)

1. Buat virtual environment (opsional):
   ```
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Mac/Linux
   ```
2. Install dependency:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` jadi `.env`, isi semua variabelnya termasuk
   `GOOGLE_CREDENTIALS_JSON` (isi seluruh JSON dalam satu baris).
4. Export env var sebelum run (atau pakai `python-dotenv` kalau mau
   otomatis baca `.env`), lalu:
   ```
   python bot.py
   ```

## Deploy ke Railway

1. Push folder ini ke repo GitHub.
2. Di Railway: **New Project** → **Deploy from GitHub repo** → pilih
   repo ini.
3. Railway otomatis kebaca `Procfile` dan `requirements.txt`.
4. Di tab **Variables**, isi:
   - `TELEGRAM_BOT_TOKEN`
   - `GOOGLE_CREDENTIALS_JSON` (paste seluruh isi file JSON)
   - `GOOGLE_SHEET_ID`
   - (opsional) `GOOGLE_SHEET_NAME`, `GROUPS_PATH`
5. Pastikan service type-nya **Worker** (bot ini pakai polling, bukan
   webhook/HTTP server).
6. Deploy — bot langsung online.

## Catatan

- Update `groups.csv` kapan saja ada grup/member baru yang mau dijual
  usernamenya, lalu push ulang ke GitHub (Railway auto redeploy).
- Kolom di spreadsheet: `Username | Kategori | Grup | Nama | Tanggal`.
  Untuk kpop, `Grup` diisi nama grup dan `Nama` kosong. Untuk kategori
  lain, `Grup` kosong dan `Nama` diisi hasil "based on" yang kamu
  ketik.
- Data tombol kategori (`groups.csv`) itu terpisah dari data rekap
  (spreadsheet) — jadi kamu bisa bebas nambah pilihan tombol tanpa
  ganggu data yang sudah tersimpan.
