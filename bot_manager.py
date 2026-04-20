import asyncio
import logging
import os
import re
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import settings
import database
from ai_service import AIService, RateLimitError, run_ai

RATE_LIMIT_MSG = "I'm a bit overwhelmed right now — please try again in a minute."
from document_factory import DocumentFactory, _extract_tax_rate

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

_ONBOARDING_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Supabase Storage helpers for onboarding sample files
# ---------------------------------------------------------------------------

async def _upload_onboarding_file(telegram_id: int, filename: str, file_bytes: bytes) -> str:
    """Upload a sample file to Supabase Storage. Returns the storage path."""
    storage_path = f"onboarding/{telegram_id}/{filename}"
    ext = os.path.splitext(filename)[1].lower()
    ct = _ONBOARDING_CONTENT_TYPES.get(ext, "application/octet-stream")
    await database.supabase.storage.from_(settings.SUPABASE_ONBOARDING_BUCKET).upload(
        storage_path, file_bytes, file_options={"content-type": ct}
    )
    return storage_path


async def _list_onboarding_storage_paths(telegram_id: int) -> list[str]:
    """List all onboarding files in Supabase Storage for a user. Returns storage paths."""
    folder = f"onboarding/{telegram_id}"
    items = await database.supabase.storage.from_(settings.SUPABASE_ONBOARDING_BUCKET).list(folder)
    return [
        f"{folder}/{item['name']}"
        for item in (items or [])
        if item.get("name") and not item["name"].startswith(".")
    ]


async def _delete_onboarding_storage_files(telegram_id: int) -> None:
    """Delete all onboarding files from Supabase Storage for a user."""
    paths = await _list_onboarding_storage_paths(telegram_id)
    if paths:
        await database.supabase.storage.from_(settings.SUPABASE_ONBOARDING_BUCKET).remove(paths)


async def _upload_quote_template(user_id: str, template_bytes: bytes) -> str:
    """Upload a per-user docxtpl template to Supabase Storage. Returns the storage path."""
    storage_path = f"templates/{user_id}/quote_template.docx"
    try:
        await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).remove([storage_path])
    except Exception:
        pass
    await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).upload(
        storage_path, template_bytes,
        file_options={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    )
    return storage_path


async def _download_quote_template(template_path: str) -> bytes | None:
    """Download a user's docxtpl template from Supabase Storage. Returns bytes or None."""
    try:
        return await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).download(template_path)
    except Exception as e:
        logger.warning(f"Could not download quote template {template_path}: {e}")
        return None


async def _download_onboarding_files_to_temp(paths: list[str]) -> list[str]:
    """Download storage files to local temp dir for AI processing. Returns local temp paths."""
    local_paths = []
    for storage_path in paths:
        try:
            file_bytes = await database.supabase.storage.from_(settings.SUPABASE_ONBOARDING_BUCKET).download(storage_path)
            filename = storage_path.split("/")[-1]
            local_path = os.path.join(TEMP_DIR, f"onboarding_{uuid.uuid4().hex}_{filename}")
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            logger.info(f"Downloaded onboarding file {filename}: {len(file_bytes)} bytes -> {local_path}")
            local_paths.append(local_path)
        except Exception as e:
            logger.error(f"Failed to download onboarding file {storage_path}: {e}", exc_info=True)
    return local_paths


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def update_user_state(telegram_id: int, state: str):
    """Updates the user's bot_state in Supabase."""
    await database.supabase.table("users").update({"bot_state": state}).eq("telegram_id", telegram_id).execute()


async def get_user(telegram_id: int):
    """Retrieves user by telegram_id."""
    res = await database.supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None


async def get_brand_dna(user_id: str) -> dict:
    """Retrieves the user's Brand DNA config from Supabase."""
    res = await database.supabase.table("user_configs").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else {}


async def set_pending_state(telegram_id: int, quote_data: dict, brand_dna: dict):
    """Persists pending quote and brand DNA to Supabase (survives restarts and multi-worker deploys)."""
    await database.supabase.table("users").update({
        "pending_quote": quote_data,
        "pending_brand_dna": brand_dna,
    }).eq("telegram_id", telegram_id).execute()


async def clear_pending_state(telegram_id: int):
    """Clears the pending quote state after generation or cancellation."""
    await database.supabase.table("users").update({
        "pending_quote": None,
        "pending_brand_dna": None,
    }).eq("telegram_id", telegram_id).execute()


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

    lines.append("\nDoes this look right? Press *YES* or tell me what to change.")
    return "\n".join(lines)


def _yes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("YES ✓", callback_data="confirm_yes")]])


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
    """Generates the quote document, uploads to Supabase Storage, sends via URL, and cleans up."""
    user = update.effective_user

    # Atomically check quota and reserve a document slot via Postgres RPC.
    # reserve_quota_slot() uses an advisory lock so two simultaneous requests
    # for the same user cannot both slip through the count check.
    from subscription_service import get_user_tier, monthly_limit_for_tier, get_billing_period_start, get_active_extra_quotes_limit
    from config import settings as _settings
    tier = await get_user_tier(db_user["id"])
    monthly_limit = monthly_limit_for_tier(tier)
    if tier == "free":
        promo_limit = await get_active_extra_quotes_limit(db_user["id"])
        if promo_limit is not None:
            monthly_limit = promo_limit
    billing_start = await get_billing_period_start(db_user["id"])

    doc_id = None
    quota_exceeded = False
    try:
        rpc_res = await database.supabase.rpc("reserve_quota_slot", {
            "p_user_id": db_user["id"],
            "p_billing_start": billing_start.isoformat(),
            "p_limit": monthly_limit,
        }).execute()
        doc_id = rpc_res.data  # UUID string if slot reserved, None if quota exceeded
        quota_exceeded = (doc_id is None)
    except Exception as e:
        # RPC unavailable (e.g. migration not yet run) — fall back to a non-atomic
        # count check so existing users are not blocked during the migration window.
        logger.warning(f"reserve_quota_slot RPC failed, falling back to count check: {e}")
        from subscription_service import get_monthly_usage
        monthly_count = await get_monthly_usage(db_user["id"])
        quota_exceeded = monthly_count >= monthly_limit

    if quota_exceeded:
        account_url = f"{_settings.APP_URL}/account"
        if tier == "free":
            msg_text = (
                f"You've used all {monthly_limit} free quotes this month.\n\n"
                f"Upgrade to Premium for 100 quotes/month at:\n{account_url}"
            )
        else:
            msg_text = (
                f"You've reached your Premium limit of {monthly_limit} quotes this month. "
                "Resets on the 1st of next month."
            )
        if status_msg:
            await status_msg.edit_text(msg_text)
        else:
            await update.message.reply_text(msg_text)
        await clear_pending_state(user.id)
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
        total_res = await database.supabase.table("documents").select("id", count="exact").eq("user_id", db_user["id"]).execute()
        quote_num = (total_res.count or 0)
    except Exception:
        quote_num = 1
    unique_id = uuid.uuid4().hex[:6]
    output_filename = f"Quote_{surname}_{quote_num:03d}_{unique_id}.{output_ext}"

    # Generate the document; release the reserved slot on any failure
    result = None
    doc_path = None
    try:
        if preferred_format == "xlsx":
            result = await asyncio.to_thread(DocumentFactory.generate_xlsx, quote_data, brand_dna, output_filename)
        else:
            template_path = brand_dna.get("template_docx_path")
            template_bytes = await _download_quote_template(template_path) if template_path else None
            if template_bytes:
                result = await asyncio.to_thread(
                    DocumentFactory.generate_from_template, template_bytes, quote_data, brand_dna, output_filename
                )
            else:
                result = await asyncio.to_thread(DocumentFactory.generate_docx, quote_data, brand_dna, output_filename)
        doc_path = result["filepath"]
        if not os.path.exists(doc_path):
            raise RuntimeError("Generated file not found on disk")
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        if doc_id:
            try:
                await database.supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
        await status_msg.edit_text("Failed to generate the document. Please try again.")
        return

    # Send document directly to Telegram; release reserved slot on failure
    try:
        with open(doc_path, 'rb') as f:
            await context.bot.send_document(chat_id=user.id, document=f, filename=output_filename)
    except Exception as e:
        logger.error(f"Failed to send document to Telegram: {e}")
        if doc_id:
            try:
                await database.supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
        await status_msg.edit_text("Failed to send the document. Please try again.")
        return
    finally:
        try:
            os.remove(doc_path)
        except Exception:
            pass

    await status_msg.edit_text(
        "Here is your generated quote!\n\n"
        "Use commands:\n"
        "/restart to change your uploaded quote DNA documents\n"
        "/feedback along with a message to give us feedback and tell us what features you want added."
    )

    # Persist the document record: update the reserved placeholder if we have one,
    # otherwise insert a new row (fallback path when the RPC was unavailable).
    doc_fields = {
        "customer_name": quote_data.get("customer_name"),
        "customer_address": quote_data.get("customer_address"),
        "line_items": quote_data.get("line_items", []),
        "subtotal": result["subtotal"],
        "tax_amount": result["tax_amount"],
        "total": result["total"],
    }
    try:
        if doc_id:
            await database.supabase.table("documents").update(doc_fields).eq("id", doc_id).execute()
        else:
            await database.supabase.table("documents").insert({"user_id": db_user["id"], **doc_fields}).execute()
        logger.info(f"Document recorded for user {db_user['id']} (telegram_id={user.id})")
    except Exception as e:
        logger.error(f"Failed to persist document record for user {db_user['id']}: {e}")

    # Clear pending state and return user to ACTIVE
    await clear_pending_state(user.id)
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
            res = await database.supabase.table("users").select("*").eq("id", payload).execute()
            if res.data:
                await database.supabase.table("users").update({
                    "telegram_id": user.id,
                    "bot_state": "ONBOARDING"
                }).eq("id", payload).execute()
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


async def restart(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets the user back to ONBOARDING so they can re-upload Brand DNA documents."""
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    # Delete existing Brand DNA config
    try:
        await database.supabase.table("user_configs").delete().eq("user_id", db_user["id"]).execute()
    except Exception as e:
        logger.error(f"Failed to delete user_configs during restart: {e}")

    # Delete any uploaded onboarding samples from Supabase Storage
    try:
        await _delete_onboarding_storage_files(user.id)
    except Exception as e:
        logger.error(f"Failed to delete onboarding storage files during restart: {e}")

    # Reset state to ONBOARDING
    await update_user_state(user.id, "ONBOARDING")

    await update.message.reply_text(
        "Your Brand DNA has been reset! Let's start fresh.\n\n"
        "Please upload 3–10 past invoices or quotes (PDF/Image). "
        "Type /finish\\_onboarding when you're done.",
        parse_mode="Markdown"
    )


async def feedback(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stores user feedback in the Supabase feedback table."""
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    # Extract the feedback message (everything after /feedback)
    message_text = (update.message.text or "").strip()
    if message_text.lower().startswith("/feedback"):
        feedback_text = message_text[len("/feedback"):].strip()
    else:
        feedback_text = ""

    if not feedback_text:
        await update.message.reply_text(
            "Please include your feedback message after the command.\n\n"
            "_Example: /feedback I love it but could you include invoices too?!?_",
            parse_mode="Markdown"
        )
        return

    try:
        await database.supabase.table("feedback").insert({
            "user_id": db_user["id"],
            "telegram_id": user.id,
            "email": db_user.get("email"),
            "message": feedback_text,
        }).execute()
        await update.message.reply_text(
            "Thanks for your feedback! The developers will be in touch via email shortly."
        )
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}")
        await update.message.reply_text("Sorry, something went wrong saving your feedback. Please try again.")


async def whoami(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with the email linked to this Telegram account."""
    user = update.effective_user
    db_user = await get_user(user.id)
    if not db_user:
        await update.message.reply_text("No account found for this Telegram ID. Please register on the website first.")
        return
    email = db_user.get("email") or "(no email linked)"
    await update.message.reply_text(f"Your linked email: *{email}*", parse_mode="Markdown")


async def commands(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all available bot commands."""
    await update.message.reply_text(
        "📋 *Available Commands*\n\n"
        "/start — Link your account and get started\n"
        "/restart — Re-upload your quote DNA documents\n"
        "/feedback — Send feedback to the developers\n"
        "/whoami — Check which email is linked to your account\n"
        "/redeem — Apply a promo code\n"
        "/commands — Show this list of commands\n"
        "/finish\\_onboarding — Complete the onboarding process after uploading samples",
        parse_mode="Markdown"
    )


async def redeem(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redeems a promo code for the user."""
    user = update.effective_user
    db_user = await get_user(user.id)
    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    text = (update.message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Usage: /redeem YOUR\\_CODE", parse_mode="Markdown")
        return

    code = parts[1].strip()
    from subscription_service import redeem_promo_code
    result = await redeem_promo_code(db_user["id"], code)
    if result["success"]:
        await update.message.reply_text(result["message"])
    else:
        await update.message.reply_text(f"Could not apply code: {result['error']}")


async def finish_onboarding(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user or db_user.get("bot_state") != "ONBOARDING":
        await update.message.reply_text("You are not currently in the onboarding phase.")
        return

    # List files uploaded to Supabase Storage for this user
    try:
        storage_paths = await _list_onboarding_storage_paths(user.id)
    except Exception as e:
        logger.error(f"Failed to list onboarding storage files: {e}")
        await update.message.reply_text("Failed to load your uploaded files. Please try again.")
        return

    if len(storage_paths) < 1:
        await update.message.reply_text("Please upload at least 1 sample invoice before finishing.")
        return

    msg = await update.message.reply_text(
        f"Processing {len(storage_paths)} document(s) to extract your Brand DNA. This might take a minute..."
    )

    # Download storage files to temp dir for AI processing
    local_files = await _download_onboarding_files_to_temp(storage_paths)
    if not local_files:
        await msg.edit_text("Failed to load your uploaded files. Please try again.")
        return

    template_bytes = None
    try:
        dna_data = await run_ai(AIService.extract_brand_dna, local_files)

        # Build docxtpl template from the first DOCX sample (non-blocking)
        docx_files = [f for f in local_files if f.lower().endswith(".docx")]
        if docx_files and dna_data:
            try:
                template_bytes = await run_ai(AIService.build_quote_template, docx_files[0], dna_data)
            except Exception as e:
                logger.warning(f"Template building failed (non-fatal): {e}")

    except RateLimitError:
        await msg.edit_text(RATE_LIMIT_MSG)
        return
    finally:
        # Always clean up temp files
        for f in local_files:
            try:
                os.remove(f)
            except Exception:
                pass

    if not dna_data:
        await msg.edit_text(
            "Sorry, the AI service is temporarily unavailable. Please try /finish\\_onboarding again in a moment.",
            parse_mode="Markdown"
        )
        return

    # Upload docxtpl template to Supabase Storage and record the path
    if template_bytes:
        try:
            template_path = await _upload_quote_template(db_user["id"], template_bytes)
            dna_data["template_docx_path"] = template_path
            logger.info(f"Quote template stored at {template_path} for user {db_user['id']}")
        except Exception as e:
            logger.warning(f"Failed to upload quote template (non-fatal): {e}")

    dna_data["user_id"] = db_user["id"]
    try:
        await database.supabase.table("user_configs").upsert(dna_data).execute()

        # Delete onboarding samples from Supabase Storage
        try:
            await database.supabase.storage.from_(settings.SUPABASE_ONBOARDING_BUCKET).remove(storage_paths)
        except Exception as e:
            logger.error(f"Failed to delete onboarding storage files after processing: {e}")

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
            # Download from Telegram to a temp file, then upload to Supabase Storage
            tmp_path = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}{ext}")
            await file_obj.download_to_drive(custom_path=tmp_path)
            try:
                storage_filename = f"{uuid.uuid4().hex}{ext}"
                with open(tmp_path, "rb") as f:
                    file_bytes = f.read()
                await _upload_onboarding_file(user.id, storage_filename, file_bytes)
            except Exception as e:
                logger.error(f"Failed to upload onboarding file to storage: {e}")
                await update.message.reply_text("Failed to save your file. Please try again.")
                return
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            # Count files now in storage so the user knows their running total
            try:
                stored = await _list_onboarding_storage_paths(user.id)
                count = len(stored)
            except Exception:
                count = 1

            await update.message.reply_text(
                f"Received sample {count}. "
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
                quote_data = await run_ai(AIService.extract_quote_from_image, filepath)
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
            await set_pending_state(user.id, quote_data, brand_dna)
            await update_user_state(user.id, "AWAITING_CONFIRMATION")

            summary = format_quote_summary(quote_data, brand_dna)
            await msg.edit_text(summary, parse_mode="Markdown", reply_markup=_yes_keyboard())
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
            await database.supabase.table("user_configs").update({"preferred_format": chosen_format}).eq("user_id", db_user["id"]).execute()
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

        pending_quote = db_user.get("pending_quote")
        pending_brand_dna = db_user.get("pending_brand_dna")

        if not pending_quote:
            # State lost on restart — reset gracefully
            await update_user_state(user.id, "ACTIVE")
            await update.message.reply_text(
                "Sorry, I lost track of the pending quote (likely a restart). Please send the job details again."
            )
            return

        msg = await update.message.reply_text("Checking your response...")
        try:
            result = await run_ai(AIService.refine_quote, pending_quote, update.message.text or "")
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
            await set_pending_state(user.id, updated_quote, pending_brand_dna)
            summary = format_quote_summary(updated_quote, pending_brand_dna)
            await msg.edit_text(f"Updated quote:\n\n{summary}", parse_mode="Markdown", reply_markup=_yes_keyboard())
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
            quote_data = await run_ai(AIService.transcribe_and_extract_voice, filepath)
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
            quote_data = await run_ai(AIService.generate_quote_data, update.message.text)
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
    await set_pending_state(user.id, quote_data, brand_dna)
    await update_user_state(user.id, "AWAITING_CONFIRMATION")

    summary = format_quote_summary(quote_data, brand_dna)
    await msg.edit_text(summary, parse_mode="Markdown", reply_markup=_yes_keyboard())


# ---------------------------------------------------------------------------
# Inline button callbacks
# ---------------------------------------------------------------------------

async def handle_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the YES ✓ inline button press — treat it as a typed YES confirmation."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    db_user = await get_user(user.id)
    if not db_user:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    pending_quote = db_user.get("pending_quote")
    pending_brand_dna = db_user.get("pending_brand_dna")

    if not pending_quote:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Sorry, I lost track of the pending quote (likely a restart). Please send the job details again."
        )
        return

    # Remove the button so it can't be pressed twice
    await query.edit_message_reply_markup(reply_markup=None)

    msg = await query.message.reply_text("Generating your document...")
    await generate_and_send_quote(
        update, context, db_user,
        pending_quote,
        pending_brand_dna,
        status_msg=msg,
    )


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

def build_application():
    """Build and return the configured bot Application (without running it)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN provided.")
        return None

    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .updater(None)  # webhooks only — no polling updater needed
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("finish_onboarding", finish_onboarding))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("feedback", feedback))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("commands", commands))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CallbackQueryHandler(handle_confirm_yes, pattern="^confirm_yes$"))

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
