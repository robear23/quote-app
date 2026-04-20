from google import genai
from google.genai import types
import asyncio
import io
import json
import logging
import time
import os
import base64 as _b64
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
9. "primary_color_hex": The dominant brand/header color as a 6-digit hex code WITHOUT the # prefix (e.g., "1B3A5C" for navy blue). Look at header backgrounds, table header rows, colored banners, and logo colors. This is critical — inspect the document carefully for any colored elements.
10. "secondary_color_hex": The secondary accent color as a 6-digit hex code WITHOUT the # prefix, if present (e.g., highlight colors, subheadings). Set to null if none.

Return ONLY a valid JSON object with these keys. If a field cannot be determined, set its value to null.
For "calculation_methods", always use a JSON object (not a string). If a tax rate is found (e.g. 20% VAT), set "tax_rate" to the numeric value (e.g. 20).
"""

QUOTE_GENERATION_PROMPT = """
You are an expert AI assistant who turns raw user requests into structured quote data for tradespeople.
Input is often terse shorthand like "Customer Name. Job description Total" or "Name, job, price".
Extract the following from the user's input in strict JSON format:
1. "customer_name": Name of the customer (string)
2. "customer_address": Address of the customer if mentioned (string or null)
3. "line_items": An array of objects, each with:
   - "description" (string): what the work or material is
   - "quantity" (number): how many units
   - "unit_price" (number): price per unit

Rules:
- A trailing number after the job description is ALWAYS the price — never an address, postcode, or ID.
- If a lump-sum total is given (e.g. "New bathroom 3000"), create ONE line item with quantity=1 and unit_price equal to that total.
- If prices are not mentioned at all, infer reasonable defaults for the trade described.
- Always produce at least one line item — never return an empty line_items array.

Example:
Input: "Amy Smith. New bathroom 3000"
Output: {"customer_name": "Amy Smith", "customer_address": null, "line_items": [{"description": "New bathroom", "quantity": 1, "unit_price": 3000}]}

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

Rules:
- If a lump-sum total is mentioned (e.g. "New bathroom, three thousand pounds"), create ONE line item with quantity=1 and unit_price equal to that total.
- If prices are not mentioned at all, infer reasonable defaults for the trade described.
- Always produce at least one line item — never return an empty line_items array.
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

TEMPLATE_MAP_PROMPT = """
You are analyzing a DOCX quote/invoice document to identify which cells contain VARIABLE data that changes per quote.

Document structure (JSON):
{structure}

Business info already extracted (static — do NOT mark these as variable):
{business_info}

Identify the locations of these VARIABLE fields. Return null for any field you cannot locate.

Respond with ONLY a valid JSON object with these keys:
- "customer_name": location where the customer/client name appears
- "customer_address": location of customer address (null if absent)
- "quote_ref": location of quote/invoice reference number (null if absent)
- "quote_date": location of the date (null if absent)
- "line_items_table_index": integer index (0-based) of the table containing line items rows (description, qty, price, total columns)
- "line_item_header_rows": list of row indices (0-based) that are header rows in the line items table
- "subtotal_value_location": location of the subtotal numeric value cell (null if absent)
- "tax_amount_value_location": location of the tax/VAT amount numeric value cell (null if absent)
- "grand_total_value_location": location of the grand total / total due numeric value cell

Location format: {{"type": "table", "table_index": N, "row_index": N, "col_index": N}}
  OR {{"type": "paragraph", "paragraph_index": N}} (use 0-based index into the non-empty paragraphs list)
"""

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

JSON_CONFIG = types.GenerateContentConfig(response_mime_type="application/json")

# Limits concurrent Gemini calls to prevent thread pool exhaustion under load.
# Tune this based on your Gemini API quota (free tier: lower; paid tier: higher).
_ai_semaphore = asyncio.Semaphore(5)


async def run_ai(func, *args):
    """Run a sync AI function with concurrency limiting (max 5 simultaneous Gemini calls)."""
    async with _ai_semaphore:
        return await asyncio.to_thread(func, *args)


class RateLimitError(Exception):
    """Raised when Gemini API rate limit retries are exhausted."""
    pass


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
            if "429" in error_str or "quota" in error_str.lower() or "503" in error_str or "UNAVAILABLE" in error_str:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Gemini transient error (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise
    raise RateLimitError("Gemini API is unavailable — please try again in a moment.")


class AIService:
    @staticmethod
    def extract_brand_dna(file_uris: list[str]) -> dict | None:
        """
        Takes a list of local file paths, sends them to Gemini,
        and returns the structured JSON Brand DNA, or None on failure.
        """
        try:
            import base64 as _b64
            import docx as _docx
            from docx.oxml.ns import qn as _qn
            uploaded_files = []
            text_contents = []
            logo_b64 = None
            _raster_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif'}

            for path in file_uris:
                if path.lower().endswith(".docx"):
                    try:
                        doc = _docx.Document(path)
                        full_text = []

                        # Regular paragraphs
                        for para in doc.paragraphs:
                            if para.text.strip():
                                full_text.append(para.text)

                        # Table cells
                        for table in doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    if cell.text.strip():
                                        full_text.append(cell.text)

                        # Text boxes (w:txbxContent) — often used for company name/address
                        try:
                            for txbx in doc.element.body.iter(_qn('w:txbxContent')):
                                for t_el in txbx.iter(_qn('w:t')):
                                    if t_el.text and t_el.text.strip():
                                        full_text.append(t_el.text)
                        except Exception:
                            pass

                        # Headers and footers — often contain business name/address
                        try:
                            for section in doc.sections:
                                for hdr_ftr in (section.header, section.footer):
                                    if getattr(hdr_ftr, 'is_linked_to_previous', True):
                                        continue
                                    for para in hdr_ftr.paragraphs:
                                        if para.text.strip():
                                            full_text.append(para.text)
                                    for tbl in hdr_ftr.tables:
                                        for row in tbl.rows:
                                            for cell in row.cells:
                                                if cell.text.strip():
                                                    full_text.append(cell.text)
                        except Exception:
                            pass

                        extracted = "\n".join(full_text)
                        logger.info(f"DOCX text extracted from {os.path.basename(path)}: {len(extracted)} chars")
                        text_contents.append(f"\n--- Content of {os.path.basename(path)} ---\n{extracted}")

                        # Extract first raster image as logo
                        if logo_b64 is None:
                            for rel in doc.part.rels.values():
                                try:
                                    target = getattr(rel, 'target_ref', '') or ''
                                    ext = os.path.splitext(target.lower())[1]
                                    if ext in _raster_exts:
                                        blob = rel.target_part.blob
                                        if len(blob) > 500:
                                            logo_b64 = _b64.b64encode(blob).decode('utf-8')
                                            break
                                except Exception:
                                    continue
                    except Exception as e:
                        logger.error(f"Failed to read docx {path}: {e}", exc_info=True)
                else:
                    uploaded_files.append(client.files.upload(file=path))

            # If DOCX text was extracted, check it has meaningful content
            total_text_chars = sum(len(t) for t in text_contents)
            if text_contents and total_text_chars < 100 and not uploaded_files:
                logger.warning(
                    f"DOCX text extraction yielded only {total_text_chars} chars — "
                    "files may use unsupported layout (text boxes only, encrypted, etc.)"
                )

            # Don't call Gemini if there's nothing to analyze
            if not text_contents and not uploaded_files:
                logger.error("No extractable content from any onboarding file")
                return None

            if text_contents:
                combined_text = DNA_EXTRACTION_PROMPT + "\n\n" + "\n\n".join(text_contents)
                # Pass plain string when there are no file objects (list wrapping can confuse SDK)
                contents = combined_text if not uploaded_files else [combined_text] + uploaded_files
            else:
                contents = [DNA_EXTRACTION_PROMPT] + uploaded_files

            logger.info(f"Calling Gemini for Brand DNA extraction, content length: {len(str(contents))} chars")
            response = _generate_with_retry(contents)
            logger.info(f"Gemini Brand DNA response received, finish_reason: {getattr(response, 'candidates', [{}])[0]}")

            for f in uploaded_files:
                try:
                    client.files.delete(name=f.name)
                except Exception:
                    pass

            # response.text raises ValueError in the Google GenAI SDK if the response
            # has no candidates or was blocked — must be caught explicitly
            try:
                raw = response.text or ""
            except Exception as e:
                logger.error(f"response.text raised: {e}", exc_info=True)
                return None

            logger.info(f"Brand DNA raw response (first 300 chars): {raw[:300]!r}")

            # Strip markdown code fences if Gemini wraps the JSON
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            if not raw:
                logger.error("Gemini returned empty response for Brand DNA extraction")
                return None

            result = json.loads(raw)
            if not isinstance(result, dict) or not result:
                logger.error(f"Gemini returned non-dict or empty result: {result!r}")
                return None
            if logo_b64:
                result["logo_base64"] = logo_b64
            return result

        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract Brand DNA: {e}", exc_info=True)
            return None

    @staticmethod
    def generate_quote_data(text: str) -> dict:
        """Parses user text into structured quote data using Gemini."""
        try:
            response = _generate_with_retry(f"{QUOTE_GENERATION_PROMPT}\n\nUser Input: {text}")
            return json.loads(response.text)
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate quote data: {e}")
            return {}

    @staticmethod
    def transcribe_and_extract_voice(file_path: str) -> dict:
        """Transcribes a voice note (OGG) and extracts structured quote data."""
        try:
            uploaded_file = client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(mime_type="audio/ogg"),
            )

            # Wait for Gemini to finish processing the uploaded file
            max_wait = 30
            waited = 0
            while getattr(uploaded_file.state, "name", str(uploaded_file.state)) == "PROCESSING":
                time.sleep(2)
                waited += 2
                uploaded_file = client.files.get(name=uploaded_file.name)
                if waited >= max_wait:
                    raise Exception("Timed out waiting for voice file to be processed by Gemini")

            if getattr(uploaded_file.state, "name", str(uploaded_file.state)) == "FAILED":
                raise Exception(f"Gemini file processing failed for {file_path}")

            response = _generate_with_retry([VOICE_QUOTE_PROMPT, uploaded_file])

            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            return json.loads(response.text)

        except RateLimitError:
            raise
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

        except RateLimitError:
            raise
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

        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Failed to refine quote: {e}")
            return {"confirmed": True, "updated_quote": current_quote}

    @staticmethod
    def build_quote_template(docx_path: str, brand_dna: dict) -> bytes | None:
        """
        Takes a sample quote DOCX, asks Gemini to map variable fields, injects
        docxtpl Jinja2 placeholders via python-docx, and returns the modified
        DOCX as bytes. Returns None if the document cannot be processed.
        """
        try:
            import docx as _docx
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn

            doc = _docx.Document(docx_path)
        except Exception as e:
            logger.error(f"Failed to open DOCX for template building: {e}")
            return None

        # Build a compact structure summary to send to Gemini
        non_empty_paras = [p for p in doc.paragraphs if p.text.strip()]
        structure = {
            "paragraphs": [{"index": i, "text": p.text.strip()} for i, p in enumerate(non_empty_paras[:60])],
            "tables": [],
        }
        for ti, table in enumerate(doc.tables):
            table_data = {"index": ti, "rows": []}
            for ri, row in enumerate(table.rows[:20]):
                cells = [{"col": ci, "text": cell.text.strip()} for ci, cell in enumerate(row.cells)]
                table_data["rows"].append(cells)
            structure["tables"].append(table_data)

        business_info = {k: brand_dna.get(k) for k in (
            "business_name", "business_address", "contact_details", "bank_info", "vat_tax_status"
        ) if brand_dna.get(k)}

        prompt = TEMPLATE_MAP_PROMPT.format(
            structure=json.dumps(structure, indent=2),
            business_info=json.dumps(business_info, indent=2),
        )

        try:
            response = _generate_with_retry(prompt)
            field_map = json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini template mapping failed: {e}")
            return None

        # ── Helpers ─────────────────────────────────────────────────────────

        def _set_para_text(para, text: str):
            """Replace paragraph text, preserving formatting of the first run."""
            for run in para.runs:
                run.text = ""
            if para.runs:
                para.runs[0].text = text
            else:
                para.add_run(text)

        def _set_cell_text(cell, text: str):
            _set_para_text(cell.paragraphs[0], text)

        def _inject_location(loc, placeholder: str):
            if not loc or not isinstance(loc, dict):
                return
            try:
                if loc.get("type") == "paragraph":
                    idx = loc["paragraph_index"]
                    if idx < len(non_empty_paras):
                        _set_para_text(non_empty_paras[idx], placeholder)
                elif loc.get("type") == "table":
                    cell = doc.tables[loc["table_index"]].rows[loc["row_index"]].cells[loc["col_index"]]
                    _set_cell_text(cell, placeholder)
            except (IndexError, KeyError, TypeError) as e:
                logger.warning(f"Failed to inject placeholder '{placeholder}': {e}")

        # ── Inject simple field placeholders ────────────────────────────────
        _inject_location(field_map.get("customer_name"), "{{ customer_name }}")
        _inject_location(field_map.get("customer_address"), "{{ customer_address }}")
        _inject_location(field_map.get("quote_ref"), "{{ quote_ref }}")
        _inject_location(field_map.get("quote_date"), "{{ quote_date }}")
        _inject_location(field_map.get("subtotal_value_location"), "{{ subtotal }}")
        _inject_location(field_map.get("tax_amount_value_location"), "{{ tax_amount }}")
        _inject_location(field_map.get("grand_total_value_location"), "{{ grand_total }}")

        # ── Inject line items table loop ─────────────────────────────────────
        li_ti = field_map.get("line_items_table_index")
        if li_ti is not None:
            try:
                li_table = doc.tables[int(li_ti)]
                header_rows = set(field_map.get("line_item_header_rows") or [0])
                data_row_indices = [i for i in range(len(li_table.rows)) if i not in header_rows]

                if data_row_indices:
                    first_idx = data_row_indices[0]
                    template_row = li_table.rows[first_idx]
                    num_cols = len(template_row.cells)

                    # Placeholders per column: first cell gets the {% tr for %} tag
                    col_tpls = [
                        "{% tr for item in line_items %}{{ item.description }}",
                        "{{ item.qty }}",
                        "{{ item.unit_price_str }}",
                        "{{ item.total_str }}",
                    ]
                    for ci in range(min(num_cols, len(col_tpls))):
                        _set_cell_text(template_row.cells[ci], col_tpls[ci])
                    # Clear any extra columns beyond our 4
                    for ci in range(len(col_tpls), num_cols):
                        _set_cell_text(template_row.cells[ci], "")

                    # Delete extra data rows (keep only the first as the loop template)
                    for ri in reversed(data_row_indices[1:]):
                        row_elem = li_table.rows[ri]._tr
                        li_table._tbl.remove(row_elem)

                    # Add {% tr endfor %} row after the template row
                    endfor_tr = OxmlElement('w:tr')
                    for ci in range(num_cols):
                        tc = OxmlElement('w:tc')
                        tc.append(OxmlElement('w:tcPr'))
                        wp = OxmlElement('w:p')
                        if ci == 0:
                            wr = OxmlElement('w:r')
                            wt = OxmlElement('w:t')
                            wt.text = "{% tr endfor %}"
                            wr.append(wt)
                            wp.append(wr)
                        tc.append(wp)
                        endfor_tr.append(tc)
                    template_row._tr.addnext(endfor_tr)

            except (IndexError, TypeError) as e:
                logger.warning(f"Failed to inject line items loop: {e}")

        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        return output.getvalue()
