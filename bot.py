import os
import asyncio
import logging
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PicklePersistence,
)

from keyboards import (
    CODE_TO_CATEGORY,
    CATEGORY_CODES,
    KPOP_CATEGORIES,
    CODE_TO_GALLERY,
    load_groups,
    category_keyboard,
    group_keyboard,
    member_keyboard,
    gallery_keyboard_kpop,
    gallery_keyboard_text,
    gallery_keyboard_lihat,
    category_keyboard_lihat,
    group_keyboard_lihat,
    back_only_keyboard,
)
import sheets
import ocr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROUPS_PATH = os.environ.get("GROUPS_PATH", "groups.csv")

GROUPS = load_groups(GROUPS_PATH)


# ---------- Command dasar ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Kirim screenshot daftar username buat dikategorikan.\n"
        "Ketik /lihat buat cek rekap yang sudah ada.\n"
        "Kirim @username buat cek lokasi kategorinya."
    )


async def lihat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Pilih gallery yang mau dilihat:", reply_markup=gallery_keyboard_lihat()
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tambah 1 username manual tanpa screenshot: /add @username"""
    if not context.args:
        await update.message.reply_text(
            "Pakai format: /add @username\nContoh: /add @Minwooky"
        )
        return

    username = context.args[0].lstrip("@").strip()
    if not username:
        await update.message.reply_text(
            "Pakai format: /add @username\nContoh: /add @Minwooky"
        )
        return

    # Tambahkan ke antrian yang sedang berjalan (kalau ada), atau mulai antrian baru.
    pending = context.user_data.setdefault("pending", [])
    context.user_data.setdefault("nama_store", {})
    index = len(pending)
    pending.append(username)

    await update.message.reply_text(
        f"@{username}\nPilih kategori:", reply_markup=category_keyboard(index)
    )


async def hapus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cari semua lokasi username, lalu kasih tombol hapus per-lokasi: /hapus @username"""
    if not context.args:
        await update.message.reply_text(
            "Pakai format: /hapus @username\nContoh: /hapus @Minwooky"
        )
        return

    username = context.args[0].lstrip("@").strip()
    if not username:
        await update.message.reply_text(
            "Pakai format: /hapus @username\nContoh: /hapus @Minwooky"
        )
        return

    try:
        entries = await asyncio.to_thread(sheets.find_entries, username)
    except Exception as e:
        logger.error("Gagal baca dari Sheets: %s", e)
        await update.message.reply_text("Gagal cek rekap, coba lagi sebentar lagi.")
        return

    if not entries:
        await update.message.reply_text(f"@{username} tidak ditemukan di rekap.")
        return

    lines = [f"@{username} ditemukan di {len(entries)} lokasi:"]
    buttons = []
    for i, (row_index, row) in enumerate(entries, start=1):
        lokasi = row.get("Kategori", "")
        if row.get("Grup"):
            lokasi += f" / {row['Grup']}"
        if row.get("Nama"):
            lokasi += f" / {row['Nama']}"
        if row.get("Gallery"):
            lokasi += f" (@{row['Gallery']})"
        lines.append(f"{i}. {lokasi}")
        buttons.append(
            [InlineKeyboardButton(f"🗑 Hapus #{i}", callback_data=f"delhap|{row_index}|{username}")]
        )
    buttons.append([InlineKeyboardButton("❌ Batal", callback_data="delhap_batal")])

    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


# ---------- Alur input dari screenshot ----------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Lagi baca gambar...")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = BytesIO()
    await file.download_to_memory(out=buf)

    try:
        usernames = await asyncio.to_thread(ocr.extract_usernames_from_image, buf.getvalue())
    except RuntimeError as e:
        logger.error("Vision API error: %s", e)
        await update.message.reply_text("Gagal proses OCR, coba lagi sebentar lagi.")
        return

    if not usernames:
        await update.message.reply_text(
            "Gagal baca username dari gambar. Coba kirim ulang screenshot yang lebih jelas."
        )
        return

    context.user_data["pending"] = usernames
    context.user_data["awaiting_text"] = None
    context.user_data["nama_store"] = {}
    await send_next_username(update.effective_chat.id, context, 0)


async def send_next_username(chat_id, context, index):
    pending = context.user_data.get("pending", [])
    if index >= len(pending):
        await context.bot.send_message(chat_id, "Selesai! Semua username sudah dikategorikan.")
        context.user_data["pending"] = []
        context.user_data["nama_store"] = {}
        return
    username = pending[index]
    await context.bot.send_message(
        chat_id,
        f"@{username}\nPilih kategori:",
        reply_markup=category_keyboard(index),
    )


async def handle_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]

    pending = context.user_data.get("pending", [])
    if index >= len(pending):
        return
    username = pending[index]

    if kategori in KPOP_CATEGORIES:
        await query.edit_message_text(
            f"@{username}\nKategori: {kategori}\nPilih grup:",
            reply_markup=group_keyboard(index, kategori, GROUPS),
        )
    else:
        context.user_data["awaiting_text"] = {"index": index, "kategori": kategori}
        await query.edit_message_text(
            f"@{username}\nKategori: {kategori}\nBalas pesan ini dengan nama / based on-nya:"
        )


async def handle_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code, grup = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]

    pending = context.user_data.get("pending", [])
    username = pending[index]

    await query.edit_message_text(
        f"@{username}\nKategori: {kategori}\nGrup: {grup}\nPilih member:",
        reply_markup=member_keyboard(index, kategori, grup, GROUPS),
    )


async def handle_member_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Member dipilih -> lanjut pilih gallery dulu, belum simpan."""
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code, grup, member = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]

    pending = context.user_data.get("pending", [])
    username = pending[index]

    await query.edit_message_text(
        f"@{username}\nKategori: {kategori}\nGrup: {grup}\nNama: {member}\nSimpan ke gallery mana?",
        reply_markup=gallery_keyboard_kpop(index, kategori, grup, member),
    )


async def handle_gallery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gallery dipilih (alur kpop) -> simpan ke Sheets."""
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code, grup, member, gal_code = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]
    gallery = CODE_TO_GALLERY[gal_code]

    pending = context.user_data.get("pending", [])
    username = pending[index]

    try:
        await asyncio.to_thread(sheets.add_entry, username, kategori, grup, member, gallery)
    except Exception as e:
        logger.error("Gagal simpan ke Sheets: %s", e)
        await query.edit_message_text("Gagal simpan ke rekap, coba lagi sebentar lagi.")
        return
    await query.edit_message_text(
        f"Tersimpan: @{username} -> {kategori} / {grup} / {member} (@{gallery})"
    )
    await send_next_username(update.effective_chat.id, context, index + 1)


async def handle_galtxt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gallery dipilih (alur non-kpop, nama dari balasan teks) -> simpan ke Sheets."""
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code, gal_code = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]
    gallery = CODE_TO_GALLERY[gal_code]

    pending = context.user_data.get("pending", [])
    username = pending[index]
    nama = context.user_data.get("nama_store", {}).get(index, "")

    try:
        await asyncio.to_thread(sheets.add_entry, username, kategori, "", nama, gallery)
    except Exception as e:
        logger.error("Gagal simpan ke Sheets: %s", e)
        await query.edit_message_text("Gagal simpan ke rekap, coba lagi sebentar lagi.")
        return
    context.user_data.get("nama_store", {}).pop(index, None)
    await query.edit_message_text(f"Tersimpan: @{username} - {nama} ({kategori}) (@{gallery})")
    await send_next_username(update.effective_chat.id, context, index + 1)


# ---------- Tombol Kembali ----------

async def handle_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    target = parts[1]

    pending = context.user_data.get("pending", [])

    if target == "cat":
        index = int(parts[2])
        username = pending[index]
        await query.edit_message_text(
            f"@{username}\nPilih kategori:", reply_markup=category_keyboard(index)
        )

    elif target == "grp":
        index = int(parts[2])
        cat_code = parts[3]
        kategori = CODE_TO_CATEGORY[cat_code]
        username = pending[index]
        await query.edit_message_text(
            f"@{username}\nKategori: {kategori}\nPilih grup:",
            reply_markup=group_keyboard(index, kategori, GROUPS),
        )

    elif target == "mem":
        index = int(parts[2])
        cat_code = parts[3]
        grup = parts[4]
        kategori = CODE_TO_CATEGORY[cat_code]
        username = pending[index]
        await query.edit_message_text(
            f"@{username}\nKategori: {kategori}\nGrup: {grup}\nPilih member:",
            reply_markup=member_keyboard(index, kategori, grup, GROUPS),
        )

    elif target == "gallihat":
        await query.edit_message_text(
            "Pilih gallery yang mau dilihat:", reply_markup=gallery_keyboard_lihat()
        )

    elif target == "catlihat":
        gal_code = parts[2]
        gallery = CODE_TO_GALLERY[gal_code]
        await query.edit_message_text(
            f"Gallery: @{gallery}\nPilih kategori:",
            reply_markup=category_keyboard_lihat(gallery),
        )

    elif target == "grplihat":
        gal_code = parts[2]
        cat_code = parts[3]
        gallery = CODE_TO_GALLERY[gal_code]
        kategori = CODE_TO_CATEGORY[cat_code]
        await query.edit_message_text(
            f"Gallery: @{gallery}\nKategori: {kategori}\nPilih grup:",
            reply_markup=group_keyboard_lihat(gallery, kategori, GROUPS),
        )


# ---------- Pesan teks: jawaban "based on" ATAU cek @username ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    awaiting = context.user_data.get("awaiting_text")

    if awaiting:
        index = awaiting["index"]
        kategori = awaiting["kategori"]
        pending = context.user_data.get("pending", [])
        username = pending[index]

        context.user_data["awaiting_text"] = None
        context.user_data.setdefault("nama_store", {})[index] = text
        await update.message.reply_text(
            f"@{username}\nKategori: {kategori}\nNama: {text}\nSimpan ke gallery mana?",
            reply_markup=gallery_keyboard_text(index, kategori),
        )
        return

    if text.startswith("@"):
        username = text[1:]
        try:
            row_index, row = await asyncio.to_thread(sheets.find_entry, username)
        except Exception as e:
            logger.error("Gagal baca dari Sheets: %s", e)
            await update.message.reply_text("Gagal cek rekap, coba lagi sebentar lagi.")
            return
        if row is None:
            await update.message.reply_text(f"@{username} tidak ditemukan di rekap.")
            return

        lokasi = row["Kategori"]
        if row.get("Grup"):
            lokasi += f" / {row['Grup']}"
        if row.get("Nama"):
            lokasi += f" / {row['Nama']}"
        if row.get("Gallery"):
            lokasi += f" (@{row['Gallery']})"

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Hapus dari rekap", callback_data=f"del|{row_index}|{username}")]]
        )
        await update.message.reply_text(f"@{username} ada di: {lokasi}", reply_markup=keyboard)
        return

    await update.message.reply_text(
        "Kirim screenshot buat dikategorikan, atau ketik @username buat cek lokasinya."
    )


async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, row_index_str, username = query.data.split("|")
    try:
        await asyncio.to_thread(sheets.delete_entry, int(row_index_str))
    except Exception as e:
        logger.error("Gagal hapus dari Sheets: %s", e)
        await query.edit_message_text("Gagal hapus dari rekap, coba lagi sebentar lagi.")
        return
    await query.edit_message_text(f"@{username} sudah dihapus dari rekap.")


async def handle_delhap_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tombol hapus/batal dari hasil /hapus (bisa lebih dari 1 lokasi per username)."""
    query = update.callback_query
    await query.answer()

    if query.data == "delhap_batal":
        await query.edit_message_text("Dibatalkan.")
        return

    _, row_index_str, username = query.data.split("|")
    row_index = int(row_index_str)

    try:
        ws = sheets.get_sheet()
        current_row = await asyncio.to_thread(ws.row_values, row_index)
    except Exception as e:
        logger.error("Gagal baca baris sebelum hapus: %s", e)
        await query.edit_message_text("Gagal hapus dari rekap, coba lagi sebentar lagi.")
        return

    # Validasi baris masih username yang sama, jaga-jaga kalau ada baris lain
    # yang sudah lebih dulu dihapus dari tombol lain di pesan yang sama
    # (posisi baris di bawahnya jadi geser).
    current_username = current_row[0].strip().lower() if current_row else ""
    if current_username != username.strip().lower():
        await query.edit_message_text(
            "Data sudah berubah (kemungkinan ada baris lain yang baru dihapus).\n"
            "Jalankan /hapus lagi buat lihat lokasi terbaru."
        )
        return

    try:
        await asyncio.to_thread(sheets.delete_entry, row_index)
    except Exception as e:
        logger.error("Gagal hapus dari Sheets: %s", e)
        await query.edit_message_text("Gagal hapus dari rekap, coba lagi sebentar lagi.")
        return
    await query.edit_message_text(f"@{username} (lokasi ini) sudah dihapus dari rekap.")


# ---------- /lihat: browsing rekap ----------

async def handle_lihat_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, gal_code = query.data.split("|")
    gallery = CODE_TO_GALLERY[gal_code]
    await query.edit_message_text(
        f"Gallery: @{gallery}\nPilih kategori:",
        reply_markup=category_keyboard_lihat(gallery),
    )


async def handle_lihat_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, gal_code, cat_code = query.data.split("|")
    gallery = CODE_TO_GALLERY[gal_code]
    kategori = CODE_TO_CATEGORY[cat_code]

    if kategori in KPOP_CATEGORIES:
        await query.edit_message_text(
            f"Gallery: @{gallery}\nKategori: {kategori}\nPilih grup:",
            reply_markup=group_keyboard_lihat(gallery, kategori, GROUPS),
        )
    else:
        try:
            entries = await asyncio.to_thread(
                sheets.get_entries_by_category, kategori, None, gallery
            )
        except Exception as e:
            logger.error("Gagal baca dari Sheets: %s", e)
            await query.edit_message_text("Gagal ambil rekap, coba lagi sebentar lagi.")
            return
        await query.edit_message_text(
            format_entries(kategori, entries, gallery=gallery),
            reply_markup=back_only_keyboard(f"back|catlihat|{gal_code}"),
        )


async def handle_lihat_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, gal_code, cat_code, grup = query.data.split("|")
    gallery = CODE_TO_GALLERY[gal_code]
    kategori = CODE_TO_CATEGORY[cat_code]
    try:
        entries = await asyncio.to_thread(
            sheets.get_entries_by_category, kategori, grup, gallery
        )
    except Exception as e:
        logger.error("Gagal baca dari Sheets: %s", e)
        await query.edit_message_text("Gagal ambil rekap, coba lagi sebentar lagi.")
        return
    await query.edit_message_text(
        format_entries(kategori, entries, grup, gallery),
        reply_markup=back_only_keyboard(f"back|grplihat|{gal_code}|{cat_code}"),
    )


def format_entries(kategori, entries, grup=None, gallery=None):
    judul = kategori + (f" - {grup}" if grup else "")
    if gallery:
        judul += f" (@{gallery})"
    if not entries:
        return f"{judul}\nBelum ada rekap."

    by_sub: dict[str, list[str]] = {}
    for e in entries:
        # Selalu grouping berdasarkan Nama (member untuk kpop, nama/based-on untuk lainnya).
        # Kolom Grup tidak dipakai lagi di sini karena pada level ini nilainya
        # sudah sama untuk semua entri (grup sudah dipilih sebelumnya).
        sub = e.get("Nama") or "-"
        by_sub.setdefault(sub, []).append(e["Username"])

    lines = [judul]
    for sub, usernames in by_sub.items():
        lines.append(f"\n{sub}")
        lines.extend(f"@{u}" for u in usernames)
    return "\n".join(lines)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                "Ada error tak terduga, coba lagi sebentar lagi.",
            )
        except Exception:
            pass


async def post_init(app: Application):
    """Daftarkan daftar command supaya muncul di menu '/' Telegram."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Mulai & lihat cara pakai bot"),
            BotCommand("add", "Tambah 1 username manual: /add @username"),
            BotCommand("lihat", "Lihat rekap yang sudah tersimpan"),
            BotCommand("hapus", "Hapus username dari rekap: /hapus @username"),
        ]
    )


def main():
    persistence = PicklePersistence(filepath="bot_data.pickle")
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lihat", lihat_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("hapus", hapus_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Callback mode "input baru" (index berupa angka)
    app.add_handler(CallbackQueryHandler(handle_category_callback, pattern=r"^cat\|(?!lihat\|)\d"))
    app.add_handler(CallbackQueryHandler(handle_group_callback, pattern=r"^grp\|(?!lihat\|)\d"))
    app.add_handler(CallbackQueryHandler(handle_member_callback, pattern=r"^mem\|"))
    app.add_handler(CallbackQueryHandler(handle_gallery_callback, pattern=r"^gal\|(?!lihat\|)\d"))
    app.add_handler(CallbackQueryHandler(handle_galtxt_callback, pattern=r"^galtxt\|"))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern=r"^del\|"))
    app.add_handler(CallbackQueryHandler(handle_delhap_callback, pattern=r"^delhap"))

    # Callback mode "/lihat" (gallery -> kategori -> [grup] -> hasil)
    app.add_handler(CallbackQueryHandler(handle_lihat_gallery, pattern=r"^gal\|lihat\|"))
    app.add_handler(CallbackQueryHandler(handle_lihat_category, pattern=r"^cat\|lihat\|"))
    app.add_handler(CallbackQueryHandler(handle_lihat_group, pattern=r"^grp\|lihat\|"))

    # Tombol kembali (semua alur)
    app.add_handler(CallbackQueryHandler(handle_back_callback, pattern=r"^back\|"))

    # Teks biasa paling akhir supaya command lain kepilih duluan
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
