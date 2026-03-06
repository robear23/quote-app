from google import genai
from google.genai import types
import json
import logging
import time
import os
from config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
if not client:
    logger.warning("GEMINI_API_KEY not found in environment.")

MODEL = "gemini-2.5-flash"

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
7. "calculation_methods": A JSON object with keys like "tax_rate" (numeric percentage, e.g. 20 for 20% VAT), "markup_percentage", and any other observed pricing logic.
8. "layout_preferences": Notes on visual layout (e.g., "Logo top left", "Clean modern font", "Blue color scheme").

Return ONLY a valid JSON object with these keys. If a field cannot be determined, set its value to null.
For "calculation_methods", always use a JSON object (not a string). If a tax rate is found (e.g. 20% VAT), set "tax_rate" to the numeric value (e.g. 20).
"""

QUOTE_GENERATION_PROMPT = """
You are an expert AI assistant who turns raw user requests into structured quote data for tradespeople.
Extract the following from the user's input in strict JSON format:
1. "customer_name": Name of the customer (string)
2. "customer_address": Address of the customer if mentioned (string or null)
3. "line_items": An array of objects, each with:
   - "description" (string): what the work or material is
   - "quantity" (number): how many units
   - "unit_price" (number): price per unit

If prices are not mentioned, infer reasonable defaults for the trade described.
Return ONLY valid JSON.
"""

VOICE_QUOTE_PROMPT = """
You are an expert AI assistant who turns voice notes from tradespeople into structured quote data.
Transcribe the following voice note and extract the quote details in strict JSON format:
1. "customer_name": Name of the customer (string or null)
2. "customer_address": Address of the customer if mentioned (string or null)
3. "line_items": An array of objects, each with:
   - "description" (string): what the work or material is
   - "quantity" (number): how many units
   - "unit_price" (number): price per unit

If prices are not mentioned, infer reasonable defaults for the trade described.
Return ONLY valid JSON.
"""

IMAGE_QUOTE_PROMPT = """
You are an expert AI assistant who extracts quote information from images sent by tradespeople.
The image may show handwritten notes, a photo of a job, a printed list, a whiteboard, or a notebook.
Extract the following in strict JSON format:
1. "customer_name": Name of the customer if visible (string or null)
2. "customer_address": Address if visible (string or null)
3. "line_items": An array of objects, each with:
   - "description" (string): what the work or material is
   - "quantity" (number): how many units
   - "unit_price" (number): price per unit

If prices are not visible, infer reasonable defaults based on the trade context.
Return ONLY valid JSON.
"""

REFINEMENT_PROMPT = """
You are helping a tradesperson refine a quote. They were shown a summary and have replied.

Current quote data (JSON):
{current_quote}

User's reply: "{user_response}"

Determine whether the user is CONFIRMING the quote (e.g. yes, ok, looks good, send it, correct, fine, that's right, generate it)
or REQUESTING CHANGES (e.g. mentioning different prices, names, items to add/remove, corrections, currency changes).

If the user requests a currency change (e.g. "currency is £", "use GBP", "change to euros", "currency should be USD"):
- Update the "currency" field in updated_quote to the correct ISO code (e.g. "GBP" for £/pounds, "EUR" for euros, "USD" for dollars).

Return a JSON object with exactly these two keys:
- "confirmed": true if confirming, false if requesting changes
- "updated_quote": the complete updated quote JSON (unchanged if confirmed, with modifications applied if changes were requested)
"""

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

JSON_CONFIG = types.GenerateContentConfig(response_mime_type="application/json")


def _generate_with_retry(contents, config=JSON_CONFIG):
    """Calls Gemini with exponential backoff retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded for Gemini API call")


class AIService:
    @staticmethod
    def extract_brand_dna(file_uris: list[str]) -> dict:
        """
        Takes a list of local file paths, sends them to Gemini,
        and returns the structured JSON Brand DNA.
        """
        try:
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
                    uploaded_files.append(client.files.upload(file=path))

            contents = [DNA_EXTRACTION_PROMPT] + text_contents + uploaded_files

            response = _generate_with_retry(contents)

            for f in uploaded_files:
                try:
                    client.files.delete(name=f.name)
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
            response = _generate_with_retry(f"{QUOTE_GENERATION_PROMPT}\n\nUser Input: {text}")
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Failed to generate quote data: {e}")
            return {}

    @staticmethod
    def transcribe_and_extract_voice(file_path: str) -> dict:
        """Transcribes a voice note (OGG) and extracts structured quote data."""
        try:
            uploaded_file = client.files.upload(file=file_path)

            response = _generate_with_retry([VOICE_QUOTE_PROMPT, uploaded_file])

            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Failed to process voice note: {e}")
            return {}

    @staticmethod
    def extract_quote_from_image(file_path: str) -> dict:
        """Extracts structured quote data from an image (photo of notes, job site, etc.)."""
        try:
            uploaded_file = client.files.upload(file=file_path)

            response = _generate_with_retry([IMAGE_QUOTE_PROMPT, uploaded_file])

            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Failed to extract quote from image: {e}")
            return {}

    @staticmethod
    def refine_quote(current_quote: dict, user_response: str) -> dict:
        """
        Determines if the user is confirming a quote or requesting changes.
        Returns {"confirmed": bool, "updated_quote": dict}.
        """
        try:
            prompt = REFINEMENT_PROMPT.format(
                current_quote=json.dumps(current_quote, indent=2),
                user_response=user_response
            )
            response = _generate_with_retry(prompt)
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Failed to refine quote: {e}")
            return {"confirmed": True, "updated_quote": current_quote}
