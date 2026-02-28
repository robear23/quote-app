import google.generativeai as genai
import json
import logging
import time
import os
from config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment.")

DNA_EXTRACTION_PROMPT = """
You are a highly capable AI assistant helping a tradesperson set up their automated quoting system. 
Analyze the provided sample invoices/quotes and extract their "Brand DNA" into a strict JSON format.

Extract the following information:
1. "business_name": The name of the business issuing the quotes.
2. "business_address": The physical address of the business.
3. "contact_details": Phone numbers, emails, or websites.
4. "bank_info": Bank details for payment (Account Number, Sort Code, IBAN, etc.).
5. "vat_tax_status": Information regarding VAT registration, tax rates applied, or tax IDs.
6. "currency": The primary currency used (e.g., USD, GBP, EUR).
7. "calculation_methods": Any observed logic (e.g., standard labor rates, markup percentages, tax logic).
8. "layout_preferences": Notes on visual layout (e.g., "Logo top left", "Clean modern font", "Blue color scheme").

Return ONLY a valid JSON object with these keys. If a field cannot be determined, set its value to null.
"""

QUOTE_GENERATION_PROMPT = """
You are an expert AI assistant who turns raw user requests into structured quote data.
Extract the following from the user's input to generate a quote in strict JSON format:
1. "customer_name": Name of the customer (string)
2. "customer_address": Address of the customer if any (string or null)
3. "line_items": An array of objects, where each object has "description" (string), "quantity" (number), and "unit_price" (number).

Infer reasonable default prices if none are given based on the context, or use the ones provided.
Return ONLY valid JSON.
"""

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def _call_gemini_with_retry(model, contents, generation_config=None):
    """Calls Gemini with exponential backoff retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(
                contents,
                generation_config=generation_config
            )
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("Max retries exceeded for Gemini API call")


class AIService:
    @staticmethod
    def extract_brand_dna(file_uris: list[str]) -> dict:
        """
        Takes a list of local file paths downloaded by Telegram,
        sends them to Gemini, and returns the structured JSON Brand DNA.
        """
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            uploaded_files = []
            text_contents = []
            for path in file_uris:
                if path.lower().endswith(".docx"):
                    try:
                        import docx
                        doc = docx.Document(path)
                        full_text = []
                        for para in doc.paragraphs:
                            full_text.append(para.text)
                        for table in doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    full_text.append(cell.text)
                        text_contents.append(f"\n--- Content of {os.path.basename(path)} ---\n" + "\n".join(full_text))
                    except Exception as e:
                        logger.error(f"Failed to read docx {path}: {e}")
                else:
                    uploaded_files.append(genai.upload_file(path))
            
            contents = [DNA_EXTRACTION_PROMPT] + text_contents + uploaded_files
            
            response = _call_gemini_with_retry(
                model,
                contents,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            
            # Cleanup uploaded files after processing
            for f in uploaded_files:
                try:
                    genai.delete_file(f.name)
                except Exception:
                    pass

            return json.loads(response.text)
            
        except Exception as e:
            logger.error(f"Failed to extract Brand DNA: {e}")
            return {}

    @staticmethod
    def generate_quote_data(text: str) -> dict:
        """Parses user text into structured quote data using Gemini."""
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = _call_gemini_with_retry(
                model,
                f"{QUOTE_GENERATION_PROMPT}\n\nUser Input: {text}",
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Failed to generate quote data: {e}")
            return {}
