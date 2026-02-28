import os
from docx import Document
import xlsxwriter
import logging

logger = logging.getLogger(__name__)

# Ensure output directory exists
OUTPUT_DIR = "generated_documents"
os.makedirs(OUTPUT_DIR, exist_ok=True)

from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

class DocumentFactory:
    """Handles generation of specific document types based on user preferences."""

    @staticmethod
    def generate_docx(quote_data: dict, brand_dna: dict, output_filename: str) -> str:
        """Generates a Microsoft Word document (.docx) using Brand DNA."""
        filepath = os.path.join(OUTPUT_DIR, output_filename)
        document = Document()
        
        # 1. Add Brand Header
        b_name = brand_dna.get("business_name") or "Your Business Name"
        header = document.add_heading(b_name.upper(), 0)
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 2. Add Company Details
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
        
        # 3. Add Customer Details
        cust_para = document.add_paragraph()
        cust_para.add_run(f"Prepared For: {quote_data.get('customer_name', 'Customer')}\n").bold = True
        if quote_data.get('customer_address'):
            cust_para.add_run(f"Address: {quote_data.get('customer_address')}\n")
            
        currency = brand_dna.get("currency") or "USD"
        cust_para.add_run(f"Currency: {currency}")

        # 4. Add Line Items Table
        line_items = quote_data.get('line_items', [])
        subtotal = 0.0
        if line_items:
            table = document.add_table(rows=1, cols=4)
            table.style = 'Light Shading Accent 1' # Try to use a nice Word style
            
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Description'
            hdr_cells[1].text = 'Qty'
            hdr_cells[2].text = 'Unit Price'
            hdr_cells[3].text = 'Total'
            
            for item in line_items:
                row_cells = table.add_row().cells
                desc = item.get('description', '')
                qty = float(item.get('quantity', 1))
                price = float(item.get('unit_price', 0.0))
                total = qty * price
                subtotal += total
                
                row_cells[0].text = desc
                row_cells[1].text = str(qty)
                row_cells[2].text = f"{price:.2f}"
                row_cells[3].text = f"{total:.2f}"

        # 5. Add Totals
        document.add_paragraph("\n")
        totals_para = document.add_paragraph()
        totals_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        totals_para.add_run(f"Subtotal: {subtotal:.2f}\n")
        
        # Super basic tax logic if there was a mention of it, but defaulting to 0 for now since Gemini didn't return a strict tax rate %
        # In a real app we'd parse the brand_dna "calculation_methods" deeper
        totals_para.add_run(f"TOTAL: {subtotal:.2f}").bold = True

        # 6. Add Footer
        if brand_dna.get("calculation_methods") or brand_dna.get("layout_preferences"):
            footer = document.add_paragraph("\nNotes:")
            if brand_dna.get("calculation_methods"):
                document.add_paragraph(str(brand_dna["calculation_methods"]), style='Intense Quote')

        document.save(filepath)
        logger.info(f"Generated DOCX: {filepath}")
        return filepath

    @staticmethod
    def generate_xlsx(quote_data: dict, output_filename: str) -> str:
        """Generates a Microsoft Excel document (.xlsx)."""
        filepath = os.path.join(OUTPUT_DIR, output_filename)
        workbook = xlsxwriter.Workbook(filepath)
        worksheet = workbook.add_worksheet()
        
        # Simple scaffold for xlsx generation
        worksheet.write('A1', f"Quote for {quote_data.get('customer_name', 'Customer')}")
        worksheet.write('A2', f"Address: {quote_data.get('customer_address', 'N/A')}")
        
        worksheet.write('A4', 'Description')
        worksheet.write('B4', 'Quantity')
        worksheet.write('C4', 'Unit Price')
        
        row = 4
        line_items = quote_data.get('line_items', [])
        for item in line_items:
            worksheet.write(row, 0, item.get('description', ''))
            worksheet.write(row, 1, item.get('quantity', 0))
            worksheet.write(row, 2, item.get('unit_price', 0.0))
            row += 1

        workbook.close()
        logger.info(f"Generated XLSX: {filepath}")
        return filepath
