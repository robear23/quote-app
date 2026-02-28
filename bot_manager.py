import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from config import settings
from database import supabase
from ai_service import AIService
import os

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# In-memory store for files uploaded during ONBOARDING
# Dict mapping telegram_id -> list of local file paths
onboarding_files = {}

# Restore any files left in the temp directory from previous sessions
import glob
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

async def update_user_state(telegram_id: int, state: str):
    """Updates the user's bot_state in Supabase."""
    supabase.table("users").update({"bot_state": state}).eq("telegram_id", telegram_id).execute()

async def get_user(telegram_id: int):
    """Retrieves user by telegram_id."""
    res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    payload = context.args[0] if context.args else None
    
    # Check if user already linked
    existing_user = await get_user(user.id)
    
    if existing_user:
        state = existing_user.get("bot_state")
        if state == "HANDSHAKE":
            # Just linked
            await update_user_state(user.id, "ONBOARDING")
            await update.message.reply_text("Welcome back! Let's get started. Please send me 3-10 examples of your past quotes or invoices (PDF or Images). When you're done, type /finish_onboarding.")
        elif state == "ONBOARDING":
             await update.message.reply_text("You are currently setting up your Brand DNA. Please upload sample quotes/invoices or type /finish_onboarding.")
        elif state == "ACTIVE":
             await update.message.reply_text("Your account is active. Send me audio, text, or a photo to generate a new quote!")
        return

    # First time linking via deep link payload (which is the UUID from Web)
    if payload:
        try:
            # Look up the web-created user by UUID
            res = supabase.table("users").select("*").eq("id", payload).execute()
            if res.data:
                # Link telegram_id to this user
                supabase.table("users").update({
                    "telegram_id": user.id,
                    "bot_state": "ONBOARDING"
                }).eq("id", payload).execute()
                await update.message.reply_text(f"Hi {user.first_name}! Account linked. Let's learn your Brand DNA. Please upload 3 to 10 past invoices or quotes (PDF/Image). Type /finish_onboarding when done.")
            else:
                await update.message.reply_text("Invalid registration link. Please register on the website first.")
        except Exception as e:
            logger.error(f"Error during linking: {e}")
            await update.message.reply_text("An error occurred linking your account.")
    else:
        await update.message.reply_text("Hi! Please visit our website to register before using the bot.")

async def finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_user(user.id)
    
    if not db_user or db_user.get("bot_state") != "ONBOARDING":
        await update.message.reply_text("You are not currently in the onboarding phase.")
        return
        
    files = onboarding_files.get(user.id, [])
    if len(files) < 1: # Require at least 1 for testing, ideally 3+
        await update.message.reply_text("Please upload at least 1 sample invoice before finishing.")
        return
        
    await update.message.reply_text(f"Processing {len(files)} documents to extract your Brand DNA. This might take a minute...")
    
    # 1. Trigger Gemini Extraction
    dna_data = AIService.extract_brand_dna(files)
    
    if not dna_data:
        await update.message.reply_text("Sorry, I couldn't extract your details. Please try uploading clearer images/PDFs.")
        return
        
    # 2. Save to User Configs
    dna_data["user_id"] = db_user["id"]
    try:
        supabase.table("user_configs").upsert(dna_data).execute()
        
        # 3. Transition to ACTIVE
        await update_user_state(user.id, "ACTIVE")
        
        # Cleanup temporary files
        for f in files:
            if os.path.exists(f):
                os.remove(f)
        onboarding_files.pop(user.id, None)
        
        await update.message.reply_text("Brand DNA extracted and saved! You are now ready to generate quotes. Try sending me a voice note like 'Make a quote for John Smith for fixing the sink, $150 labor and $50 parts'.")
        
    except Exception as e:
        logger.error(f"Failed saving config: {e}")
        await update.message.reply_text("Failed to save your configuration. Please try again.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles both Photos and Documents (PDFs)."""
    user = update.effective_user
    db_user = await get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first.")
        return
        
    state = db_user.get("bot_state")
    
    if state == "ONBOARDING":
        # Get the file
        file_obj = None
        ext = ""
        if update.message.document:
            file_obj = await context.bot.get_file(update.message.document.file_id)
            # Try to get extension from the filename
            filename = update.message.document.file_name
            if filename and '.' in filename:
                ext = f".{filename.split('.')[-1]}"
            else:
                ext = ".pdf" # Fallback
        elif update.message.photo:
            # Get largest photo
            file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
            ext = ".jpg"
            
        if file_obj:
            filepath = os.path.join(TEMP_DIR, f"{user.id}_{file_obj.file_id}{ext}")
            await file_obj.download_to_drive(custom_path=filepath)
            
            if user.id not in onboarding_files:
                onboarding_files[user.id] = []
            onboarding_files[user.id].append(filepath)
            
            await update.message.reply_text(f"Received sample {len(onboarding_files[user.id])}. Send more or type /finish_onboarding.")
    
    elif state == "ACTIVE":
        if update.message.photo:
             await update.message.reply_text("I received a photo. I will extract the quote details from this shortly (WIP).")
        else:
             await update.message.reply_text("I only process photos or text/voice for quotes once active.")

import uuid
from document_factory import DocumentFactory

async def handle_text_or_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_user(user.id)
    
    if not db_user or db_user.get("bot_state") != "ACTIVE":
        await update.message.reply_text("I can only process these once you have finished Onboarding.")
        return
        
    text = ""
    if update.message.voice:
         await update.message.reply_text("Voice note transcription is currently WIP. Please type the text for now.")
         return
    else:
         text = update.message.text
         msg = await update.message.reply_text("Parsing text to generate quote...")

    # Fast-fetch user config (Brand DNA)
    res = supabase.table("user_configs").select("*").eq("user_id", db_user["id"]).execute()
    brand_dna = res.data[0] if res.data else {}

    # Extract quote data using Gemini
    quote_data = AIService.generate_quote_data(text)
    
    if not quote_data:
        await msg.edit_text("Sorry, I couldn't understand the quote details. Could you be more specific?")
        return
    
    # Generate Document
    output_filename = f"Quote_{uuid.uuid4().hex[:8]}.docx"
    doc_path = DocumentFactory.generate_docx(quote_data, brand_dna, output_filename)
    
    # Send document back
    if os.path.exists(doc_path):
        with open(doc_path, 'rb') as doc_file:
            await context.bot.send_document(chat_id=user.id, document=doc_file, filename=output_filename)
        await msg.edit_text("Here is your generated quote!")
    else:
        await msg.edit_text("Failed to generate the document file.")


def run_bot():
    if not settings.TELEGRAM_BOT_TOKEN:
         logger.error("No TELEGRAM_BOT_TOKEN provided.")
         return
         
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("finish_onboarding", finish_onboarding))
    
    # Document handlers (Photos and Files)
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))
    
    # Text and Voice handlers
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE & ~filters.COMMAND, handle_text_or_voice))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    run_bot()
