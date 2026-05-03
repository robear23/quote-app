# Quote Generation Test Results — 2026-05-03 17:32

**Templates tested:** 10  |  **Run date:** 2026-05-03 17:32

## Summary

| Template | Plac. | Line. | Calc. | Temp. | Clie. | **Total /50** | Status |
|---|---|---|---|---|---|---|---|
| `01_aura_design` | 10 | 10 | 10 | 10 | 4 | **44** | ✅ PASS |
| `02_global_steel` | 10 | 10 | 10 | 10 | 4 | **44** | ✅ PASS |
| `03_azure_estate` | 10 | 10 | 7 | 10 | 1 | **38** | ✅ PASS |
| `04_quick_handyman` | 10 | 10 | 10 | 10 | 4 | **44** | ✅ PASS |
| `05_vet_clinic` | 10 | 10 | 7 | 10 | 2 | **39** | ✅ PASS |
| `06_solar_rebate` | 10 | 0 | 10 | 10 | 2 | **32** | ⚠️ WARN |
| `07_move_easy` | 10 | 10 | 10 | 10 | 2 | **42** | ✅ PASS |
| `08_code_crafters` | 10 | 10 | 10 | 10 | 3 | **43** | ✅ PASS |
| `09_gourmet_catering` | 10 | 10 | 10 | 10 | 3 | **43** | ✅ PASS |
| `10_fit_pro` | 10 | 10 | 10 | 10 | 2 | **42** | ✅ PASS |

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
**Business:** Aura Design Studio  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Project Item, Amount

**Total Score: 44/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 4/10 | Status field is unpopulated.; Inconsistency between 'Valid for 14 days' in T&C and 'Valid Until' date (30 days from issuance). |

**Client Readiness Note:** The quote populated most fields accurately, including client details, line items, and totals. However, the 'Status' field is entirely blank, and there's a significant inconsistency between the 'Valid for 14 days' in the terms and the 'Valid Until' date, which is 30 days from issuance. These critical flaws make the document unprofessional and not client-ready.

### 02_global_steel
**Business:** Global Steel & Supply Corp  |  **Currency:** USD  |  **Tax:** 7.0%  |  **Columns:** Part No, Description, Qty, Weight (lbs), Unit Price, Subtotal

**Total Score: 44/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 4/10 | 'Weight (lbs)' column is present as a header but is entirely blank for all line items.; 'Project Code' and 'Department' fields are present but left entirely blank, appearing as unpopulated template fields. |

**Client Readiness Note:** The quote accurately calculates totals and populates customer details, but it fails on completeness and professional appearance. Key fields like 'Weight (lbs)' are entirely missing data for all line items, and 'Project Code' and 'Department' are left blank, making the document appear unfinished and unprofessional for a client.

### 03_azure_estate
**Business:** The Azure Estate  |  **Currency:** USD  |  **Tax:** 18.0%  |  **Columns:** Service Category, Description, Investment

**Total Score: 38/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected tax amount '$3,960.00' not found in output |
| Template Fidelity | 10/10 | None |
| Client Readiness | 1/10 | Missing 'Status' value.; Missing 'Service Category' for all line items. (+3 more) |

**Client Readiness Note:** The generated quote is critically incomplete and inaccurate. Key line item details, including service categories and individual investments, are entirely missing, rendering the document incomprehensible. Furthermore, the service charge calculation is incorrect.

### 04_quick_handyman
**Business:** Quick Fix Handyman Services  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Columns:** Job Description, Price

**Total Score: 44/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 4/10 | Missing value for 'Status' field; Inconsistent 'Valid Until' date that contradicts the stated 14-day validity period |

**Client Readiness Note:** The quote document is generally well-structured but is not client-ready due to a missing value for the 'Status' field. A critical inaccuracy exists where the 'Valid Until' date of June 02, 2026, directly contradicts the stated 'Valid for 14 days' term, extending the validity period significantly.

### 05_vet_clinic
**Business:** Happy Paws Veterinary Clinic  |  **Currency:** AUD  |  **Tax:** 10.0%  |  **Columns:** Procedure / Item, Qty, Cost (inc GST)

**Total Score: 39/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected subtotal 'A$505.00' not found in output |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Missing 'Cost (inc GST)' for all listed line items.; The 'Status' field is left blank. (+2 more) |

**Client Readiness Note:** The generated quote is severely incomplete as it fails to include the 'Cost (inc GST)' for any of the listed procedures/items. Additionally, the 'Status' field is left blank, and the 'Valid Until' date is inconsistent with the 'Valid for 14 days' term, making it entirely unsuitable for client delivery.

### 06_solar_rebate
**Business:** Eco-Power Solar Solutions  |  **Currency:** AUD  |  **Tax:** 0.0%  |  **Columns:** System Component, Qty, Price

**Total Score: 32/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 0/10 | Line item description not found: '6.6kW Tier 1 Solar Panel Array'; Line item description not found: '5kW Hybrid Inverter (Battery Ready)' (+1 more) |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Missing names for all system component line items.; Missing "Status" field value. (+2 more) |

**Client Readiness Note:** The quote is severely incomplete, lacking product descriptions, the government rebate amount, and the final status. This leads to an incorrect net payable amount and makes the document unprofessional and unusable for a client.

### 07_move_easy
**Business:** Move Easy Logisitics  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Columns:** Service Description, Volume (cu.ft), Rate/cu.ft, Total

**Total Score: 42/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | The 'Status' field is left blank.; Key line item details (Volume and Rate/cu.ft) are missing for 'Residential Move - 3 Bedroom House' and 'Packing & Unpacking Services (Flat Rate)'. (+1 more) |

**Client Readiness Note:** The generated quote has significant omissions and a critical calculation error. The 'Status' field is blank, key line item details for volume and rate are missing, and most importantly, the 'ESTIMATED TOTAL' is incorrect, rendering the document unsuitable for client presentation.

### 08_code_crafters
**Business:** Code Crafters Software  |  **Currency:** EUR  |  **Tax:** 19.0%  |  **Columns:** Software Service, Seats, Monthly Fee, Yearly Total

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | The 'Status' field is left blank, indicating an unprocessed placeholder.; The 'Seats' column is missing values for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'. (+2 more) |

**Client Readiness Note:** The generated quote contains several critical errors that render it unusable. Key fields like 'Status' and 'Seats' are either empty or missing, and the 'Monthly Fee' figures for both services are incorrect based on the provided yearly totals and template logic. This indicates significant data mapping and completeness issues.

### 09_gourmet_catering
**Business:** Gourmet Garden Catering  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Item Description, Price Per Head, Quantity, Total

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | Final TOTAL QUOTE calculation is incorrect; it repeats the subtotal (£7,920.00) instead of adding the Staffing Fee (£850.00) for a correct total of £8,770.00.; The 'Status' field is present but left entirely blank, which looks incomplete and unprofessional. |

**Client Readiness Note:** The quote populates most client and item details correctly but fails to calculate the final total accurately, simply repeating the subtotal instead of including the staffing fee. Additionally, the 'Status' field is left blank, appearing unprofessional.

### 10_fit_pro
**Business:** FitPro Personal Training  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Training Package, Cost

**Total Score: 42/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Missing value for 'Status' field.; Missing individual costs for all 'Training Package' line items. (+2 more) |

**Client Readiness Note:** The quote is significantly incomplete and inaccurate, with missing line item costs, an unpriced additional item, and an unpopulated 'Status' field. The total also appears inconsistent given the added item and missing individual prices, making it completely unsuitable for a client.

## All Issues Found

| Template | Dimension | Issue |
|---|---|---|
| `01_aura_design` | Client Readiness | Status field is unpopulated. |
| `01_aura_design` | Client Readiness | Inconsistency between 'Valid for 14 days' in T&C and 'Valid Until' date (30 days from issuance). |
| `02_global_steel` | Client Readiness | 'Weight (lbs)' column is present as a header but is entirely blank for all line items. |
| `02_global_steel` | Client Readiness | 'Project Code' and 'Department' fields are present but left entirely blank, appearing as unpopulated template fields. |
| `03_azure_estate` | Calculation Accuracy | Expected tax amount '$3,960.00' not found in output |
| `03_azure_estate` | Client Readiness | Missing 'Status' value. |
| `03_azure_estate` | Client Readiness | Missing 'Service Category' for all line items. |
| `03_azure_estate` | Client Readiness | Missing 'Investment' (price) for all line items. |
| `03_azure_estate` | Client Readiness | The 'Description' column is redundant, repeating the missing 'Service Category' information. |
| `03_azure_estate` | Client Readiness | Service charge calculation is incorrect (18% of $22,000 should be $3,960, not $3,690). |
| `04_quick_handyman` | Client Readiness | Missing value for 'Status' field |
| `04_quick_handyman` | Client Readiness | Inconsistent 'Valid Until' date that contradicts the stated 14-day validity period |
| `05_vet_clinic` | Calculation Accuracy | Expected subtotal 'A$505.00' not found in output |
| `05_vet_clinic` | Client Readiness | Missing 'Cost (inc GST)' for all listed line items. |
| `05_vet_clinic` | Client Readiness | The 'Status' field is left blank. |
| `05_vet_clinic` | Client Readiness | The 'Valid Until' date (02 June 2026) is inconsistent with the stated 'Valid for 14 days' term (should be 17 May 2026). |
| `05_vet_clinic` | Client Readiness | The calculated 'GST Included' and 'TOTAL PAYABLE' cannot be verified due to missing line item costs. |
| `06_solar_rebate` | Line Items Integrity | Line item description not found: '6.6kW Tier 1 Solar Panel Array' |
| `06_solar_rebate` | Line Items Integrity | Line item description not found: '5kW Hybrid Inverter (Battery Ready)' |
| `06_solar_rebate` | Line Items Integrity | Line item description not found: 'Smart Meter Installation' |
| `06_solar_rebate` | Client Readiness | Missing names for all system component line items. |
| `06_solar_rebate` | Client Readiness | Missing "Status" field value. |
| `06_solar_rebate` | Client Readiness | Missing "Govt Rebate (STCs)" amount. |
| `06_solar_rebate` | Client Readiness | "NET AMOUNT PAYABLE" is incorrect. |
| `07_move_easy` | Client Readiness | The 'Status' field is left blank. |
| `07_move_easy` | Client Readiness | Key line item details (Volume and Rate/cu.ft) are missing for 'Residential Move - 3 Bedroom House' and 'Packing & Unpacking Services (Flat Rate)'. |
| `07_move_easy` | Client Readiness | The 'ESTIMATED TOTAL' of $6,500.00 is incorrectly calculated based on the listed line items ($7,125.00 is the correct sum). |
| `08_code_crafters` | Client Readiness | The 'Status' field is left blank, indicating an unprocessed placeholder. |
| `08_code_crafters` | Client Readiness | The 'Seats' column is missing values for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'. |
| `08_code_crafters` | Client Readiness | The 'Monthly Fee' for 'Enterprise License - CRM Suite' is incorrect (€540.00 instead of €1,125.00 based on the yearly total of €13,500.00). |
| `08_code_crafters` | Client Readiness | The 'Monthly Fee' for 'Premium Support Add-on (Annual)' is incorrect (€2,400.00 instead of €200.00), appearing to incorrectly display the annual fee in the monthly column. |
| `09_gourmet_catering` | Client Readiness | Final TOTAL QUOTE calculation is incorrect; it repeats the subtotal (£7,920.00) instead of adding the Staffing Fee (£850.00) for a correct total of £8,770.00. |
| `09_gourmet_catering` | Client Readiness | The 'Status' field is present but left entirely blank, which looks incomplete and unprofessional. |
| `10_fit_pro` | Client Readiness | Missing value for 'Status' field. |
| `10_fit_pro` | Client Readiness | Missing individual costs for all 'Training Package' line items. |
| `10_fit_pro` | Client Readiness | An additional line item ('FitPro T-Shirt & Water Bottle') was added without a specified cost. |
| `10_fit_pro` | Client Readiness | The total amount (£535.00) matches the original template's total despite an additional item being present and individual line item costs missing, suggesting an inaccuracy or lack of justification for the total. |

## Recommended Fixes & Next Steps

### Client Readiness
- **[01_aura_design]** Status field is unpopulated.
- **[01_aura_design]** Inconsistency between 'Valid for 14 days' in T&C and 'Valid Until' date (30 days from issuance).
- **[02_global_steel]** 'Weight (lbs)' column is present as a header but is entirely blank for all line items.
- **[02_global_steel]** 'Project Code' and 'Department' fields are present but left entirely blank, appearing as unpopulated template fields.
- **[03_azure_estate]** Missing 'Status' value.
- **[03_azure_estate]** Missing 'Service Category' for all line items.
- **[03_azure_estate]** Missing 'Investment' (price) for all line items.
- **[03_azure_estate]** The 'Description' column is redundant, repeating the missing 'Service Category' information.
- **[03_azure_estate]** Service charge calculation is incorrect (18% of $22,000 should be $3,960, not $3,690).
- **[04_quick_handyman]** Missing value for 'Status' field
- **[04_quick_handyman]** Inconsistent 'Valid Until' date that contradicts the stated 14-day validity period
- **[05_vet_clinic]** Missing 'Cost (inc GST)' for all listed line items.
- **[05_vet_clinic]** The 'Status' field is left blank.
- **[05_vet_clinic]** The 'Valid Until' date (02 June 2026) is inconsistent with the stated 'Valid for 14 days' term (should be 17 May 2026).
- **[05_vet_clinic]** The calculated 'GST Included' and 'TOTAL PAYABLE' cannot be verified due to missing line item costs.
- **[06_solar_rebate]** Missing names for all system component line items.
- **[06_solar_rebate]** Missing "Status" field value.
- **[06_solar_rebate]** Missing "Govt Rebate (STCs)" amount.
- **[06_solar_rebate]** "NET AMOUNT PAYABLE" is incorrect.
- **[07_move_easy]** Key line item details (Volume and Rate/cu.ft) are missing for 'Residential Move - 3 Bedroom House' and 'Packing & Unpacking Services (Flat Rate)'.
- **[07_move_easy]** The 'ESTIMATED TOTAL' of $6,500.00 is incorrectly calculated based on the listed line items ($7,125.00 is the correct sum).
- **[08_code_crafters]** The 'Status' field is left blank, indicating an unprocessed placeholder.
- **[08_code_crafters]** The 'Seats' column is missing values for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'.
- **[08_code_crafters]** The 'Monthly Fee' for 'Enterprise License - CRM Suite' is incorrect (€540.00 instead of €1,125.00 based on the yearly total of €13,500.00).
- **[08_code_crafters]** The 'Monthly Fee' for 'Premium Support Add-on (Annual)' is incorrect (€2,400.00 instead of €200.00), appearing to incorrectly display the annual fee in the monthly column.
## 🛠️ Strategic Analysis & Action Plan

The diverse template set has exposed three primary categories of system weakness. Below are the recommended structural fixes.

### 1. The "Ghost Field" Problem (Custom Fields)
**Issue:** Fields like `[Status]`, `[Project Code]`, and `[Department]` appear in templates but are left blank in the output.
**Root Cause:** The AI extracts these into `custom_template_fields`, but because they aren't mentioned in the user's terse shorthand input, they default to `null`.
**Fixes:**
*   **Prompt Logic:** Update `generate_quote_data` to infer sensible defaults for common custom fields (e.g., Status → "Draft", Payment Terms → "Due on Receipt").
*   **UI Level:** Add a "Configuration" step in the bot where users can set persistent values for these template-specific fields.

### 2. Totals Mapping Reliability
**Issue:** Calculation errors in `03_azure_estate` and `09_gourmet_catering` suggest the AI is failing to map the `tax_amount` and `grand_total` placeholders in complex tables.
**Root Cause:** When templates have multiple "total-like" rows (Subtotal, Surcharge, Tax, Total), the mapping logic sometimes picks the wrong cell or fails to find one, leaving the original sample text behind.
**Fixes:**
*   **Prompt Refinement:** Update `TEMPLATE_MAP_PROMPT` to prioritize mapping cells based on their proximity to recognizable keywords (*VAT*, *Service Charge*, *Total Due*) rather than just table indices.
*   **Regex Pass:** Add a secondary "Smart Scan" regex specifically for totals labels to ensure they are captured even if the AI's structural mapping fails.

### 3. Column Data Integrity (The "Seats/Weight" Problem)
**Issue:** Extra columns like "Seats" (`08_code_crafters`) or "Weight" (`02_global_steel`) are often empty or merged into the description.
**Root Cause:** The `line_items` JSON structure only supports `description`, `qty`, and `unit_price`. Any extra column in the template has no data source.
**Fixes:**
*   **Dynamic Schema:** Update the AI extraction to dynamically add keys to the `line_items` array if it detects the template has extra columns (e.g., if the template has "Part No", the AI should try to extract "part_no" from the user input).
*   **Mapping Fallback:** Ensure that if a column cannot be filled, the system doesn't leave it blank but instead tries to pull relevant data from the description (e.g., extracting a part number from "ST-405 Beam").

### 4. Validity Inconsistencies
**Issue:** Discrepancy between "Valid for 14 days" in text and a fixed 30-day `valid_until` date.
**Root Cause:** The system currently hardcodes a 30-day offset in `document_factory.py`.
**Fix:** Implement a "Validity Period" setting in the `user_configs` table so the AI can use a user-defined delta instead of a hardcoded one.

---
**Next Immediate Step:** Refine the `TEMPLATE_MAP_PROMPT` in `ai_service.py` to be more aggressive about mapping totals cells, as these caused the most "Client Readiness" failures.

---
*Generated by `test_runner.py` on 2026-05-03 17:32*