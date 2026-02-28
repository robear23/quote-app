# Product Requirement Document: Telegram Quote Agent

## 1. Project Overview
An AI-powered Telegram bot that allows tradespeople to generate professional, brand-aligned quotes and invoices via voice, text, or image. The system "learns" the user's business style during a one-time onboarding process.

## 2. Target Audience
Independent tradespeople (plumbers, electricians, builders) who need to generate quotes "on-site" but require a final editable document for professional delivery.

## 3. User Journey & Functional Requirements

### Phase 1: Web-to-Bot Handshake
* **Web Entry:** Simple landing page where users enter an email.
* **Handshake:** System generates a unique ID, stores it in Supabase, and redirects the user to Telegram with a deep-link (start parameter).

### Phase 2: AI Onboarding (State: ONBOARDING)
* **Sample Ingestion:** Bot requests 3–10 previous invoice/quote samples (PDF/JPG).
* **DNA Extraction:** - **Visuals:** Layout, logo placement, fonts, and table structures.
    - **Logic:** VAT/Tax registration status, currency, and calculation methods.
    - **Identity:** Business name, address, contact details, and bank info.
* **Format Preference:** Bot asks if the user prefers final outputs in `.docx` (Word), `.xlsx` (Excel), or editable PDF.

### Phase 3: Quote Generation (State: ACTIVE)
* **Multi-modal Input:** User sends a voice note, a photo of a notebook, or a text message.
* **Processing:** AI extracts:
    - Customer details (Name, Address).
    - Line items (Description, Quantity, Unit Price).
    - Adjustments (Discounts, Tax).
* **Interactive Refinement:** AI presents a summary in Telegram and asks: "Would you like to add/change anything further?"

### Phase 4: Delivery
* **Output:** Generates the file in the preferred format using the brand-matched template.
* **Storage:** All generated quotes are stored in Supabase for future reference/re-billing.

## 4. Technical Stack (Antigravity Environment)
* **Backend:** Python (FastAPI).
* **Database:** Supabase (Auth, Tables, Storage).
* **LLM:** Gemini 1.5 Pro (Multimodal analysis & Extraction).
* **Bot API:** python-telegram-bot.
* **File Gen:** `python-docx` for Word, `XlsxWriter` for Excel.
