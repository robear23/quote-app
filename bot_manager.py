import asyncio
import logging
import os
import re
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import settings
import database
from ai_service import AIService, RateLimitError, run_ai, assess_docx_template_fields, assess_xlsx_mapping_fields, analyze_template_visually  # noqa: F401 (run_ai re-exported)

try:
    import sentry_sdk as _sentry
except ImportError:
    _sentry = None


def _sentry_user(db_user: dict | None):
    if _sentry and settings.SENTRY_DSN and db_user:
        _sentry.set_user({"id": db_user.get("id"), "email": db_user.get("email")})


async def run_ai_notify(func, *args, msg=None):
    """Like run_ai, but updates msg after 10s so the user knows we're still working."""
    task = asyncio.create_task(run_ai(func, *args))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
    except asyncio.TimeoutError:
        if msg:
            try:
                await msg.edit_text("The AI is taking a moment, please hold on...")
            except Exception:
                pass
        return await task

RATE_LIMIT_MSG = "The AI service is temporarily busy. Please wait a moment and try again."
from document_factory import DocumentFactory, _extract_tax_rate, SAMPLE_QUOTE_DATA

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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


async def _upload_logo(user_id: str, logo_b64: str) -> str:
    """Upload a user's logo PNG to Supabase Storage. Returns the storage path."""
    import base64 as _b64
    storage_path = f"templates/{user_id}/logo.png"
    logo_bytes = _b64.b64decode(logo_b64)
    try:
        await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).remove([storage_path])
    except Exception:
        pass
    await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).upload(
        storage_path, logo_bytes,
        file_options={"content-type": "image/png"},
    )
    return storage_path


async def _download_logo(logo_path: str) -> str | None:
    """Download a user's logo from Supabase Storage. Returns base64 string or None."""
    import base64 as _b64
    try:
        logo_bytes = await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).download(logo_path)
        return _b64.b64encode(logo_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"Could not download logo {logo_path}: {e}")
        return None


async def _upload_blank_template(user_id: str, template_bytes: bytes) -> str:
    """Upload the original blank DOCX template to Supabase Storage. Returns the storage path."""
    storage_path = f"templates/{user_id}/blank_template.docx"
    try:
        await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).remove([storage_path])
    except Exception:
        pass
    await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).upload(
        storage_path, template_bytes,
        file_options={"content-type": _DOCX_CONTENT_TYPE},
    )
    return storage_path


async def _upload_xlsx_template(user_id: str, template_bytes: bytes) -> str:
    """Upload a per-user XLSX template to Supabase Storage. Returns the storage path."""
    storage_path = f"templates/{user_id}/quote_template.xlsx"
    try:
        await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).remove([storage_path])
    except Exception:
        pass
    await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).upload(
        storage_path, template_bytes,
        file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    )
    return storage_path


async def _upload_generated_quote(user_id: str, file_path: str, filename: str) -> str:
    """Uploads a generated quote to Supabase Storage. Returns the storage path 'bucket/path'."""
    bucket = "generated-quotes"
    storage_path = f"{user_id}/{filename}"
    
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        content_type = "application/octet-stream"
        if filename.endswith(".pdf"): content_type = "application/pdf"
        elif filename.endswith(".docx"): content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.endswith(".xlsx"): content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        await database.supabase.storage.from_(bucket).upload(
            storage_path, file_bytes,
            file_options={"content-type": content_type}
        )
        return f"{bucket}/{storage_path}"
    except Exception as e:
        logger.warning(f"Failed to upload generated quote {filename} to Supabase: {e}")
        return ""



def _currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("£ GBP", callback_data="onboarding_currency_GBP"),
            InlineKeyboardButton("$ USD", callback_data="onboarding_currency_USD"),
            InlineKeyboardButton("€ EUR", callback_data="onboarding_currency_EUR"),
        ],
        [
            InlineKeyboardButton("A$ AUD", callback_data="onboarding_currency_AUD"),
            InlineKeyboardButton("R ZAR", callback_data="onboarding_currency_ZAR"),
            InlineKeyboardButton("C$ CAD", callback_data="onboarding_currency_CAD"),
        ],
        [InlineKeyboardButton("Other — type your currency code", callback_data="onboarding_currency_OTHER")],
    ])


def _template_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Looks good ✓", callback_data="template_preview_ok"),
        InlineKeyboardButton("Re-upload template", callback_data="template_preview_reupload"),
    ]])


def _format_field_report(fields: dict) -> str:
    """Returns a short field-detection summary for the template preview message."""
    labels = {
        "customer_name": "Client name",
        "customer_address": "Client address",
        "quote_ref": "Quote reference",
        "quote_date": "Date",
        "valid_until": "Expiry date",
        "line_items": "Line items table",
        "grand_total": "Total",
    }
    lines = []
    for key, label in labels.items():
        found = fields.get(key, False)
        lines.append(f"{'✓' if found else '✗'} {label}" + ("" if found else " *(not detected — will be blank)*"))
    return "\n".join(lines)


def _format_field_report_from_visual(visual: dict) -> str:
    """Builds the field detection summary from vision AI results."""
    checks = [
        ("customer_name",    "Client name"),
        ("customer_address", "Client address"),
        ("quote_ref",        "Quote reference"),
        ("quote_date",       "Date"),
        ("valid_until",      "Expiry date"),
        ("line_items_table", "Line items table"),
        ("grand_total",      "Total"),
    ]
    lines = []
    for key, label in checks:
        val = visual.get(key)
        found = bool(val)
        lines.append(f"{'✓' if found else '✗'} {label}" + ("" if found else " *(not detected)*"))
    return "\n".join(lines)


async def _save_currency_and_ask_tax(
    update: Update, _context: ContextTypes.DEFAULT_TYPE, db_user: dict, currency_code: str
) -> None:
    telegram_id = update.effective_user.id
    await database.supabase.table("user_configs").update({"currency": currency_code}).eq("user_id", db_user["id"]).execute()
    await update_user_state(telegram_id, "ONBOARDING_TAX")
    reply_fn = update.message.reply_text if update.message else update.callback_query.message.reply_text
    await reply_fn(
        f"Currency set to *{currency_code}*.\n\n"
        "What's your tax/VAT rate?\n\n"
        "• Enter a number — e.g. *20* for 20% VAT, *10* for 10% GST\n"
        "• Type *0* or *none* if you don't charge tax",
        parse_mode="Markdown"
    )


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

    # Inject logo into brand_dna for scratch generation if not already present
    if not brand_dna.get("logo_base64") and brand_dna.get("logo_path"):
        logo_b64 = await _download_logo(brand_dna["logo_path"])
        if logo_b64:
            brand_dna = {**brand_dna, "logo_base64": logo_b64}

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
            template_xlsx_path = brand_dna.get("template_xlsx_path")
            if template_xlsx_path:
                template_bytes = await _download_quote_template(template_xlsx_path)
                if template_bytes:
                    result = await asyncio.to_thread(
                        DocumentFactory.generate_from_xlsx_template, template_bytes, quote_data, brand_dna, output_filename
                    )
                else:
                    logger.warning(f"XLSX template download failed for user {db_user['id']} — falling back to scratch")
                    result = await asyncio.to_thread(DocumentFactory.generate_xlsx, quote_data, brand_dna, output_filename)
            else:
                # Legacy users who chose xlsx before template-based flow
                result = await asyncio.to_thread(DocumentFactory.generate_xlsx, quote_data, brand_dna, output_filename)
        else:
            template_path = brand_dna.get("template_docx_path")
            if not template_path:
                logger.warning(f"No template_docx_path for user {db_user['id']} — blocking generation")
                if doc_id:
                    try:
                        await database.supabase.table("documents").delete().eq("id", doc_id).execute()
                    except Exception:
                        pass
                await clear_pending_state(user.id)
                await update_user_state(user.id, "ACTIVE")
                await status_msg.edit_text(
                    "❌ No quote template found for your account.\n\n"
                    "Use /restart to re-upload your template before generating quotes."
                )
                return

            template_bytes = await _download_quote_template(template_path)
            if not template_bytes:
                logger.warning(f"template_docx_path set but download failed for user {db_user['id']}")
                if doc_id:
                    try:
                        await database.supabase.table("documents").delete().eq("id", doc_id).execute()
                    except Exception:
                        pass
                await clear_pending_state(user.id)
                await update_user_state(user.id, "ACTIVE")
                await status_msg.edit_text(
                    "❌ Couldn't load your quote template (storage error).\n\n"
                    "Use /restart to re-upload your template."
                )
                return

            result = await asyncio.to_thread(
                DocumentFactory.generate_from_template, template_bytes, quote_data, brand_dna, output_filename
            )
        doc_path = result["filepath"]
        if not os.path.exists(doc_path):
            raise RuntimeError("Generated file not found on disk")
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        if _sentry and settings.SENTRY_DSN:
            _sentry.capture_exception(e)
        if doc_id:
            try:
                await database.supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
        await status_msg.edit_text(
            "Failed to generate the document. Please try again.\n\n"
            "If this keeps happening, use /restart to re-upload your template."
        )
        return

    # Send document directly to Telegram; release reserved slot on failure
    # Send document directly to Telegram; release reserved slot on failure
    try:
        # ── PDF CONVERSION ───────────────────────────────────────────────
        pdf_path = None
        pdf_filename = os.path.splitext(output_filename)[0] + ".pdf"
        
        if not output_filename.endswith(".pdf"):
            pdf_path = await asyncio.to_thread(DocumentFactory.convert_to_pdf, doc_path)
        
        # Send the primary document
        with open(doc_path, 'rb') as f:
            await context.bot.send_document(chat_id=user.id, document=f, filename=output_filename)
        
        # Send the PDF version too if requested/available
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user.id, 
                    document=f, 
                    filename=pdf_filename,
                    caption="Here is the PDF version for easy sharing."
                )

        # ── UPLOAD FOR SHARING ───────────────────────────────────────────
        file_to_upload = pdf_path if (pdf_path and os.path.exists(pdf_path)) else doc_path
        upload_filename = pdf_filename if (pdf_path and os.path.exists(pdf_path)) else output_filename
        
        storage_url = await _upload_generated_quote(db_user["id"], file_to_upload, upload_filename)
        
    except Exception as e:
        logger.error(f"Failed to send/upload document: {e}")
        if doc_id:
            try:
                await database.supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
        await status_msg.edit_text("Failed to send the document. Please try again.")
        return
    finally:
        try:
            if os.path.exists(doc_path): os.remove(doc_path)
            if pdf_path and os.path.exists(pdf_path): os.remove(pdf_path)
        except Exception:
            pass

    share_url = f"{_settings.APP_URL}/share/{doc_id}" if doc_id else None
    reply_markup = None
    if share_url:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Share Quote (Email/Messages)", url=share_url)
        ]])

    await status_msg.edit_text(
        "Here is your generated quote!\n\n"
        "Use commands:\n"
        "/restart to re-upload your quote template\n"
        "/feedback along with a message to give us feedback and tell us what features you want added.",
        reply_markup=reply_markup
    )

    # Persist the document record: update the reserved placeholder if we have one,
    # otherwise insert a new row (fallback path when the RPC was unavailable).
    doc_fields = {
        "customer_name": quote_data.get("customer_name"),
        "customer_address": quote_data.get("customer_address"),
        "customer_email": quote_data.get("customer_email"),
        "customer_phone": quote_data.get("customer_phone"),
        "email_subject": quote_data.get("email_subject"),
        "cover_message": quote_data.get("cover_message"),
        "line_items": quote_data.get("line_items", []),
        "subtotal": result["subtotal"],
        "tax_amount": result["tax_amount"],
        "total": result["total"],
        "file_url": storage_url if storage_url else None,
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
                "Welcome! Let's set up your quote template.\n\n"
                "📄 *Quick tip before you upload:*\n\n"
                "Your template should be a blank quote with your *business info already filled in*. "
                "For client details, use labels like `[Client Name]`, `[Date]`, `[Quote Ref]` — these are picked up automatically.\n\n"
                "Send your *.docx or .xlsx* file when you're ready.",
                parse_mode="Markdown"
            )
        elif state == "ONBOARDING":
            await update.message.reply_text(
                "You're in the setup phase. Please upload your blank .docx quote template to continue."
            )
        elif state in ("ONBOARDING_CURRENCY",):
            await update.message.reply_text(
                "Please select your currency to continue setup."
            )
        elif state in ("ONBOARDING_TAX",):
            await update.message.reply_text(
                "Please enter your tax/VAT rate to continue setup (e.g. *20* for 20%, or *0* for none).",
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
                    f"Hi {user.first_name}! Account linked.\n\n"
                    "📄 *Quick tip before you upload:*\n\n"
                    "Your template should be a blank quote with your *business info already filled in*. "
                    "For client details, use labels like `[Client Name]`, `[Date]`, `[Quote Ref]` — these are picked up automatically.\n\n"
                    "Send your *.docx or .xlsx* file when you're ready.",
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

    # Delete stored templates from Supabase Storage
    try:
        paths_to_remove = [
            f"templates/{db_user['id']}/blank_template.docx",
            f"templates/{db_user['id']}/quote_template.docx",
            f"templates/{db_user['id']}/logo.png",
        ]
        await database.supabase.storage.from_(settings.SUPABASE_TEMPLATES_BUCKET).remove(paths_to_remove)
    except Exception as e:
        logger.warning(f"Failed to delete template storage files during restart (non-fatal): {e}")

    # Reset state to ONBOARDING
    await update_user_state(user.id, "ONBOARDING")

    await update.message.reply_text(
        "Your template has been reset! Let's start fresh.\n\n"
        "📄 *Quick tip before you upload:*\n\n"
        "Your template should be a blank quote with your *business info already filled in*. "
        "For client details, use labels like `[Client Name]`, `[Date]`, `[Quote Ref]` — these are picked up automatically.\n\n"
        "Send your *.docx* file when you're ready.",
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
        "/restart — Reset and re-upload your quote template\n"
        "/feedback — Send feedback to the developers\n"
        "/whoami — Check which email is linked to your account\n"
        "/redeem — Apply a promo code\n"
        "/commands — Show this list of commands",
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


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles file uploads in ONBOARDING and ACTIVE states."""
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please register first at our website.")
        return

    _sentry_user(db_user)

    state = db_user.get("bot_state")

    if state == "ONBOARDING":
        # Accept DOCX or XLSX — reject everything else
        if not update.message.document:
            await update.message.reply_text(
                "Please upload your blank quote template as a Word (.docx) or Excel (.xlsx) file."
            )
            return

        filename = update.message.document.file_name or ""
        is_docx = filename.lower().endswith(".docx")
        is_xlsx = filename.lower().endswith(".xlsx")
        if not is_docx and not is_xlsx:
            await update.message.reply_text(
                "Please upload a Word (.docx) or Excel (.xlsx) template. "
                "PDF and image templates are not supported."
            )
            return

        status_msg = await update.message.reply_text("Got it! Processing your template, just a moment...")

        tmp_ext = "docx" if is_docx else "xlsx"
        file_obj = await context.bot.get_file(update.message.document.file_id)
        tmp_path = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}.{tmp_ext}")
        await file_obj.download_to_drive(custom_path=tmp_path)

        try:
            with open(tmp_path, "rb") as f:
                template_bytes = f.read()

            if is_docx:
                # ── DOCX branch ──────────────────────────────────────────────
                try:
                    dna_data = await run_ai_notify(AIService.extract_brand_dna_from_blank, tmp_path, msg=status_msg)
                except RateLimitError:
                    await status_msg.edit_text(RATE_LIMIT_MSG)
                    return

                if not dna_data:
                    await status_msg.edit_text(
                        "Sorry, I couldn't read that template. "
                        "Please make sure it's a valid .docx file and try again."
                    )
                    return

                # Convert to PNG for inline preview + visual field analysis
                await status_msg.edit_text("Analysing your template layout...")
                png_bytes = await asyncio.to_thread(
                    DocumentFactory.convert_to_preview_png, template_bytes, "docx"
                )
                visual_hints: dict = {}
                if png_bytes:
                    try:
                        visual_hints = await run_ai(analyze_template_visually, png_bytes)
                    except Exception as e:
                        logger.warning(f"Visual field detection failed (non-fatal): {e}")

                try:
                    blank_path = await _upload_blank_template(db_user["id"], template_bytes)
                    dna_data["blank_template_path"] = blank_path
                except Exception as e:
                    logger.warning(f"Failed to upload blank template (non-fatal): {e}")

                try:
                    jinja_bytes = await run_ai(AIService.build_quote_template, tmp_path, dna_data, visual_hints)
                except RateLimitError:
                    await status_msg.edit_text(RATE_LIMIT_MSG)
                    return
                except Exception as e:
                    logger.error(f"Template building failed: {e}")
                    jinja_bytes = None

                if not jinja_bytes:
                    await status_msg.edit_text(
                        "❌ I couldn't set up your template for auto-fill.\n\n"
                        "Make sure your template has clear column headers (Description, Qty, Price, Total) "
                        "and labeled fields for client name and date.\n\n"
                        "Please upload a corrected .docx template to continue."
                    )
                    return

                try:
                    tpl_path = await _upload_quote_template(db_user["id"], jinja_bytes)
                except Exception as e:
                    logger.error(f"Failed to upload mapped template: {e}")
                    await status_msg.edit_text(
                        "❌ Failed to save your template (storage error). Please try again."
                    )
                    return

                dna_data["template_docx_path"] = tpl_path
                dna_data["preferred_format"] = "docx"
                logger.info(f"Jinja2 template stored at {tpl_path} for user {db_user['id']}")

                logo_b64 = dna_data.pop("logo_base64", None)
                if logo_b64:
                    try:
                        logo_path = await _upload_logo(db_user["id"], logo_b64)
                        dna_data["logo_path"] = logo_path
                    except Exception as e:
                        logger.warning(f"Failed to upload logo (non-fatal): {e}")

                # Build field report — prefer vision results, fall back to XML scan
                if visual_hints:
                    field_report = _format_field_report_from_visual(visual_hints)
                else:
                    field_report = _format_field_report(assess_docx_template_fields(jinja_bytes))

                # Send preview — PNG inline photo if available, else fallback to docx file
                preview_sent = False
                if png_bytes:
                    try:
                        await status_msg.edit_text(
                            "✅ *Template saved!*\n\n"
                            "Here's a preview image of your template — I've detected the fields below that will be filled in automatically when you generate quotes "
                            "(your actual quotes will be sent as editable Word files):\n\n"
                            + field_report,
                            parse_mode="Markdown"
                        )
                        await update.message.reply_photo(
                            photo=png_bytes,
                            caption="Your quote template"
                        )
                        preview_sent = True
                    except Exception as e:
                        logger.warning(f"PNG preview send failed (non-fatal): {e}")

                if not preview_sent:
                    # Fallback: generate filled docx preview
                    try:
                        preview_filename = f"Preview_{uuid.uuid4().hex[:8]}.docx"
                        preview_result = await asyncio.to_thread(
                            DocumentFactory.generate_from_template, jinja_bytes, SAMPLE_QUOTE_DATA, dna_data, preview_filename
                        )
                        preview_path = preview_result["filepath"]
                        await status_msg.edit_text(
                            "✅ *Template saved!* Here's a sample quote using your template:\n\n" + field_report,
                            parse_mode="Markdown"
                        )
                        with open(preview_path, "rb") as f:
                            await update.message.reply_document(document=f, filename="Preview.docx")
                        os.remove(preview_path)
                        preview_sent = True
                    except Exception as e:
                        logger.warning(f"DOCX preview generation failed (non-fatal): {e}")

                if preview_sent:
                    await update.message.reply_text(
                        "Does this look right? Confirm to continue, or re-upload if anything's off.\n\n"
                        "_Note: actual quotes you generate will be sent as editable .docx files._",
                        parse_mode="Markdown",
                        reply_markup=_template_preview_keyboard()
                    )
                else:
                    # All preview attempts failed — skip straight to currency
                    dna_data["user_id"] = db_user["id"]
                    await database.supabase.table("user_configs").upsert(dna_data).execute()
                    await update_user_state(user.id, "ONBOARDING_CURRENCY")
                    await status_msg.edit_text(
                        "Template saved!\n\n"
                        "What currency do you use for your quotes?\n\n"
                        "Select from the options below, or type the 3-letter code (e.g. NZD, CHF, AED).",
                        reply_markup=_currency_keyboard()
                    )
                    return  # skip the shared upsert/state update below

            else:
                # ── XLSX branch ──────────────────────────────────────────────
                try:
                    dna_data = await run_ai_notify(AIService.extract_brand_dna_from_xlsx, tmp_path, msg=status_msg)
                except RateLimitError:
                    await status_msg.edit_text(RATE_LIMIT_MSG)
                    return

                if not dna_data:
                    await status_msg.edit_text(
                        "Sorry, I couldn't read that template. "
                        "Please make sure it's a valid .xlsx file and try again."
                    )
                    return

                # Convert to PNG for inline preview + visual field analysis
                await status_msg.edit_text("Analysing your template layout...")
                png_bytes = await asyncio.to_thread(
                    DocumentFactory.convert_to_preview_png, template_bytes, "xlsx"
                )
                visual_hints: dict = {}
                if png_bytes:
                    try:
                        visual_hints = await run_ai(analyze_template_visually, png_bytes)
                    except Exception as e:
                        logger.warning(f"Visual field detection failed (non-fatal): {e}")

                try:
                    mapping = await run_ai(AIService.build_xlsx_field_mapping, tmp_path, dna_data, visual_hints)
                except RateLimitError:
                    await status_msg.edit_text(RATE_LIMIT_MSG)
                    return
                except Exception as e:
                    logger.error(f"XLSX field mapping failed: {e}")
                    mapping = None

                if not mapping:
                    await status_msg.edit_text(
                        "❌ I couldn't map your Excel template for auto-fill.\n\n"
                        "Make sure your template has clear column headers (Description, Qty, Price, Total) "
                        "and labeled cells for client name and date.\n\n"
                        "Please upload a corrected .xlsx template to continue."
                    )
                    return

                try:
                    tpl_path = await _upload_xlsx_template(db_user["id"], template_bytes)
                except Exception as e:
                    logger.error(f"Failed to upload XLSX template: {e}")
                    await status_msg.edit_text(
                        "❌ Failed to save your template (storage error). Please try again."
                    )
                    return

                dna_data["template_xlsx_path"] = tpl_path
                dna_data["xlsx_field_mapping"] = mapping
                dna_data["preferred_format"] = "xlsx"
                logger.info(f"XLSX template stored at {tpl_path} for user {db_user['id']}")

                # Build field report — prefer vision results, fall back to mapping scan
                if visual_hints:
                    field_report = _format_field_report_from_visual(visual_hints)
                else:
                    field_report = _format_field_report(assess_xlsx_mapping_fields(mapping))

                # Send preview — PNG inline photo if available, else fallback to xlsx file
                preview_sent = False
                if png_bytes:
                    try:
                        await status_msg.edit_text(
                            "✅ *Template saved!*\n\n"
                            "Here's a preview image of your template — I've detected the fields below that will be filled in automatically when you generate quotes "
                            "(your actual quotes will be sent as editable Excel files):\n\n"
                            + field_report,
                            parse_mode="Markdown"
                        )
                        await update.message.reply_photo(
                            photo=png_bytes,
                            caption="Your quote template"
                        )
                        preview_sent = True
                    except Exception as e:
                        logger.warning(f"PNG preview send failed (non-fatal): {e}")

                if not preview_sent:
                    # Fallback: generate filled xlsx preview
                    try:
                        preview_filename = f"Preview_{uuid.uuid4().hex[:8]}.xlsx"
                        preview_result = await asyncio.to_thread(
                            DocumentFactory.generate_from_xlsx_template, template_bytes, SAMPLE_QUOTE_DATA, dna_data, preview_filename
                        )
                        preview_path = preview_result["filepath"]
                        await status_msg.edit_text(
                            "✅ *Template saved!* Here's a sample quote using your template:\n\n" + field_report,
                            parse_mode="Markdown"
                        )
                        with open(preview_path, "rb") as f:
                            await update.message.reply_document(document=f, filename="Preview.xlsx")
                        os.remove(preview_path)
                        preview_sent = True
                    except Exception as e:
                        logger.warning(f"XLSX preview generation failed (non-fatal): {e}")

                if preview_sent:
                    await update.message.reply_text(
                        "Does this look right? Confirm to continue, or re-upload if anything's off.\n\n"
                        "_Note: actual quotes you generate will be sent as editable .xlsx files._",
                        parse_mode="Markdown",
                        reply_markup=_template_preview_keyboard()
                    )
                else:
                    dna_data["user_id"] = db_user["id"]
                    await database.supabase.table("user_configs").upsert(dna_data).execute()
                    await update_user_state(user.id, "ONBOARDING_CURRENCY")
                    await status_msg.edit_text(
                        "Template saved!\n\n"
                        "What currency do you use for your quotes?\n\n"
                        "Select from the options below, or type the 3-letter code (e.g. NZD, CHF, AED).",
                        reply_markup=_currency_keyboard()
                    )
                    return  # skip the shared upsert/state update below

            # Persist brand DNA (currency/tax come from Q&A after preview confirmation)
            dna_data["user_id"] = db_user["id"]
            await database.supabase.table("user_configs").upsert(dna_data).execute()
            # State stays ONBOARDING — handle_template_preview_ok advances it to ONBOARDING_CURRENCY

        except Exception as e:
            logger.error(f"Error during template onboarding: {e}", exc_info=True)
            await status_msg.edit_text(
                "Something went wrong processing your template. Please try again."
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    elif state in ("ONBOARDING_CURRENCY", "ONBOARDING_TAX"):
        await update.message.reply_text(
            "Please answer the setup question above before uploading files."
        )

    elif state == "ACTIVE":
        if update.message.photo:
            msg = await update.message.reply_text("Analysing your photo to extract quote details...")

            try:
                file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
                filepath = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}.jpg")
                await file_obj.download_to_drive(custom_path=filepath)
            except Exception as e:
                logger.error(f"Failed to download photo from Telegram: {e}")
                await msg.edit_text("Sorry, I couldn't download your photo. Please try again.")
                return

            brand_dna = await get_brand_dna(db_user["id"])
            try:
                quote_data = await run_ai_notify(AIService.extract_quote_from_image, filepath, msg=msg)
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

    _sentry_user(db_user)
    state = db_user.get("bot_state")

    # ------------------------------------------------------------------
    # ONBOARDING_CURRENCY: user is choosing their invoice currency
    # ------------------------------------------------------------------
    if state == "ONBOARDING_CURRENCY":
        text = (update.message.text or "").strip().upper()
        currency_aliases = {
            "GBP": "GBP", "£": "GBP", "POUNDS": "GBP", "STERLING": "GBP",
            "USD": "USD", "$": "USD", "DOLLARS": "USD",
            "EUR": "EUR", "€": "EUR", "EUROS": "EUR",
            "AUD": "AUD", "A$": "AUD", "AU$": "AUD",
            "CAD": "CAD", "C$": "CAD",
            "ZAR": "ZAR", "RAND": "ZAR",
        }
        chosen = currency_aliases.get(text)
        if not chosen:
            # Accept any 2-5 char uppercase string as a custom currency code
            import re as _re
            if _re.fullmatch(r'[A-Z]{2,5}', text):
                chosen = text
        if chosen:
            await _save_currency_and_ask_tax(update, context, db_user, chosen)
        else:
            await update.message.reply_text(
                "Please press one of the currency buttons, or type the 3-letter code (e.g. *GBP*, *USD*, *NZD*).",
                parse_mode="Markdown"
            )
        return

    # ------------------------------------------------------------------
    # ONBOARDING_TAX: user is entering their tax/VAT rate
    # ------------------------------------------------------------------
    if state == "ONBOARDING_TAX":
        text = (update.message.text or "").strip().lower()
        tax_rate = None

        if text in ("0", "none", "no", "no tax", "0%", "n/a", "nil", "exempt"):
            tax_rate = 0.0
        else:
            cleaned = text.rstrip('%').strip()
            try:
                val = float(cleaned)
                if 0 <= val <= 100:
                    tax_rate = val
            except ValueError:
                pass

        if tax_rate is None:
            await update.message.reply_text(
                "Please enter a number between 0 and 100 (e.g. *20* for 20% VAT), "
                "or type *none* if you don't charge tax.",
                parse_mode="Markdown"
            )
            return

        vat_status = "No tax" if tax_rate == 0 else f"Tax {tax_rate:.0f}%"
        calc_methods = {"tax_rate": tax_rate}
        try:
            await database.supabase.table("user_configs").update({
                "vat_tax_status": vat_status,
                "calculation_methods": calc_methods,
            }).eq("user_id", db_user["id"]).execute()
            await update_user_state(user.id, "ACTIVE")
            await update.message.reply_text(
                f"Tax rate set to *{tax_rate:.0f}%*.\n\n"
                "✅ You're all set! Send me a voice note, photo, or type the job details to generate your first quote.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to save tax rate: {e}")
            await update.message.reply_text("Failed to save your tax rate. Please try again.")
        return

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
            result = await run_ai_notify(AIService.refine_quote, pending_quote, update.message.text or "", msg=msg)
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
            quote_data = await run_ai_notify(AIService.transcribe_and_extract_voice, filepath, msg=msg)
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
            quote_data = await run_ai_notify(AIService.generate_quote_data, update.message.text, msg=msg)
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

    _sentry_user(db_user)
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


async def handle_onboarding_currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle currency selection inline button presses during onboarding."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    db_user = await get_user(user.id)
    if not db_user or db_user.get("bot_state") != "ONBOARDING_CURRENCY":
        return

    currency_code = query.data.replace("onboarding_currency_", "")

    if currency_code == "OTHER":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text(
            "Please type your currency as a 3-letter code (e.g. *NZD* for New Zealand Dollar, *CHF* for Swiss Franc).",
            parse_mode="Markdown"
        )
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _save_currency_and_ask_tax(update, context, db_user, currency_code)


async def handle_template_preview_ok(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """User confirmed the template preview looks good — proceed to currency selection."""
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    db_user = await get_user(query.from_user.id)
    if not db_user or db_user.get("bot_state") != "ONBOARDING":
        return
    await update_user_state(query.from_user.id, "ONBOARDING_CURRENCY")
    await query.message.reply_text(
        "What currency do you use for your quotes?\n\n"
        "Select from the options below, or type the 3-letter code (e.g. NZD, CHF, AED).",
        reply_markup=_currency_keyboard()
    )


async def handle_template_preview_reupload(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """User wants to fix their template — stay in ONBOARDING and prompt re-upload."""
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    db_user = await get_user(query.from_user.id)
    if not db_user or db_user.get("bot_state") != "ONBOARDING":
        return
    await query.message.reply_text(
        "No problem — please upload a revised template.\n\n"
        "💡 *Tips for best results:*\n"
        "• Add labels like `Bill To:`, `Date:`, `Quote Ref:` next to the relevant fields\n"
        "• Make sure your line items table has column headers (Description, Qty, Price, Total)\n"
        "• You can also use `[Client Name]`, `[Date]`, `[Quote Ref]` as explicit placeholders",
        parse_mode="Markdown"
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
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("feedback", feedback))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("commands", commands))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CallbackQueryHandler(handle_confirm_yes, pattern="^confirm_yes$"))
    application.add_handler(CallbackQueryHandler(handle_onboarding_currency_callback, pattern="^onboarding_currency_"))
    application.add_handler(CallbackQueryHandler(handle_template_preview_ok, pattern="^template_preview_ok$"))
    application.add_handler(CallbackQueryHandler(handle_template_preview_reupload, pattern="^template_preview_reupload$"))

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
