"""
test_runner.py — Quote generation automated test suite.

Workflow:
  1. Creates 10 realistic DOCX templates (blank templates with bracket placeholders)
  2. Runs each through: extract_brand_dna → build_quote_template → generate_from_template
  3. Scores each on 5 dimensions (placeholder accuracy, line items, calculations,
     template fidelity, client readiness)
  4. Writes test_results/quote_test_analysis.md

Usage (from project root):  python test_runner.py
"""

import os
import re
import sys
import json
import shutil
import logging
import traceback
from pathlib import Path
from datetime import date, datetime

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.path.insert(0, str(Path(__file__).parent))
from ai_service import AIService
from document_factory import DocumentFactory, _sym
from config import settings
from google import genai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_runner")

TEMPLATES_DIR = Path("test_templates")
GENERATED_DIR = Path("test_generated")
RESULTS_DIR = Path("test_results")
for _d in (TEMPLATES_DIR, GENERATED_DIR, RESULTS_DIR):
    _d.mkdir(exist_ok=True)

_gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
ANALYSIS_MODEL = "gemini-2.5-flash"


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "id": "01_plumber",
        "business_name": "Waters & Sons Plumbing Services",
        "business_address": "14 Copper Lane, Birmingham, B3 2PQ",
        "contact_line": "Tel: 0121 555 0190  |  info@watersplumbing.co.uk",
        "vat_reg": "VAT Registration No: 123 456 789",
        "bank_details": "Bank: Lloyds Bank  |  Sort Code: 30-10-15  |  Account No: 12345678",
        "columns": ["Description", "Qty", "Unit Price", "Total"],
        "sample_rows": [
            ["Replace combi boiler (Worcester Bosch 30i)", "1", "£1,200.00", "£1,200.00"],
            ["New radiator — double panel convector", "2", "£145.00", "£290.00"],
        ],
        "totals_rows": [("Subtotal", "£1,490.00"), ("VAT (20%)", "£298.00"), ("TOTAL DUE", "£1,788.00")],
        "client_label": "Client Name",
        "address_label": "Client Address",
        "ref_label": "Quote No.",
        "date_label": "Date",
        "primary_color": "1B4F72",
        "currency": "GBP",
        "tax_rate": 20.0,
        "quote_data": {
            "customer_name": "Mr James Holloway",
            "customer_address": "82 Elm Park Road, Solihull, B91 3DP",
            "line_items": [
                {"description": "Supply and fit new combi boiler (Worcester Bosch 30i)", "quantity": 1, "unit_price": 1400.00},
                {"description": "Emergency call-out fee", "quantity": 1, "unit_price": 95.00},
                {"description": "Labour — installation (6 hours)", "quantity": 6, "unit_price": 65.00},
            ],
        },
    },
    {
        "id": "02_web_agency",
        "business_name": "Pixel Forge Studio",
        "business_address": "200 Design District, London, EC2A 4NE",
        "contact_line": "hello@pixelforge.io  |  +44 20 7946 0831",
        "vat_reg": None,
        "bank_details": "Bank: Monzo Business  |  Sort: 04-00-04  |  Account: 87654321",
        "columns": ["Service", "Hours", "Rate", "Total"],
        "sample_rows": [
            ["Website redesign — UX/UI design phase", "40", "$150.00", "$6,000.00"],
            ["Front-end development (React)", "60", "$175.00", "$10,500.00"],
        ],
        "totals_rows": [("Total", "$16,500.00")],
        "client_label": "Customer Name",
        "address_label": "Customer Address",
        "ref_label": "Invoice #",
        "date_label": "Invoice Date",
        "primary_color": "2C3E50",
        "currency": "USD",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Sarah Chen",
            "customer_address": "Suite 200, 45 Tech Boulevard, San Francisco, CA 94105",
            "line_items": [
                {"description": "Website redesign — UX/UI design phase", "quantity": 40, "unit_price": 150.00},
                {"description": "Front-end development (React)", "quantity": 60, "unit_price": 175.00},
                {"description": "CMS integration and training", "quantity": 8, "unit_price": 200.00},
            ],
        },
    },
    {
        "id": "03_interior_design",
        "business_name": "Elara Interiors Ltd",
        "business_address": "Suite 5, The Design Quarter, London, W1K 3JZ",
        "contact_line": "studio@elarainteriors.co.uk  |  Tel: 020 3456 7890",
        "vat_reg": None,
        "bank_details": "Bank: HSBC  |  Sort Code: 40-05-30  |  Account: 23456789",
        "columns": ["Description", "Qty", "Unit", "Unit Price", "Total"],
        "sample_rows": [
            ["Full design concept and mood boards", "1", "pack", "£850.00", "£850.00"],
            ["Bespoke sofa — 3-seat velvet", "1", "item", "£2,200.00", "£2,200.00"],
            ["Window dressing — made-to-measure curtains", "2", "pair", "£640.00", "£1,280.00"],
        ],
        "totals_rows": [("Subtotal", "£4,330.00"), ("Total", "£4,330.00")],
        "client_label": "Client Name",
        "address_label": "Client Address",
        "ref_label": "Quote No.",
        "date_label": "Quote Date",
        "primary_color": "7D3C98",
        "currency": "GBP",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Mrs Catherine Walsh",
            "customer_address": "14 Kensington Gardens, London, W8 4PX",
            "line_items": [
                {"description": "Full living room design concept and mood boards", "quantity": 1, "unit_price": 850.00},
                {"description": "Bespoke sofa (3-seater, velvet, duck-egg blue)", "quantity": 1, "unit_price": 2200.00},
                {"description": "Window dressing — made-to-measure curtains", "quantity": 2, "unit_price": 640.00},
                {"description": "Interior design consultation (per day)", "quantity": 3, "unit_price": 500.00},
            ],
        },
    },
    {
        "id": "04_construction",
        "business_name": "Blue Ridge Construction Pty Ltd",
        "business_address": "Unit 3, 88 Industrial Drive, Fyshwick, ACT 2609",
        "contact_line": "Phone: (02) 6123 4567  |  admin@blueridgeconstruction.com.au",
        "vat_reg": "ABN: 51 234 567 890",
        "bank_details": "Bank: Commonwealth  |  BSB: 062-000  |  Account: 34567890",
        "columns": ["Item", "Units", "Rate", "Amount"],
        "sample_rows": [
            ["Demolition and site preparation", "1 lot", "A$4,500.00", "A$4,500.00"],
            ["Concrete slab — 6m x 4m", "1 lot", "A$8,800.00", "A$8,800.00"],
        ],
        "totals_rows": [("Subtotal", "A$13,300.00"), ("GST (10%)", "A$1,330.00"), ("TOTAL", "A$14,630.00")],
        "client_label": "Client Name",
        "address_label": "Project Address",
        "ref_label": "Quote Reference",
        "date_label": "DD/MM/YYYY",
        "primary_color": "E67E22",
        "currency": "AUD",
        "tax_rate": 10.0,
        "quote_data": {
            "customer_name": "David Nguyen",
            "customer_address": "22 Ironbark Close, Canberra ACT 2600",
            "line_items": [
                {"description": "Demolition and site preparation", "quantity": 1, "unit_price": 4500.00},
                {"description": "Concrete slab — 6m x 4m extension", "quantity": 1, "unit_price": 8800.00},
                {"description": "Structural framing and roofing", "quantity": 1, "unit_price": 12000.00},
            ],
        },
    },
    {
        "id": "05_accounting",
        "business_name": "Meridian Advisory Services",
        "business_address": "Floor 7, City Tower, Manchester, M1 4BT",
        "contact_line": "info@meridianadvisory.co.uk  |  0161 234 5678",
        "vat_reg": "VAT No: 987 654 321",
        "bank_details": "Bank: NatWest  |  Sort Code: 60-40-05  |  Account: 45678901",
        "columns": ["Description", "Hours", "Rate", "Amount"],
        "sample_rows": [
            ["Statutory accounts preparation", "10", "£120.00", "£1,200.00"],
            ["Management accounts — Q1 review", "5", "£95.00", "£475.00"],
        ],
        "totals_rows": [("Sub-Total", "£1,675.00"), ("VAT (20%)", "£335.00"), ("Total Due", "£2,010.00")],
        "client_label": "Client Name",
        "address_label": "Client Address",
        "ref_label": "Invoice Number",
        "date_label": "Invoice Date",
        "primary_color": "154360",
        "currency": "GBP",
        "tax_rate": 20.0,
        "quote_data": {
            "customer_name": "Bourne Tech Limited",
            "customer_address": "3rd Floor, Southgate House, Leeds, LS1 4AD",
            "line_items": [
                {"description": "Statutory accounts preparation and filing", "quantity": 1, "unit_price": 1200.00},
                {"description": "Management accounts — quarterly review", "quantity": 4, "unit_price": 450.00},
            ],
        },
    },
    {
        "id": "06_photography",
        "business_name": "Luminary Photography Co.",
        "business_address": "Studio 4, Lightworks Building, Edinburgh, EH1 1BB",
        "contact_line": "hello@luminaryphoto.com  |  07700 900 123",
        "vat_reg": None,
        "bank_details": "Bank: Starling Bank  |  Sort: 60-83-71  |  Account: 56789012",
        "columns": ["Package", "Price"],
        "sample_rows": [
            ["Full-day wedding photography (8 hours, 2 photographers)", "£3,200.00"],
            ["Premium editing package (300+ digital images)", "£800.00"],
        ],
        "totals_rows": [("Total", "£4,000.00")],
        "client_label": "Client Name",
        "address_label": "Client Address",
        "ref_label": "Ref No.",
        "date_label": "Date",
        "primary_color": "2C3E50",
        "currency": "GBP",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Emily & Marcos Reyes",
            "customer_address": "2890 Sunset Drive, Austin, TX 78701",
            "line_items": [
                {"description": "Full-day wedding photography (8 hours, 2 photographers)", "quantity": 1, "unit_price": 3200.00},
                {"description": "Premium editing package (300+ edited digital images)", "quantity": 1, "unit_price": 800.00},
            ],
        },
    },
    {
        "id": "07_it_services",
        "business_name": "TechStream Solutions GmbH",
        "business_address": "Hauptstrasse 120, 10117 Berlin, Germany",
        "contact_line": "info@techstream.de  |  +49 30 1234 5678",
        "vat_reg": "USt-IdNr.: DE 123 456 789",
        "bank_details": "Bank: Deutsche Bank  |  IBAN: DE89 3704 0044 0532 0130 00  |  BIC: COBADEFFXXX",
        "columns": ["Service", "Hours", "Rate (EUR)", "Total (EUR)"],
        "sample_rows": [
            ["Network infrastructure audit", "8", "EUR 200.00", "EUR 1,600.00"],
            ["Cloud migration consultation", "16", "EUR 185.00", "EUR 2,960.00"],
        ],
        "totals_rows": [("Subtotal", "EUR 4,560.00"), ("Total", "EUR 4,560.00")],
        "client_label": "Customer Name",
        "address_label": "Customer Address",
        "ref_label": "Ref #",
        "date_label": "Date",
        "primary_color": "1E8449",
        "currency": "EUR",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Brandt Manufacturing AG",
            "customer_address": "Industriestrasse 42, 80331 Munchen",
            "line_items": [
                {"description": "Network infrastructure audit", "quantity": 8, "unit_price": 200.00},
                {"description": "Server migration to cloud (AWS)", "quantity": 24, "unit_price": 185.00},
                {"description": "Cybersecurity assessment and report", "quantity": 16, "unit_price": 220.00},
                {"description": "Staff IT training workshop", "quantity": 4, "unit_price": 350.00},
            ],
        },
    },
    {
        "id": "08_landscaping",
        "business_name": "GreenPath Landscapes Ltd",
        "business_address": "34 Okarito Place, Christchurch, Canterbury 8082",
        "contact_line": "info@greenpathlandscapes.co.nz  |  03 379 4567",
        "vat_reg": "NZBN: 9429041234567",
        "bank_details": "Bank: ASB Bank  |  Account: 12-3456-7890123-00",
        "columns": ["Description", "Qty", "Unit Price", "Total"],
        "sample_rows": [
            ["Garden design plan and consultation", "1", "NZ$600.00", "NZ$600.00"],
            ["Native planting — supply and install", "15", "NZ$45.00", "NZ$675.00"],
        ],
        "totals_rows": [("Subtotal", "NZ$1,275.00"), ("GST (15%)", "NZ$191.25"), ("Total", "NZ$1,466.25")],
        "client_label": "Customer Name",
        "address_label": "Property Address",
        "ref_label": "Quote No.",
        "date_label": "Date",
        "primary_color": "186A3B",
        "currency": "NZD",
        "tax_rate": 15.0,
        "quote_data": {
            "customer_name": "Fiona & Stuart MacPherson",
            "customer_address": "67 Pohutukawa Avenue, Auckland 1010",
            "line_items": [
                {"description": "Garden design plan and consultation", "quantity": 1, "unit_price": 600.00},
                {"description": "Native planting — supply and install (15 plants)", "quantity": 15, "unit_price": 45.00},
                {"description": "Lawn scarification and reseeding", "quantity": 1, "unit_price": 380.00},
            ],
        },
    },
    {
        "id": "09_event_planning",
        "business_name": "Occasions Unlimited Events",
        "business_address": "Floor 12, Rockefeller Plaza, New York, NY 10020",
        "contact_line": "events@occasionsunlimited.com  |  +1 (212) 555-0147",
        "vat_reg": None,
        "bank_details": "Bank: Chase  |  Routing: 021000021  |  Account: 67890123",
        "columns": ["Service / Item", "Qty", "Price", "Total"],
        "sample_rows": [
            ["Venue hire — Grand Ballroom (full day)", "1", "$4,500.00", "$4,500.00"],
            ["Catering — 3-course dinner per guest", "80", "$85.00", "$6,800.00"],
            ["Audio-visual and technical crew", "1", "$2,800.00", "$2,800.00"],
        ],
        "totals_rows": [("Subtotal", "$14,100.00"), ("Total", "$14,100.00")],
        "client_label": "Client Name",
        "address_label": "Client Address",
        "ref_label": "Reference",
        "date_label": "Quote Date",
        "primary_color": "117A65",
        "currency": "USD",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Apex Financial Group",
            "customer_address": "One Liberty Plaza, New York, NY 10006",
            "line_items": [
                {"description": "Venue hire — Grand Ballroom (full day)", "quantity": 1, "unit_price": 4500.00},
                {"description": "Catering — 3-course dinner for 120 guests", "quantity": 120, "unit_price": 85.00},
                {"description": "Audio-visual equipment and technical crew", "quantity": 1, "unit_price": 2800.00},
                {"description": "Floral arrangements and table centrepieces", "quantity": 12, "unit_price": 175.00},
                {"description": "Event coordination and management", "quantity": 1, "unit_price": 1800.00},
            ],
        },
    },
    {
        "id": "10_legal_services",
        "business_name": "Thornton & Associates Solicitors",
        "business_address": "4 Gray's Inn Square, London, WC1R 5AH",
        "contact_line": "enquiries@thorntonlaw.co.uk  |  020 7242 8910",
        "vat_reg": None,
        "bank_details": "Bank: Barclays  |  Sort Code: 20-00-00  |  Account: 78901234",
        "columns": ["Professional Service", "Hours", "Fee (GBP)"],
        "sample_rows": [
            ["Residential conveyancing — freehold purchase", "6", "£900.00"],
            ["Land Registry and disbursements", "1", "£350.00"],
        ],
        "totals_rows": [("Subtotal", "£1,250.00"), ("Total", "£1,250.00")],
        "client_label": "Client Name",
        "address_label": "Address",
        "ref_label": "Matter Reference",
        "date_label": "Date",
        "primary_color": "641E16",
        "currency": "GBP",
        "tax_rate": 0.0,
        "quote_data": {
            "customer_name": "Mr & Mrs Philip Drummond",
            "customer_address": "Hillcrest Cottage, Great Missenden, HP16 0BD",
            "line_items": [
                {"description": "Residential conveyancing — purchase of freehold property", "quantity": 1, "unit_price": 1500.00},
                {"description": "Land Registry and search fees", "quantity": 1, "unit_price": 350.00},
            ],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# DOCX TEMPLATE CREATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _shade_cell(cell, fill_hex: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex.upper().lstrip("#"))
    tcPr.append(shd)


def _set_cell_text_styled(cell, text: str, bold: bool = False, color_hex: str = None, size_pt: int = None):
    para = cell.paragraphs[0]
    for run in para.runs:
        run.text = ""
    if para.runs:
        run = para.runs[0]
        run.text = text
    else:
        run = para.add_run(text)
    if bold:
        run.font.bold = True
    if color_hex:
        run.font.color.rgb = _rgb(color_hex)
    if size_pt:
        run.font.size = Pt(size_pt)


def create_template_doc(t: dict) -> Document:
    """Creates a DOCX blank template for the given config dict."""
    doc = Document()
    primary = t["primary_color"]
    white = "FFFFFF"

    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    # ── Business header ──────────────────────────────────────────────────────
    p = doc.add_paragraph()
    r = p.add_run(t["business_name"])
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = _rgb(primary)
    p.paragraph_format.space_after = Pt(2)

    addr_p = doc.add_paragraph(t["business_address"])
    addr_p.paragraph_format.space_before = Pt(0)
    addr_p.paragraph_format.space_after = Pt(0)

    contact_p = doc.add_paragraph(t["contact_line"])
    contact_p.paragraph_format.space_before = Pt(0)
    contact_p.paragraph_format.space_after = Pt(0)

    if t.get("vat_reg"):
        vp = doc.add_paragraph(t["vat_reg"])
        vp.paragraph_format.space_before = Pt(0)
        vp.paragraph_format.space_after = Pt(4)

    # ── QUOTATION title ──────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tr = title_p.add_run("QUOTATION")
    tr.font.size = Pt(18)
    tr.font.bold = True
    tr.font.color.rgb = _rgb(primary)
    title_p.paragraph_format.space_after = Pt(8)

    # ── Meta table: ref + date ───────────────────────────────────────────────
    ref_label = t["ref_label"]
    date_label = t["date_label"]
    meta = doc.add_table(rows=2, cols=4)
    meta.style = "Table Grid"

    label_bg = "D5E8F4"
    meta.cell(0, 0).text = ref_label
    _shade_cell(meta.cell(0, 0), label_bg)
    meta.cell(0, 1).text = f"[{ref_label}]"
    meta.cell(0, 2).text = date_label
    _shade_cell(meta.cell(0, 2), label_bg)
    meta.cell(0, 3).text = f"[{date_label}]"
    meta.cell(1, 0).text = "Valid Until"
    _shade_cell(meta.cell(1, 0), label_bg)
    meta.cell(1, 1).text = "[DD/MM/YYYY]"
    meta.cell(1, 2).text = ""
    meta.cell(1, 3).text = ""

    doc.add_paragraph("").paragraph_format.space_before = Pt(6)

    # ── Bill To ──────────────────────────────────────────────────────────────
    bt = doc.add_paragraph()
    bt_run = bt.add_run("Bill To:")
    bt_run.font.bold = True
    bt_run.font.color.rgb = _rgb(primary)
    bt.paragraph_format.space_after = Pt(0)

    doc.add_paragraph(f"[{t['client_label']}]").paragraph_format.space_after = Pt(0)
    doc.add_paragraph(f"[{t['address_label']}]").paragraph_format.space_after = Pt(8)

    doc.add_paragraph("")

    # ── Line items table ─────────────────────────────────────────────────────
    columns = t["columns"]
    sample_rows = t["sample_rows"]
    num_cols = len(columns)
    items_tbl = doc.add_table(rows=1 + len(sample_rows), cols=num_cols)
    items_tbl.style = "Table Grid"

    for ci, col_name in enumerate(columns):
        cell = items_tbl.cell(0, ci)
        _set_cell_text_styled(cell, col_name, bold=True, color_hex=white)
        _shade_cell(cell, primary)

    for ri, row_data in enumerate(sample_rows):
        for ci, val in enumerate(row_data):
            items_tbl.cell(ri + 1, ci).text = str(val)

    doc.add_paragraph("").paragraph_format.space_before = Pt(4)

    # ── Totals table ─────────────────────────────────────────────────────────
    totals_rows = t["totals_rows"]
    totals_tbl = doc.add_table(rows=len(totals_rows), cols=2)
    totals_tbl.style = "Table Grid"

    for ri, (label, val) in enumerate(totals_rows):
        label_cell = totals_tbl.cell(ri, 0)
        val_cell = totals_tbl.cell(ri, 1)
        is_last = ri == len(totals_rows) - 1
        if is_last:
            _shade_cell(label_cell, primary)
            _shade_cell(val_cell, primary)
            _set_cell_text_styled(label_cell, label, bold=True, color_hex=white)
            _set_cell_text_styled(val_cell, val, bold=True, color_hex=white)
        else:
            label_cell.text = label
            val_cell.text = val

    doc.add_paragraph("").paragraph_format.space_before = Pt(8)

    # ── Bank / payment footer ─────────────────────────────────────────────────
    pmt = doc.add_paragraph()
    pr = pmt.add_run("Payment Details:")
    pr.font.bold = True
    pr.font.color.rgb = _rgb(primary)
    pmt.paragraph_format.space_after = Pt(0)

    doc.add_paragraph(t["bank_details"]).paragraph_format.space_after = Pt(0)
    doc.add_paragraph("Payment due within 30 days of invoice date.")

    return doc


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(t: dict) -> dict:
    """
    Runs one template through the full pipeline.
    Returns a result dict with paths, brand_dna, quote_data, error info.
    """
    tid = t["id"]
    result = {
        "id": tid,
        "config": t,
        "blank_path": None,
        "processed_path": None,
        "generated_path": None,
        "brand_dna": None,
        "errors": [],
        "warnings": [],
    }

    # Step 1: Create blank template
    log.info(f"[{tid}] Creating blank template...")
    blank_path = TEMPLATES_DIR / f"{tid}_blank.docx"
    try:
        doc = create_template_doc(t)
        doc.save(str(blank_path))
        result["blank_path"] = blank_path
        log.info(f"[{tid}] Blank template saved: {blank_path}")
    except Exception as e:
        result["errors"].append(f"Template creation failed: {e}")
        log.error(f"[{tid}] Template creation error: {e}")
        return result

    # Step 2: Extract brand DNA
    log.info(f"[{tid}] Extracting brand DNA...")
    try:
        brand_dna = AIService.extract_brand_dna_from_blank(str(blank_path))
        if not brand_dna:
            result["errors"].append("extract_brand_dna_from_blank returned None")
            return result
        # Merge in currency/tax/format (normally collected during bot onboarding)
        brand_dna["currency"] = t["currency"]
        brand_dna["calculation_methods"] = {"tax_rate": t["tax_rate"]}
        brand_dna["preferred_format"] = "docx"
        result["brand_dna"] = brand_dna
        log.info(f"[{tid}] Brand DNA extracted: business_name={brand_dna.get('business_name')!r}, color={brand_dna.get('primary_color_hex')!r}")
    except Exception as e:
        result["errors"].append(f"Brand DNA extraction failed: {e}")
        log.error(f"[{tid}] Brand DNA error: {traceback.format_exc()}")
        return result

    # Step 3: Build Jinja2 template
    log.info(f"[{tid}] Building quote template (Gemini field mapping)...")
    try:
        template_bytes = AIService.build_quote_template(str(blank_path), brand_dna)
        if not template_bytes:
            result["errors"].append("build_quote_template returned None")
            return result
        processed_path = TEMPLATES_DIR / f"{tid}_processed.docx"
        processed_path.write_bytes(template_bytes)
        result["processed_path"] = processed_path
        log.info(f"[{tid}] Processed template saved: {processed_path}")
    except Exception as e:
        result["errors"].append(f"Template building failed: {e}")
        log.error(f"[{tid}] build_quote_template error: {traceback.format_exc()}")
        return result

    # Step 4: Generate quote
    log.info(f"[{tid}] Generating quote...")
    output_filename = f"{tid}_generated.docx"
    try:
        gen_result = DocumentFactory.generate_from_template(
            template_bytes,
            t["quote_data"],
            brand_dna,
            output_filename,
        )
        src = Path(gen_result["filepath"])
        dst = GENERATED_DIR / f"{tid}_generated.docx"
        shutil.copy2(str(src), str(dst))
        result["generated_path"] = dst
        result["gen_financials"] = {
            "subtotal": gen_result["subtotal"],
            "tax_amount": gen_result["tax_amount"],
            "total": gen_result["total"],
        }
        log.info(f"[{tid}] Quote generated: {dst}  subtotal={gen_result['subtotal']:.2f}")
    except Exception as e:
        result["errors"].append(f"Quote generation failed: {e}")
        log.error(f"[{tid}] generate_from_template error: {traceback.format_exc()}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def extract_docx_text(path: Path) -> str:
    """Extract all text from a DOCX file."""
    try:
        doc = Document(str(path))
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text.strip())
        return "\n".join(parts)
    except Exception as e:
        return f"[TEXT EXTRACTION FAILED: {e}]"


_JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_BRACKET_RE = re.compile(r"\[.+?\]")


def score_placeholder_accuracy(text: str) -> tuple[int, list[str]]:
    """Score 0-10: check for unfilled Jinja2 or bracket placeholders."""
    issues = []
    jinja_hits = _JINJA_RE.findall(text)
    bracket_hits = [m for m in _BRACKET_RE.findall(text) if len(m) > 3]

    for hit in jinja_hits:
        issues.append(f"Unfilled Jinja2 tag: `{hit}`")
    for hit in bracket_hits:
        issues.append(f"Remaining bracket placeholder: `{hit}`")

    total_issues = len(jinja_hits) + len(bracket_hits)
    score = max(0, 10 - total_issues * 2)
    return score, issues


def score_line_items(text: str, quote_data: dict, sym: str) -> tuple[int, list[str]]:
    """Score 0-10: check all expected line items appear in the generated text."""
    issues = []
    line_items = quote_data.get("line_items", [])
    found = 0

    for item in line_items:
        desc = item.get("description", "")
        # Check for at least the first 20 chars of description
        needle = desc[:20].lower()
        if needle and needle in text.lower():
            found += 1
        else:
            issues.append(f"Line item description not found: '{desc[:40]}'")

    if not line_items:
        return 5, ["No line items in test data"]

    ratio = found / len(line_items)
    score = round(ratio * 10)
    if found == len(line_items):
        issues = []
    return score, issues


def score_calculations(
    text: str, quote_data: dict, tax_rate: float, sym: str
) -> tuple[int, list[str]]:
    """Score 0-10: verify subtotal, tax, and total appear correctly in the text."""
    issues = []
    items = quote_data.get("line_items", [])
    subtotal = sum(float(i.get("quantity", 1)) * float(i.get("unit_price", 0)) for i in items)
    tax_amount = subtotal * (tax_rate / 100)
    grand_total = subtotal + tax_amount

    def _fmt(amount: float) -> str:
        return f"{sym}{amount:,.2f}"

    checks = [
        (_fmt(subtotal), "subtotal"),
        (_fmt(grand_total), "grand total"),
    ]
    if tax_rate > 0:
        checks.append((_fmt(tax_amount), "tax amount"))

    found = 0
    for val_str, label in checks:
        # Strip currency symbol for a fallback match (handles multi-char symbols like A$)
        bare = val_str.lstrip("A$C$NZ$HK$S$R$£€¥₹")
        if val_str in text or bare in text:
            found += 1
        else:
            issues.append(f"Expected {label} {val_str!r} not found in output")

    score = round((found / len(checks)) * 10)
    return score, issues


def score_template_fidelity(text: str, brand_dna: dict, t: dict) -> tuple[int, list[str]]:
    """Score 0-10: verify template business identity is preserved in the output."""
    issues = []
    checks = [
        (t["business_name"], "business name"),
        (t.get("business_address", "").split(",")[0], "business address (first part)"),
    ]

    found = 0
    for needle, label in checks:
        if needle and needle.lower() in text.lower():
            found += 1
        else:
            issues.append(f"Template identity field not found — {label}: '{needle}'")

    # Check customer name was injected
    cust = t["quote_data"]["customer_name"]
    if cust.lower() in text.lower():
        found += 1
    else:
        issues.append(f"Customer name not injected: '{cust}'")

    score = round((found / 3) * 10)
    return score, issues


def score_client_readiness_gemini(
    blank_text: str, generated_text: str, template_id: str
) -> tuple[int, str]:
    """Score 0-10 via Gemini qualitative review of the generated quote."""
    prompt = f"""You are reviewing a generated business quote document to assess whether it is ready to send to a client.

Template ID: {template_id}

--- Original blank template (business identity only) ---
{blank_text[:1500]}

--- Generated quote output ---
{generated_text[:2500]}

Assess the generated quote on:
1. Professional appearance (readable, complete sentences, no raw placeholders)
2. Completeness (header, line items, totals, payment details all present)
3. Accuracy (customer name present, figures look plausible)
4. Client-readiness (could this be sent to a real client without embarrassment?)

Respond ONLY with valid JSON:
{{"score": <0-10>, "reasoning": "<2-3 sentence summary>", "issues": ["<issue1>", "<issue2>"]}}

Return an empty "issues" array if none found. Do not wrap in code fences."""

    try:
        from google.genai import types as _types
        resp = _gemini_client.models.generate_content(
            model=ANALYSIS_MODEL,
            contents=prompt,
            config=_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = resp.text or ""
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
        data = json.loads(raw)
        return int(data.get("score", 5)), data.get("reasoning", ""), data.get("issues", [])
    except Exception as e:
        log.warning(f"Gemini client readiness scoring failed for {template_id}: {e}")
        return 5, f"Scoring error: {e}", []


def analyze_result(result: dict) -> dict:
    """Run all scoring dimensions on a completed pipeline result."""
    t = result["config"]
    sym = _sym(t["currency"])
    tax_rate = t["tax_rate"]
    brand_dna = result.get("brand_dna") or {}

    analysis = {
        "id": result["id"],
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "scores": {},
        "issues_by_dim": {},
    }

    if result.get("generated_path"):
        gen_text = extract_docx_text(result["generated_path"])
    else:
        analysis["scores"] = {d: 0 for d in ["placeholder", "line_items", "calculations", "fidelity", "client_readiness"]}
        analysis["issues_by_dim"]["pipeline"] = result.get("errors", ["Pipeline did not complete"])
        return analysis

    blank_text = extract_docx_text(result["blank_path"]) if result.get("blank_path") else ""

    s1, i1 = score_placeholder_accuracy(gen_text)
    s2, i2 = score_line_items(gen_text, t["quote_data"], sym)
    s3, i3 = score_calculations(gen_text, t["quote_data"], tax_rate, sym)
    s4, i4 = score_template_fidelity(gen_text, brand_dna, t)
    s5, reasoning5, i5 = score_client_readiness_gemini(blank_text, gen_text, t["id"])

    analysis["scores"] = {
        "placeholder_accuracy": s1,
        "line_items_integrity": s2,
        "calculation_accuracy": s3,
        "template_fidelity": s4,
        "client_readiness": s5,
        "total": s1 + s2 + s3 + s4 + s5,
    }
    analysis["issues_by_dim"] = {
        "placeholder_accuracy": i1,
        "line_items_integrity": i2,
        "calculation_accuracy": i3,
        "template_fidelity": i4,
        "client_readiness": i5,
    }
    analysis["client_readiness_reasoning"] = reasoning5
    return analysis


# ─────────────────────────────────────────────────────────────────────────────
# REPORT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def write_report(results: list[dict], analyses: list[dict], run_date: str):
    """Write test_results/quote_test_analysis.md"""
    report_path = RESULTS_DIR / "quote_test_analysis.md"

    dim_keys = ["placeholder_accuracy", "line_items_integrity", "calculation_accuracy", "template_fidelity", "client_readiness"]
    dim_labels = {
        "placeholder_accuracy": "Placeholder Accuracy",
        "line_items_integrity": "Line Items Integrity",
        "calculation_accuracy": "Calculation Accuracy",
        "template_fidelity": "Template Fidelity",
        "client_readiness": "Client Readiness",
    }

    lines = []
    lines.append(f"# Quote Generation Test Results — {run_date}\n")
    lines.append(f"**Templates tested:** {len(results)}  |  **Run date:** {run_date}\n")

    # ── Summary table ────────────────────────────────────────────────────────
    lines.append("## Summary\n")
    header = "| Template | " + " | ".join(dim_labels[k][:4] + "." for k in dim_keys) + " | **Total /50** | Status |"
    sep = "|---|" + "---|" * len(dim_keys) + "---|---|"
    lines.append(header)
    lines.append(sep)

    all_issues = []

    for analysis in analyses:
        tid = analysis["id"]
        scores = analysis.get("scores", {})
        total = scores.get("total", 0)
        dims = " | ".join(str(scores.get(k, "–")) for k in dim_keys)
        status = "✅ PASS" if total >= 35 else ("⚠️ WARN" if total >= 20 else "❌ FAIL")
        if analysis.get("errors"):
            status = "💥 ERROR"
            total = 0
        lines.append(f"| `{tid}` | {dims} | **{total}** | {status} |")

        for dim, issues in analysis.get("issues_by_dim", {}).items():
            for issue in issues:
                all_issues.append((tid, dim_labels.get(dim, dim), issue))

    lines.append("")

    # ── Dimension descriptions ────────────────────────────────────────────────
    lines.append("### Scoring Dimensions\n")
    lines.append("| Dimension | What is measured |")
    lines.append("|---|---|")
    lines.append("| Placeholder Accuracy | No `{{ }}` Jinja2 or `[bracket]` placeholders remain |")
    lines.append("| Line Items Integrity | All requested line item descriptions appear in the output |")
    lines.append("| Calculation Accuracy | Subtotal, tax, and total figures are mathematically correct |")
    lines.append("| Template Fidelity | Business identity (name, address) and customer name are present |")
    lines.append("| Client Readiness | Gemini qualitative review — is this ready to send? |")
    lines.append("")

    # ── Per-template sections ─────────────────────────────────────────────────
    lines.append("## Per-Template Detail\n")

    for result, analysis in zip(results, analyses):
        t = result["config"]
        tid = t["id"]
        scores = analysis.get("scores", {})
        total = scores.get("total", 0)

        lines.append(f"### {tid}")
        lines.append(f"**Business:** {t['business_name']}  |  **Currency:** {t['currency']}  |  **Tax:** {t['tax_rate']}%  |  **Columns:** {', '.join(t['columns'])}\n")

        if analysis.get("errors"):
            lines.append(f"**Pipeline Errors:**")
            for e in analysis["errors"]:
                lines.append(f"- ❌ {e}")
            lines.append("")
            continue

        lines.append(f"**Total Score: {total}/50**\n")
        lines.append("| Dimension | Score | Issues |")
        lines.append("|---|---|---|")

        for k in dim_keys:
            s = scores.get(k, "–")
            issues = analysis.get("issues_by_dim", {}).get(k, [])
            issue_str = "; ".join(issues[:2]) if issues else "None"
            if len(issues) > 2:
                issue_str += f" (+{len(issues)-2} more)"
            lines.append(f"| {dim_labels[k]} | {s}/10 | {issue_str} |")

        if analysis.get("client_readiness_reasoning"):
            lines.append(f"\n**Client Readiness Note:** {analysis['client_readiness_reasoning']}")

        lines.append("")

    # ── Aggregated issues ─────────────────────────────────────────────────────
    lines.append("## All Issues Found\n")
    if all_issues:
        lines.append("| Template | Dimension | Issue |")
        lines.append("|---|---|---|")
        for tid, dim, issue in all_issues:
            lines.append(f"| `{tid}` | {dim} | {issue} |")
    else:
        lines.append("No issues found.")
    lines.append("")

    # ── Recommended fixes ─────────────────────────────────────────────────────
    lines.append("## Recommended Fixes & Next Steps\n")

    # Aggregate issues by dimension
    dim_issue_map: dict[str, list[tuple[str, str]]] = {}
    for tid, dim, issue in all_issues:
        dim_issue_map.setdefault(dim, []).append((tid, issue))

    if not dim_issue_map:
        lines.append("All tests passed with no issues. No changes recommended at this time.")
    else:
        for dim, items in dim_issue_map.items():
            lines.append(f"### {dim}")
            seen = set()
            for tid, issue in items:
                if issue not in seen:
                    lines.append(f"- **[{tid}]** {issue}")
                    seen.add(issue)
            lines.append("")

    lines.append("---")
    lines.append(f"*Generated by `test_runner.py` on {run_date}*")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Report written: {report_path}")
    return report_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    log.info(f"=== Quote Generation Test Suite — {run_date} ===")
    log.info(f"Templates: {TEMPLATES_DIR}  |  Generated: {GENERATED_DIR}  |  Results: {RESULTS_DIR}")

    results = []
    analyses = []

    for i, t in enumerate(TEMPLATES, 1):
        log.info(f"\n{'='*60}")
        log.info(f"[{i}/{len(TEMPLATES)}] Running: {t['id']} ({t['business_name']})")
        log.info(f"{'='*60}")
        result = run_pipeline(t)
        results.append(result)

    log.info(f"\n{'='*60}")
    log.info("Pipeline complete. Running analysis...")
    log.info(f"{'='*60}\n")

    for result in results:
        log.info(f"Analysing: {result['id']}...")
        analysis = analyze_result(result)
        analyses.append(analysis)
        total = analysis.get("scores", {}).get("total", "n/a")
        errors = len(analysis.get("errors", []))
        log.info(f"  → Score: {total}/50  |  Errors: {errors}")

    report_path = write_report(results, analyses, run_date)

    # Print summary to console
    print(f"\n{'='*60}")
    print(f"TEST RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Template':<25} {'Total':>6}  Status")
    print(f"{'-'*45}")
    for analysis in analyses:
        tid = analysis["id"]
        total = analysis.get("scores", {}).get("total", 0)
        if analysis.get("errors"):
            status = "ERROR"
        elif total >= 35:
            status = "PASS"
        elif total >= 20:
            status = "WARN"
        else:
            status = "FAIL"
        print(f"{tid:<25} {total:>5}/50  {status}")
    print(f"\nReport: {report_path.absolute()}")


if __name__ == "__main__":
    main()
