import asyncio
import logging
import os
import re
import glob
import uuid
from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from config import settings
from database import supabase
from ai_service import AIService, RateLimitError

RATE_LIMIT_MSG = "I'm a bit overwhelmed right now — please try again in a minute."
from document_factory import DocumentFactory, _extract_tax_rate

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# In-memory store for files uploaded during ONBOARDING
# Dict mapping telegram_id -> list of local file paths
onboarding_files = {}

# Restore any files left in the temp directory from previous sessions
for filepath in glob.glob(os.path.join(TEMP_DIR, "*")):
    filename = os.path.basename(filepath)
    if "_" in filename:
        user_id_str = filename.split("_")[0]
        try:
            user_id = int(user_id_str)
            if user_id not in onboarding_files:
                onboarding_files[user_id] = []
            if filepath not in onboarding_files[user_id]:
                onboarding_files[user_id].append(filepath)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def update_user_state(telegram_id: int, state: str):
    """Updates the user's bot_state in Supabase (runs in thread to avoid blocking event loop)."""
    await asyncio.to_thread(
        lambda: supabase.table("users").update({"bot_state": state}).eq("telegram_id", telegram_id).execute()
    )


async def get_user(telegram_id: int):
    """Retrieves user by telegram_id (runs in thread to avoid blocking event loop)."""
    def _fetch():
        res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        return res.data[0] if res.data else None
    return await asyncio.to_thread(_fetch)


async def get_brand_dna(user_id: str) -> dict:
    """Retrieves the user's Brand DNA config from Supabase (runs in thread)."""
    def _fetch():
        res = supabase.table("user_configs").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else {}
    return await asyncio.to_thread(_fetch)


# ---------------------------------------------------------------------------
# Quote formatting helper
# ---------------------------------------------------------------------------

def format_quote_summary(quote_data: dict, brand_dna: dict) -> str:
    """Formats a structured quote as a readable Telegram message with a confirmation prompt."""
    currency = quote_data.get("currency") or brand_dna.get("currency") or "USD"
    customer = quote_data.get("customer_name") or "Customer"
    lines = [f"*Quote for {customer}*"]

    if quote_data.get("customer_address"):
        lines.append(f"_{quote_data['customer_address']}_")

    lines.append("")
    subtotal = 0.0
    for item in quote_data.get("line_items", []):
        desc = item.get("description", "Item")
        qty = float(item.get("quantity", 1))
        price = float(item.get("unit_price", 0.0))
        line_total = qty * price
        subtotal += line_total
        lines.append(f"• {desc} × {qty:.0f} @ {currency} {price:.2f} = {currency} {line_total:.2f}")

    lines.append("")
    lines.append(f"*Subtotal: {currency} {subtotal:.2f}*")

    tax_rate = _extract_tax_rate(brand_dna)
    if tax_rate > 0:
        tax_amount = subtotal * (tax_rate / 100)
        lines.append(f"VAT/Tax ({tax_rate:.0f}%): {currency} {tax_amount:.2f}")
        lines.append(f"*TOTAL: {currency} {subtotal + tax_amount:.2f}*")

    lines.append("\nDoes this look right? Reply *YES* to generate the document, or tell me what to change.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Document generation + delivery
# ---------------------------------------------------------------------------

async def generate_and_send_quote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user: dict,
    quote_data: dict,
    brand_dna: dict,
    status_msg=None,
):
    """Generates the quote document, sends it, stores in DB, and cleans up."""
    user = update.effective_user

    # Daily usage limit (testing phase)
    DAILY_LIMIT = 5
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        def _count_daily():
            return supabase.table("documents") \
                .select("id", count="exact") \
                .eq("user_id", db_user["id"]) \
                .gte("created_at", yesterday) \
                .execute()
        count_res = await asyncio.to_thread(_count_daily)
        daily_count = count_res.count or 0
    except Exception:
        daily_count = 0

    if daily_count >= DAILY_LIMIT:
        msg_text = (
            f"You've reached the daily limit of {DAILY_LIMIT} quotes during the testing phase. "
            "Try again tomorrow!"
        )
        if status_msg:
            await status_msg.edit_text(msg_text)
        else:
            await update.message.reply_text(msg_text)
        context.user_data.pop("pending_quote", None)
        context.user_data.pop("pending_brand_dna", None)
        await update_user_state(user.id, "ACTIVE")
        return

    if status_msg:
        await status_msg.edit_text("Generating your quote document...")
    else:
        status_msg = await update.message.reply_text("Generating your quote document...")

    # Build filename: Quote_Smith_001_a3f2bc.docx (UUID suffix prevents collisions)
    preferred_format = brand_dna.get("preferred_format") or "docx"
    output_ext = "xlsx" if preferred_format == "xlsx" else "docx"
    raw_name = quote_data.get("customer_name") or "Client"
    surname = re.sub(r'[^A-Za-z0-9]', '', raw_name.strip().split()[-1]) or "Client"
    try:
        def _count_total():
            return supabase.table("documents").select("id", count="exact").eq("user_id", db_user["id"]).execute()
        total_res = await asyncio.to_thread(_count_total)
        quote_num = (total_res.count or 0) + 1
    except Exception:
        quote_num = 1
    unique_id = uuid.uuid4().hex[:6]
    output_filename = f"Quote_{surname}_{quote_num:03d}_{unique_id}.{output_ext}"

    if preferred_format == "xlsx":
        result = await asyncio.to_thread(DocumentFactory.generate_xlsx, quote_data, brand_dna, output_filename)
    else:
        result = await asyncio.to_thread(DocumentFactory.generate_docx, quote_data, brand_dna, output_filename)

    doc_path = result["filepath"]

    if not os.path.exists(doc_path):
        await status_msg.edit_text("Failed to generate the document. Please try again.")
        return

    # Send the document
    with open(doc_path, 'rb') as doc_file:
        await context.bot.send_document(chat_id=user.id, document=doc_file, filename=output_filename)
    await status_msg.edit_text("Here is your generated quote!")

    # Cleanup local file
    try:
        os.remove(doc_path)
    except Exception:
        pass

    # Persist to Supabase documents table
    try:
        doc_record = {
            "user_id": db_user["id"],
            "customer_name": quote_data.get("customer_name"),
            "customer_address": quote_data.get("customer_address"),
            "line_items": quote_data.get("line_items", []),
            "subtotal": result["subtotal"],
            "tax_amount": result["tax_amount"],
            "total": result["total"],
        }
        await asyncio.to_thread(lambda: supabase.table("documents").insert(doc_record).execute())
    except Exception as e:
        logger.error(f"Failed to store quote in Supabase: {e}")

    # Clear pending state and return user to ACTIVE
    context.user_data.pop("pending_quote", None)
    context.user_data.pop("pending_brand_dna", None)
    await update_user_state(user.id, "ACTIVE")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    payload = context.args[0] if context.args else None

    existing_user = await get_user(user.id)

    if existing_user:
        state = existing_user.get("bot_state")
        if state == "HANDSHAKE":
            await update_user_state(user.id, "ONBOARDING")
            await update.message.reply_text(
                "Welcome! Let's get started. Please send me 3–10 examples of your past quotes or invoices "
                "(PDF or Images). When you're done, type /finish\\_onboarding.",
                parse_mode="Markdown"
            )
        elif state == "ONBOARDING":
            await update.message.reply_text(
                "You are currently setting up your Brand DNA. "
                "Please upload sample quotes/invoices or type /finish\\_onboarding.",
                parse_mode="Markdown"
            )
        elif state == "AWAITING_FORMAT":
            await update.message.reply_text(
                "Almost there! What format would you like your quotes in?\n\n"
                "Reply *1* for Word (.docx)\n"
                "Reply *2* for Excel (.xlsx)",
                parse_mode="Markdown"
            )
        elif state in ("ACTIVE", "AWAITING_CONFIRMATION"):
            await update.message.reply_text(
                "Your account is active! Send me a voice note, photo, or type the job details to generate a quote."
            )
        return

    # First-time link via deep-link payload (UUID from web registration)
    if payload:
        try:
            def _link_user():
                res = supabase.table("users").select("*").eq("id", payload).execute()
                if res.data:
                    supabase.table("users").update({
                        "telegram_id": user.id,
                        "bot_state": "ONBOARDING"
                    }).eq("id", payload).execute()
                return res.data
            data = await asyncio.to_thread(_link_user)
            if data:
                await update.message.reply_text(
                    f"Hi {user.first_name}! Account linked. Let's learn your Brand DNA.\n\n"
                    "Please upload 3–10 past invoices or quotes (PDF/Image). "
                    "Type /finish\\_onboarding when done.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("Invalid registration link. Please register on the website first.")
        except Exception as e:
            logger.error(f"Error during linking: {e}")
            await update.message.reply_text("An error occurred linking your account. Please try again.")
    else:
        await update.message.reply_text("Hi! Please visit our website to register before using the bot.")


async def finish_onboarding(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user or db_user.get("bot_state") != "ONBOARDING":
        await update.message.reply_text("You are not currently in the onboarding phase.")
        return

    files = onboarding_files.get(user.id, [])
    if len(files) < 1:
        await update.message.reply_text("Please upload at least 1 sample invoice before finishing.")
        return

    msg = await update.message.reply_text(
        f"Processing {len(files)} document(s) to extract your Brand DNA. This might take a minute..."
    )

    try:
        dna_data = await asyncio.to_thread(AIService.extract_brand_dna, files)
    except RateLimitError:
        await msg.edit_text(RATE_LIMIT_MSG)
        return

    if not dna_data:
        await msg.edit_text(
            "Sorry, I couldn't extract your details. Please try uploading clearer images/PDFs."
        )
        return

    dna_data["user_id"] = db_user["id"]
    try:
        await asyncio.to_thread(lambda: supabase.table("user_configs").upsert(dna_data).execute())

        # Cleanup temp files
        for f in files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        onboarding_files.pop(user.id, None)

        # Move to format selection step
        await update_user_state(user.id, "AWAITING_FORMAT")
        await msg.edit_text(
            "✅ Brand DNA extracted!\n\n"
            "One last thing — what format would you like your quotes in?\n\n"
            "Reply *1* for Word (.docx)\n"
            "Reply *2* for Excel (.xlsx)",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Failed saving config: {e}")
        await msg.edit_text("Failed to save your configuration. Please try again.")


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles Photos and Documents (PDFs) in ONBOARDING and ACTIVE states."""
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    state = db_user.get("bot_state")

    if state == "ONBOARDING":
        file_obj = None
        ext = ""
        if update.message.document:
            file_obj = await context.bot.get_file(update.message.document.file_id)
            filename = update.message.document.file_name
            if filename and '.' in filename:
                ext = f".{filename.split('.')[-1]}"
            else:
                ext = ".pdf"
        elif update.message.photo:
            file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
            ext = ".jpg"

        if file_obj:
            filepath = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}{ext}")
            await file_obj.download_to_drive(custom_path=filepath)

            if user.id not in onboarding_files:
                onboarding_files[user.id] = []
            onboarding_files[user.id].append(filepath)

            await update.message.reply_text(
                f"Received sample {len(onboarding_files[user.id])}. "
                "Send more or type /finish\\_onboarding.",
                parse_mode="Markdown"
            )

    elif state == "ACTIVE":
        if update.message.photo:
            msg = await update.message.reply_text("Analysing your photo to extract quote details...")

            file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
            filepath = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}.jpg")
            await file_obj.download_to_drive(custom_path=filepath)

            brand_dna = await get_brand_dna(db_user["id"])
            try:
                quote_data = await asyncio.to_thread(AIService.extract_quote_from_image, filepath)
            except RateLimitError:
                await msg.edit_text(RATE_LIMIT_MSG)
                return

            try:
                os.remove(filepath)
            except Exception:
                pass

            if not quote_data or not quote_data.get("line_items"):
                await msg.edit_text(
                    "Sorry, I couldn't extract quote details from that image. "
                    "Try a clearer photo or describe the job in text."
                )
                return

            quote_data.setdefault("currency", brand_dna.get("currency") or "USD")
            context.user_data["pending_quote"] = quote_data
            context.user_data["pending_brand_dna"] = brand_dna
            await update_user_state(user.id, "AWAITING_CONFIRMATION")

            summary = format_quote_summary(quote_data, brand_dna)
            await msg.edit_text(summary, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "Send a *photo* of your handwritten notes to extract a quote, "
                "or just type or voice the job details.",
                parse_mode="Markdown"
            )

    elif state == "AWAITING_CONFIRMATION":
        await update.message.reply_text(
            "I'm waiting on your confirmation for the current quote. "
            "Reply *YES* to generate it, or describe what to change.",
            parse_mode="Markdown"
        )

    elif state == "AWAITING_FORMAT":
        await update.message.reply_text(
            "Please reply with *1* for Word (.docx) or *2* for Excel (.xlsx).",
            parse_mode="Markdown"
        )


async def handle_text_or_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    state = db_user.get("bot_state")

    # ------------------------------------------------------------------
    # AWAITING_FORMAT: user is selecting their preferred output format
    # ------------------------------------------------------------------
    if state == "AWAITING_FORMAT":
        text = (update.message.text or "").strip().lower()
        format_map = {
            "1": "docx", "word": "docx", "docx": "docx", "doc": "docx",
            "2": "xlsx", "excel": "xlsx", "xlsx": "xlsx", "spreadsheet": "xlsx",
        }
        chosen_format = format_map.get(text)

        if not chosen_format:
            await update.message.reply_text(
                "Please reply *1* for Word (.docx) or *2* for Excel (.xlsx).",
                parse_mode="Markdown"
            )
            return

        try:
            await asyncio.to_thread(
                lambda: supabase.table("user_configs").update({"preferred_format": chosen_format}).eq("user_id", db_user["id"]).execute()
            )
            await update_user_state(user.id, "ACTIVE")
            format_name = "Word (.docx)" if chosen_format == "docx" else "Excel (.xlsx)"
            await update.message.reply_text(
                f"✅ Perfect, I'll generate your quotes as *{format_name}*.\n\n"
                "You're all set! Send me a voice note, photo, or type the job details to generate your first quote.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to save format preference: {e}")
            await update.message.reply_text("Failed to save your preference. Please try again.")
        return

    # ------------------------------------------------------------------
    # AWAITING_CONFIRMATION: user is reviewing a pending quote
    # ------------------------------------------------------------------
    if state == "AWAITING_CONFIRMATION":
        if update.message.voice:
            await update.message.reply_text(
                "I'm waiting for your confirmation. Reply with text — say *YES* to generate, or describe what to change.",
                parse_mode="Markdown"
            )
            return

        pending_quote = context.user_data.get("pending_quote")
        pending_brand_dna = context.user_data.get("pending_brand_dna")

        if not pending_quote:
            # State lost on restart — reset gracefully
            await update_user_state(user.id, "ACTIVE")
            await update.message.reply_text(
                "Sorry, I lost track of the pending quote (likely a restart). Please send the job details again."
            )
            return

        msg = await update.message.reply_text("Checking your response...")
        try:
            result = await asyncio.to_thread(AIService.refine_quote, pending_quote, update.message.text or "")
        except RateLimitError:
            await msg.edit_text(RATE_LIMIT_MSG)
            return

        if result.get("confirmed"):
            await generate_and_send_quote(
                update, context, db_user,
                result.get("updated_quote", pending_quote),
                pending_brand_dna,
                status_msg=msg
            )
        else:
            updated_quote = result.get("updated_quote", pending_quote)
            context.user_data["pending_quote"] = updated_quote
            summary = format_quote_summary(updated_quote, pending_brand_dna)
            await msg.edit_text(f"Updated quote:\n\n{summary}", parse_mode="Markdown")
        return

    # ------------------------------------------------------------------
    # ACTIVE: new quote request via text or voice
    # ------------------------------------------------------------------
    if state != "ACTIVE":
        await update.message.reply_text("Please complete the setup process first.")
        return

    quote_data = None
    msg = None

    if update.message.voice:
        msg = await update.message.reply_text("Transcribing your voice note...")

        file_obj = await context.bot.get_file(update.message.voice.file_id)
        filepath = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}.ogg")
        await file_obj.download_to_drive(custom_path=filepath)

        try:
            quote_data = await asyncio.to_thread(AIService.transcribe_and_extract_voice, filepath)
        except RateLimitError:
            await msg.edit_text(RATE_LIMIT_MSG)
            return

        try:
            os.remove(filepath)
        except Exception:
            pass

        if not quote_data or not quote_data.get("line_items"):
            await msg.edit_text(
                "Sorry, I couldn't understand the voice note. Please try again or type the job details."
            )
            return

    elif update.message.text:
        msg = await update.message.reply_text("Parsing your message...")
        try:
            quote_data = await asyncio.to_thread(AIService.generate_quote_data, update.message.text)
        except RateLimitError:
            await msg.edit_text(RATE_LIMIT_MSG)
            return

        if not quote_data or not quote_data.get("line_items"):
            await msg.edit_text(
                "Sorry, I couldn't extract quote details from that. Could you be more specific?\n\n"
                "_Example: Quote for John Smith, fix leaking sink, 2 hours labour at £75/hr, £30 parts_",
                parse_mode="Markdown"
            )
            return

    else:
        return

    # Show summary and move to confirmation state
    brand_dna = await get_brand_dna(db_user["id"])
    quote_data.setdefault("currency", brand_dna.get("currency") or "USD")
    context.user_data["pending_quote"] = quote_data
    context.user_data["pending_brand_dna"] = brand_dna
    await update_user_state(user.id, "AWAITING_CONFIRMATION")

    summary = format_quote_summary(quote_data, brand_dna)
    await msg.edit_text(summary, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

def build_application():
    """Build and return the configured bot Application (without running it)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN provided.")
        return None

    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("finish_onboarding", finish_onboarding))

    # Photos and file documents
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))

    # Text and voice — fixed precedence: (TEXT | VOICE) & ~COMMAND
    application.add_handler(MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_text_or_voice))

    return application


def run_bot():
    app = build_application()
    if app:
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
