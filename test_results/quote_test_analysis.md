# Quote Generation Test Results — 2026-05-21 09:26

**Templates tested:** 10  |  **Run date:** 2026-05-21 09:26

## Summary

| Template | Plac. | Line. | Calc. | Temp. | Clie. | **Total /50** | Status |
|---|---|---|---|---|---|---|---|
| `01_aura_design` | 10 | 10 | 10 | 10 | 8 | **48** | ✅ PASS |
| `02_global_steel` | 10 | 10 | 7 | 7 | 1 | **35** | ✅ PASS |
| `03_azure_estate` | 10 | 10 | 7 | 10 | 1 | **38** | ✅ PASS |
| `04_quick_handyman` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `05_vet_clinic` | 10 | 10 | 7 | 7 | 2 | **36** | ✅ PASS |
| `06_solar_rebate` | – | – | – | – | 0 | **0** | 💥 ERROR |
| `07_move_easy` | 10 | 10 | 0 | 7 | 2 | **29** | ⚠️ WARN |
| `08_code_crafters` | 10 | 10 | 7 | 10 | 2 | **39** | ✅ PASS |
| `09_gourmet_catering` | 10 | 10 | 10 | 10 | 4 | **44** | ✅ PASS |
| `10_fit_pro` | 10 | 10 | 10 | 7 | 2 | **39** | ✅ PASS |

### Scoring Dimensions

| Dimension | What is measured |
|---|---|
| Placeholder Accuracy | No `{{ }}` Jinja2 or `[bracket]` placeholders remain |
| Line Items Integrity | All requested line item descriptions appear in the output |
| Calculation Accuracy | Subtotal, tax, and total figures are mathematically correct |
| Template Fidelity | Business identity (name, address) and customer name are present |
| Client Readiness | Gemini qualitative review — is this ready to send? |

## Per-Template Detail

### 01_aura_design
**Business:** Aura Design Studio  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `brackets`  |  **Columns:** Project Item, Amount

**Total Score: 48/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 8/10 | Lack of comprehensive payment details (e.g., bank transfer instructions, accepted payment methods).; Terms & Conditions are minimal and do not include typical clauses like payment terms or project scope details. |

**Client Readiness Note:** The generated quote is professionally presented, accurately fills all template placeholders, and includes correct calculations and dates. However, it lacks comprehensive payment instructions and more detailed terms and conditions, which are typically essential for a truly client-ready business quote.

### 02_global_steel
**Business:** Global Steel & Supply Corp  |  **Currency:** USD  |  **Tax:** 7.0%  |  **Field Style:** `labels`  |  **Columns:** Part No, Description, Qty, Weight (lbs), Unit Price, Subtotal

**Total Score: 35/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected grand total '$17,066.50' not found in output |
| Template Fidelity | 7/10 | Customer name not injected: 'Midwest Bridge Builders' |
| Client Readiness | 1/10 | Missing 'BILL TO:' section details.; Missing 'TERMS & CONDITIONS:'. (+3 more) |

**Client Readiness Note:** The quote is critically incomplete and contains significant errors. Key sections like 'BILL TO' and 'TERMS & CONDITIONS' are blank, and the 'Weight (lbs)' column is entirely missing data. Most importantly, the final 'TOTAL AMOUNT' is incorrectly calculated, making this document entirely unsuitable for client-facing use.

### 03_azure_estate
**Business:** The Azure Estate  |  **Currency:** USD  |  **Tax:** 18.0%  |  **Field Style:** `sample`  |  **Columns:** Service Category, Description, Investment

**Total Score: 38/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected grand total '$25,960.00' not found in output |
| Template Fidelity | 10/10 | None |
| Client Readiness | 1/10 | Missing 'Service Category' values for each line item, which are replaced by description text.; Missing 'Investment' values for individual service line items. (+2 more) |

**Client Readiness Note:** The quote has critical missing information, specifically individual line item investment amounts and service categories, making the subtotal unverifiable. Additionally, the grand total calculation is incorrect, rendering the document unprofessional and not client-ready.

### 04_quick_handyman
**Business:** Quick Fix Handyman Services  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Field Style:** `brackets`  |  **Columns:** Job Description, Price

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professionally presented, complete, and accurate. All template placeholders have been correctly filled, figures are plausible and correctly summed, and the document is ready for client delivery.

### 05_vet_clinic
**Business:** Happy Paws Veterinary Clinic  |  **Currency:** AUD  |  **Tax:** 10.0%  |  **Field Style:** `labels`  |  **Columns:** Procedure / Item, Qty, Cost (inc GST)

**Total Score: 36/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected subtotal 'A$505.00' not found in output |
| Template Fidelity | 7/10 | Customer name not injected: 'Sarah Miller (Pet: Luna)' |
| Client Readiness | 2/10 | Missing "BILL TO:" information (client name/address); Missing "TERMS & CONDITIONS:" content (+2 more) |

**Client Readiness Note:** The quote is incomplete, missing crucial client billing details, terms and conditions, and individual item costs. While the header and total calculations are present, the lack of itemized pricing and key contractual information makes it unusable for a client.

### 06_solar_rebate
**Business:** Eco-Power Solar Solutions  |  **Currency:** AUD  |  **Tax:** 0.0%  |  **Field Style:** `sample`  |  **Columns:** System Component, Qty, Price

**Pipeline Errors:**
- ❌ build_quote_template returned None

### 07_move_easy
**Business:** Move Easy Logisitics  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Field Style:** `labels`  |  **Columns:** Service Description, Volume (cu.ft), Rate/cu.ft, Total

**Total Score: 29/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 0/10 | Expected subtotal '$6,500.00' not found in output; Expected grand total '$6,500.00' not found in output |
| Template Fidelity | 7/10 | Customer name not injected: 'Robert Henderson' |
| Client Readiness | 2/10 | "BILL TO:" section is blank, missing customer information.; "TERMS & CONDITIONS:" section is blank, omitting vital contractual details. (+3 more) |

**Client Readiness Note:** The generated quote is significantly incomplete and contains multiple formatting errors, making it unsuitable for client delivery. Crucial sections like 'BILL TO:' and 'TERMS & CONDITIONS:' are entirely blank, and several line item details are missing or incorrectly displayed.

### 08_code_crafters
**Business:** Code Crafters Software  |  **Currency:** EUR  |  **Tax:** 19.0%  |  **Field Style:** `brackets`  |  **Columns:** Software Service, Seats, Monthly Fee, Yearly Total

**Total Score: 39/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected grand total '€18,921.00' not found in output |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Missing 'Seats' quantity for all line items.; Incorrect 'Monthly Fee' values in line items; they appear to be annual totals or miscalculated figures instead of monthly fees. (+1 more) |

**Client Readiness Note:** The generated quote contains critical errors, including missing 'Seats' quantities, incorrect 'Monthly Fee' values in line items, and a mathematically incorrect final 'TOTAL COST'. These fundamental inaccuracies make the document unprofessional and unsuitable for client delivery.

### 09_gourmet_catering
**Business:** Gourmet Garden Catering  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `sample`  |  **Columns:** Item Description, Price Per Head, Quantity, Total

**Total Score: 44/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 4/10 | Missing value for 'Staffing Fee'.; 'TOTAL QUOTE' does not include a Staffing Fee, making it potentially incorrect. |

**Client Readiness Note:** The quote has a professional appearance with correctly calculated line items and subtotal. However, a critical "Staffing Fee" value is completely missing, rendering the overall "TOTAL QUOTE" incomplete and likely inaccurate. This significant financial omission makes the document unsuitable for client delivery.

### 10_fit_pro
**Business:** FitPro Personal Training  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `labels`  |  **Columns:** Training Package, Cost

**Total Score: 39/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 7/10 | Customer name not injected: 'Mark Stevens' |
| Client Readiness | 2/10 | Missing 'BILL TO:' information.; Missing 'TERMS & CONDITIONS:' content. (+3 more) |

**Client Readiness Note:** The generated quote is significantly incomplete and inaccurate. Key client details ('BILL TO:'), terms and conditions, and individual line item costs are missing. A new item was added without adjusting the total, making the financial summary incorrect and the quote unsuitable for client review.

## All Issues Found

| Template | Dimension | Issue |
|---|---|---|
| `01_aura_design` | Client Readiness | Lack of comprehensive payment details (e.g., bank transfer instructions, accepted payment methods). |
| `01_aura_design` | Client Readiness | Terms & Conditions are minimal and do not include typical clauses like payment terms or project scope details. |
| `02_global_steel` | Calculation Accuracy | Expected grand total '$17,066.50' not found in output |
| `02_global_steel` | Template Fidelity | Customer name not injected: 'Midwest Bridge Builders' |
| `02_global_steel` | Client Readiness | Missing 'BILL TO:' section details. |
| `02_global_steel` | Client Readiness | Missing 'TERMS & CONDITIONS:'. |
| `02_global_steel` | Client Readiness | The 'Weight (lbs)' column is empty for all line items. |
| `02_global_steel` | Client Readiness | The 'TOTAL AMOUNT' is incorrectly calculated based on the subtotal and sales tax. |
| `02_global_steel` | Client Readiness | Product descriptions are truncated, omitting important specifications like '(H-Section)' and '(Grade 60)'. |
| `03_azure_estate` | Calculation Accuracy | Expected grand total '$25,960.00' not found in output |
| `03_azure_estate` | Client Readiness | Missing 'Service Category' values for each line item, which are replaced by description text. |
| `03_azure_estate` | Client Readiness | Missing 'Investment' values for individual service line items. |
| `03_azure_estate` | Client Readiness | The 'GRAND TOTAL' calculation is incorrect based on the provided subtotal and service charge. |
| `03_azure_estate` | Client Readiness | The subtotal of $22,000.00 cannot be verified without individual line item investments. |
| `05_vet_clinic` | Calculation Accuracy | Expected subtotal 'A$505.00' not found in output |
| `05_vet_clinic` | Template Fidelity | Customer name not injected: 'Sarah Miller (Pet: Luna)' |
| `05_vet_clinic` | Client Readiness | Missing "BILL TO:" information (client name/address) |
| `05_vet_clinic` | Client Readiness | Missing "TERMS & CONDITIONS:" content |
| `05_vet_clinic` | Client Readiness | Individual line item costs are not displayed in the 'Cost (inc GST)' column |
| `05_vet_clinic` | Client Readiness | The document retains blank template sections, making it unprofessional. |
| `06_solar_rebate` | pipeline | build_quote_template returned None |
| `07_move_easy` | Calculation Accuracy | Expected subtotal '$6,500.00' not found in output |
| `07_move_easy` | Calculation Accuracy | Expected grand total '$6,500.00' not found in output |
| `07_move_easy` | Template Fidelity | Customer name not injected: 'Robert Henderson' |
| `07_move_easy` | Client Readiness | "BILL TO:" section is blank, missing customer information. |
| `07_move_easy` | Client Readiness | "TERMS & CONDITIONS:" section is blank, omitting vital contractual details. |
| `07_move_easy` | Client Readiness | Volume and Rate/cu.ft values are missing for "Residential Move - 3 Bedroom House". |
| `07_move_easy` | Client Readiness | Line items "Packing & Unpacking Services (Flat Rate)" and "Full Insurance Coverage (Up to $50k)" display duplicate amounts in the 'Rate/cu.ft' and 'Total' columns, indicating incorrect data mapping. |
| `07_move_easy` | Client Readiness | The amount for "Fuel Surcharge (10%)" is missing from the line item detail. |
| `08_code_crafters` | Calculation Accuracy | Expected grand total '€18,921.00' not found in output |
| `08_code_crafters` | Client Readiness | Missing 'Seats' quantity for all line items. |
| `08_code_crafters` | Client Readiness | Incorrect 'Monthly Fee' values in line items; they appear to be annual totals or miscalculated figures instead of monthly fees. |
| `08_code_crafters` | Client Readiness | Final 'TOTAL COST' is mathematically incorrect based on the subtotal and VAT provided. |
| `09_gourmet_catering` | Client Readiness | Missing value for 'Staffing Fee'. |
| `09_gourmet_catering` | Client Readiness | 'TOTAL QUOTE' does not include a Staffing Fee, making it potentially incorrect. |
| `10_fit_pro` | Template Fidelity | Customer name not injected: 'Mark Stevens' |
| `10_fit_pro` | Client Readiness | Missing 'BILL TO:' information. |
| `10_fit_pro` | Client Readiness | Missing 'TERMS & CONDITIONS:' content. |
| `10_fit_pro` | Client Readiness | Missing individual costs for 'Training Package' line items. |
| `10_fit_pro` | Client Readiness | Inaccurate 'TOTAL' as 'FitPro T-Shirt & Water Bottle' was added without its cost or updating the sum. |
| `10_fit_pro` | Client Readiness | Missing 'Membership #'. |

## Recommended Fixes & Next Steps

### Client Readiness
- **[01_aura_design]** Lack of comprehensive payment details (e.g., bank transfer instructions, accepted payment methods).
- **[01_aura_design]** Terms & Conditions are minimal and do not include typical clauses like payment terms or project scope details.
- **[02_global_steel]** Missing 'BILL TO:' section details.
- **[02_global_steel]** Missing 'TERMS & CONDITIONS:'.
- **[02_global_steel]** The 'Weight (lbs)' column is empty for all line items.
- **[02_global_steel]** The 'TOTAL AMOUNT' is incorrectly calculated based on the subtotal and sales tax.
- **[02_global_steel]** Product descriptions are truncated, omitting important specifications like '(H-Section)' and '(Grade 60)'.
- **[03_azure_estate]** Missing 'Service Category' values for each line item, which are replaced by description text.
- **[03_azure_estate]** Missing 'Investment' values for individual service line items.
- **[03_azure_estate]** The 'GRAND TOTAL' calculation is incorrect based on the provided subtotal and service charge.
- **[03_azure_estate]** The subtotal of $22,000.00 cannot be verified without individual line item investments.
- **[05_vet_clinic]** Missing "BILL TO:" information (client name/address)
- **[05_vet_clinic]** Missing "TERMS & CONDITIONS:" content
- **[05_vet_clinic]** Individual line item costs are not displayed in the 'Cost (inc GST)' column
- **[05_vet_clinic]** The document retains blank template sections, making it unprofessional.
- **[07_move_easy]** "BILL TO:" section is blank, missing customer information.
- **[07_move_easy]** "TERMS & CONDITIONS:" section is blank, omitting vital contractual details.
- **[07_move_easy]** Volume and Rate/cu.ft values are missing for "Residential Move - 3 Bedroom House".
- **[07_move_easy]** Line items "Packing & Unpacking Services (Flat Rate)" and "Full Insurance Coverage (Up to $50k)" display duplicate amounts in the 'Rate/cu.ft' and 'Total' columns, indicating incorrect data mapping.
- **[07_move_easy]** The amount for "Fuel Surcharge (10%)" is missing from the line item detail.
- **[08_code_crafters]** Missing 'Seats' quantity for all line items.
- **[08_code_crafters]** Incorrect 'Monthly Fee' values in line items; they appear to be annual totals or miscalculated figures instead of monthly fees.
- **[08_code_crafters]** Final 'TOTAL COST' is mathematically incorrect based on the subtotal and VAT provided.
- **[09_gourmet_catering]** Missing value for 'Staffing Fee'.
- **[09_gourmet_catering]** 'TOTAL QUOTE' does not include a Staffing Fee, making it potentially incorrect.
- **[10_fit_pro]** Missing 'BILL TO:' information.
- **[10_fit_pro]** Missing 'TERMS & CONDITIONS:' content.
- **[10_fit_pro]** Missing individual costs for 'Training Package' line items.
- **[10_fit_pro]** Inaccurate 'TOTAL' as 'FitPro T-Shirt & Water Bottle' was added without its cost or updating the sum.
- **[10_fit_pro]** Missing 'Membership #'.

### Calculation Accuracy
- **[02_global_steel]** Expected grand total '$17,066.50' not found in output
- **[03_azure_estate]** Expected grand total '$25,960.00' not found in output
- **[05_vet_clinic]** Expected subtotal 'A$505.00' not found in output
- **[07_move_easy]** Expected subtotal '$6,500.00' not found in output
- **[07_move_easy]** Expected grand total '$6,500.00' not found in output
- **[08_code_crafters]** Expected grand total '€18,921.00' not found in output

### Template Fidelity
- **[02_global_steel]** Customer name not injected: 'Midwest Bridge Builders'
- **[05_vet_clinic]** Customer name not injected: 'Sarah Miller (Pet: Luna)'
- **[07_move_easy]** Customer name not injected: 'Robert Henderson'
- **[10_fit_pro]** Customer name not injected: 'Mark Stevens'

### pipeline
- **[06_solar_rebate]** build_quote_template returned None

---
*Generated by `test_runner.py` on 2026-05-21 09:26*