import os
import re
import logging
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import xlsxwriter

logger = logging.getLogger(__name__)

OUTPUT_DIR = "generated_documents"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _extract_tax_rate(brand_dna: dict) -> float:
    """Extracts a numeric tax rate percentage from brand DNA fields."""
    calc = brand_dna.get("calculation_methods")
    if isinstance(calc, dict):
        for key in ("tax_rate", "vat_rate", "gst_rate"):
            rate = calc.get(key)
            if rate is not None:
                try:
                    return float(rate)
                except (ValueError, TypeError):
                    pass

    vat_status = brand_dna.get("vat_tax_status") or ""
    if isinstance(vat_status, str):
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', vat_status)
        if match:
            return float(match.group(1))

    return 0.0


class DocumentFactory:
    """Handles generation of specific document types based on user preferences."""

    @staticmethod
    def generate_docx(quote_data: dict, brand_dna: dict, output_filename: str) -> dict:
        """
        Generates a Microsoft Word document (.docx) using Brand DNA.
        Returns a dict: {"filepath": str, "subtotal": float, "tax_amount": float, "total": float}
        """
        filepath = os.path.join(OUTPUT_DIR, output_filename)
        document = Document()

        currency = quote_data.get("currency") or brand_dna.get("currency") or "USD"

        # 1. Brand Header
        b_name = brand_dna.get("business_name") or "Your Business Name"
        header = document.add_heading(b_name.upper(), 0)
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 2. Company Details
        company_info = document.add_paragraph()
        company_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if brand_dna.get("business_address"):
            company_info.add_run(f"{brand_dna['business_address']}\n")
        if brand_dna.get("contact_details"):
            company_info.add_run(f"{brand_dna['contact_details']}\n")
        if brand_dna.get("vat_tax_status"):
            company_info.add_run(f"{brand_dna['vat_tax_status']}\n")
        if brand_dna.get("bank_info"):
            company_info.add_run(f"Bank: {brand_dna['bank_info']}")

        document.add_heading('QUOTATION', level=1)

        # 3. Customer Details
        cust_para = document.add_paragraph()
        cust_para.add_run(f"Prepared For: {quote_data.get('customer_name', 'Customer')}\n").bold = True
        if quote_data.get('customer_address'):
            cust_para.add_run(f"Address: {quote_data.get('customer_address')}\n")
        cust_para.add_run(f"Currency: {currency}")

        # 4. Line Items Table
        line_items = quote_data.get('line_items', [])
        subtotal = 0.0
        if line_items:
            table = document.add_table(rows=1, cols=4)
            table.style = 'Light Shading Accent 1'

            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Description'
            hdr_cells[1].text = 'Qty'
            hdr_cells[2].text = f'Unit Price ({currency})'
            hdr_cells[3].text = f'Total ({currency})'

            for item in line_items:
                row_cells = table.add_row().cells
                desc = item.get('description', '')
                qty = float(item.get('quantity', 1))
                price = float(item.get('unit_price', 0.0))
                total = qty * price
                subtotal += total

                row_cells[0].text = desc
                row_cells[1].text = f"{qty:.0f}"
                row_cells[2].text = f"{price:.2f}"
                row_cells[3].text = f"{total:.2f}"

        # 5. Totals
        document.add_paragraph("\n")
        totals_para = document.add_paragraph()
        totals_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        tax_rate = _extract_tax_rate(brand_dna)
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount

        totals_para.add_run(f"Subtotal: {currency} {subtotal:.2f}\n")
        if tax_rate > 0:
            totals_para.add_run(f"VAT/Tax ({tax_rate:.0f}%): {currency} {tax_amount:.2f}\n")
        totals_para.add_run(f"TOTAL: {currency} {total:.2f}").bold = True

        # 6. Footer Notes
        if brand_dna.get("calculation_methods") or brand_dna.get("layout_preferences"):
            document.add_paragraph("\nNotes:")
            if brand_dna.get("calculation_methods"):
                calc = brand_dna["calculation_methods"]
                if isinstance(calc, dict):
                    notes = ", ".join(f"{k}: {v}" for k, v in calc.items() if k != "tax_rate")
                    if notes:
                        document.add_paragraph(notes, style='Intense Quote')
                elif isinstance(calc, str):
                    document.add_paragraph(calc, style='Intense Quote')

        document.save(filepath)
        logger.info(f"Generated DOCX: {filepath}")
        return {"filepath": filepath, "subtotal": subtotal, "tax_amount": tax_amount, "total": total}

    @staticmethod
    def generate_xlsx(quote_data: dict, brand_dna: dict, output_filename: str) -> dict:
        """
        Generates a Microsoft Excel document (.xlsx) using Brand DNA.
        Returns a dict: {"filepath": str, "subtotal": float, "tax_amount": float, "total": float}
        """
        filepath = os.path.join(OUTPUT_DIR, output_filename)
        currency = quote_data.get("currency") or brand_dna.get("currency") or "USD"
        b_name = brand_dna.get("business_name") or "Your Business Name"

        workbook = xlsxwriter.Workbook(filepath)
        worksheet = workbook.add_worksheet("Quote")

        # Formats
        bold = workbook.add_format({'bold': True})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        money_fmt = workbook.add_format({'num_format': f'#,##0.00', 'border': 1})
        total_fmt = workbook.add_format({'bold': True, 'num_format': f'#,##0.00', 'bg_color': '#E2EFDA'})

        # Column widths
        worksheet.set_column('A:A', 40)
        worksheet.set_column('B:B', 10)
        worksheet.set_column('C:D', 16)

        row = 0

        # Business header
        worksheet.write(row, 0, b_name.upper(), bold)
        row += 1
        if brand_dna.get("business_address"):
            worksheet.write(row, 0, brand_dna["business_address"])
            row += 1
        if brand_dna.get("contact_details"):
            worksheet.write(row, 0, brand_dna["contact_details"])
            row += 1
        if brand_dna.get("vat_tax_status"):
            worksheet.write(row, 0, brand_dna["vat_tax_status"])
            row += 1
        row += 1

        # Quote heading
        worksheet.write(row, 0, "QUOTATION", bold)
        row += 1

        # Customer details
        worksheet.write(row, 0, f"Prepared For: {quote_data.get('customer_name', 'Customer')}", bold)
        row += 1
        if quote_data.get("customer_address"):
            worksheet.write(row, 0, f"Address: {quote_data['customer_address']}")
            row += 1
        row += 1

        # Table headers
        worksheet.write(row, 0, 'Description', header_fmt)
        worksheet.write(row, 1, 'Qty', header_fmt)
        worksheet.write(row, 2, f'Unit Price ({currency})', header_fmt)
        worksheet.write(row, 3, f'Total ({currency})', header_fmt)
        row += 1

        # Line items
        subtotal = 0.0
        for item in quote_data.get('line_items', []):
            desc = item.get('description', '')
            qty = float(item.get('quantity', 1))
            price = float(item.get('unit_price', 0.0))
            total_line = qty * price
            subtotal += total_line

            worksheet.write(row, 0, desc)
            worksheet.write(row, 1, qty)
            worksheet.write_number(row, 2, price, money_fmt)
            worksheet.write_number(row, 3, total_line, money_fmt)
            row += 1

        row += 1

        # Totals
        tax_rate = _extract_tax_rate(brand_dna)
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount

        worksheet.write(row, 2, "Subtotal:", bold)
        worksheet.write_number(row, 3, subtotal, total_fmt)
        row += 1

        if tax_rate > 0:
            worksheet.write(row, 2, f"VAT/Tax ({tax_rate:.0f}%):", bold)
            worksheet.write_number(row, 3, tax_amount, total_fmt)
            row += 1

        worksheet.write(row, 2, "TOTAL:", bold)
        worksheet.write_number(row, 3, total, total_fmt)

        workbook.close()
        logger.info(f"Generated XLSX: {filepath}")
        return {"filepath": filepath, "subtotal": subtotal, "tax_amount": tax_amount, "total": total}
