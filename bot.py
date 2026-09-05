import os
import asyncio
import logging
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    KPOP_CATEGORIES,
    load_groups,
    category_keyboard,
    group_keyboard,
    member_keyboard,
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
        "Pilih kategori yang mau dilihat:", reply_markup=category_keyboard("lihat")
    )


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
    await send_next_username(update.effective_chat.id, context, 0)


async def send_next_username(chat_id, context, index):
    pending = context.user_data.get("pending", [])
    if index >= len(pending):
        await context.bot.send_message(chat_id, "Selesai! Semua username sudah dikategorikan.")
        context.user_data["pending"] = []
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
    query = update.callback_query
    await query.answer()
    _, index_str, cat_code, grup, member = query.data.split("|")
    index = int(index_str)
    kategori = CODE_TO_CATEGORY[cat_code]

    pending = context.user_data.get("pending", [])
    username = pending[index]

    sheets.add_entry(username, kategori, grup, member)
    await query.edit_message_text(f"Tersimpan: @{username} -> {kategori} / {grup} / {member}")
    await send_next_username(update.effective_chat.id, context, index + 1)


# ---------- Pesan teks: jawaban "based on" ATAU cek @username ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    awaiting = context.user_data.get("awaiting_text")

    if awaiting:
        index = awaiting["index"]
        kategori = awaiting["kategori"]
        pending = context.user_data.get("pending", [])
        username = pending[index]

        sheets.add_entry(username, kategori, "", text)
        context.user_data["awaiting_text"] = None
        await update.message.reply_text(f"Tersimpan: @{username} - {text} ({kategori})")
        await send_next_username(update.effective_chat.id, context, index + 1)
        return

    if text.startswith("@"):
        username = text[1:]
        row_index, row = sheets.find_entry(username)
        if row is None:
            await update.message.reply_text(f"@{username} tidak ditemukan di rekap.")
            return

        lokasi = row["Kategori"]
        if row.get("Grup"):
            lokasi += f" / {row['Grup']}"
        if row.get("Nama"):
            lokasi += f" / {row['Nama']}"

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
    sheets.delete_entry(int(row_index_str))
    await query.edit_message_text(f"@{username} sudah dihapus dari rekap.")


# ---------- /lihat: browsing rekap ----------

async def handle_lihat_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, cat_code = query.data.split("|")
    kategori = CODE_TO_CATEGORY[cat_code]

    if kategori in KPOP_CATEGORIES:
        await query.edit_message_text(
            f"Kategori: {kategori}\nPilih grup:",
            reply_markup=group_keyboard("lihat", kategori, GROUPS),
        )
    else:
        entries = sheets.get_entries_by_category(kategori)
        await query.edit_message_text(format_entries(kategori, entries))


async def handle_lihat_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, cat_code, grup = query.data.split("|")
    kategori = CODE_TO_CATEGORY[cat_code]
    entries = sheets.get_entries_by_category(kategori, grup)
    await query.edit_message_text(format_entries(kategori, entries, grup))


def format_entries(kategori, entries, grup=None):
    judul = kategori + (f" - {grup}" if grup else "")
    if not entries:
        return f"{judul}\nBelum ada rekap."

    by_sub: dict[str, list[str]] = {}
    for e in entries:
        sub = e.get("Grup") if kategori in KPOP_CATEGORIES else e.get("Nama")
        sub = sub or "-"
        by_sub.setdefault(sub, []).append(e["Username"])

    lines = [judul]
    for sub, usernames in by_sub.items():
        lines.append(f"\n{sub}")
        lines.extend(f"@{u}" for u in usernames)
    return "\n".join(lines)


def main():
    persistence = PicklePersistence(filepath="bot_data.pickle")
    app = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lihat", lihat_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Callback mode "input baru" (index berupa angka)
    app.add_handler(CallbackQueryHandler(handle_category_callback, pattern=r"^cat\|(?!lihat\|)\d"))
    app.add_handler(CallbackQueryHandler(handle_group_callback, pattern=r"^grp\|(?!lihat\|)\d"))
    app.add_handler(CallbackQueryHandler(handle_member_callback, pattern=r"^mem\|"))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern=r"^del\|"))

    # Callback mode "/lihat" (index = 'lihat')
    app.add_handler(CallbackQueryHandler(handle_lihat_category, pattern=r"^cat\|lihat\|"))
    app.add_handler(CallbackQueryHandler(handle_lihat_group, pattern=r"^grp\|lihat\|"))

    # Teks biasa paling akhir supaya command lain kepilih duluan
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
