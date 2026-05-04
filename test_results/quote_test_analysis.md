# Quote Generation Test Results — 2026-05-03 19:32

**Templates tested:** 10  |  **Run date:** 2026-05-03 19:32

## Summary

| Template | Plac. | Line. | Calc. | Temp. | Clie. | **Total /50** | Status |
|---|---|---|---|---|---|---|---|
| `01_aura_design` | 10 | 10 | 10 | 10 | 7 | **47** | ✅ PASS |
| `02_global_steel` | 10 | 10 | 10 | 10 | 5 | **45** | ✅ PASS |
| `03_azure_estate` | 10 | 10 | 10 | 10 | 2 | **42** | ✅ PASS |
| `04_quick_handyman` | 10 | 10 | 10 | 10 | 9 | **49** | ✅ PASS |
| `05_vet_clinic` | 10 | 10 | 7 | 10 | 2 | **39** | ✅ PASS |
| `06_solar_rebate` | 10 | 10 | 10 | 10 | 3 | **43** | ✅ PASS |
| `07_move_easy` | 10 | 10 | 10 | 10 | 3 | **43** | ✅ PASS |
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
**Business:** Aura Design Studio  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `brackets`  |  **Columns:** Project Item, Amount

**Total Score: 47/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 7/10 | The 'Status' is 'Draft', which is unsuitable for a quote sent to a client.; Lacks crucial payment details/instructions (e.g., bank account information, detailed payment terms). |

**Client Readiness Note:** The quote is well-formatted, accurately fills all template placeholders, and calculations are correct. However, its 'Draft' status is inappropriate for a client-facing document, and it lacks essential payment instructions.

### 02_global_steel
**Business:** Global Steel & Supply Corp  |  **Currency:** USD  |  **Tax:** 7.0%  |  **Field Style:** `labels`  |  **Columns:** Part No, Description, Qty, Weight (lbs), Unit Price, Subtotal

**Total Score: 45/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 5/10 | The 'BILL TO:' label is missing, making the customer name less clearly contextualized.; The 'Weight (lbs)' column is entirely blank for all line items, which is critical information for steel products and was present in the template's example data. (+1 more) |

**Client Readiness Note:** The quote features accurate calculations, correct dates, and a clear customer name. However, it crucially lacks 'Weight (lbs)' for all line items, which is vital for a steel product quote. The 'BILL TO:' label is also missing, impacting professional appearance.

### 03_azure_estate
**Business:** The Azure Estate  |  **Currency:** USD  |  **Tax:** 18.0%  |  **Field Style:** `sample`  |  **Columns:** Service Category, Description, Investment

**Total Score: 42/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Column misalignment and missing data for service line items (missing 'Service Category' entries, duplicated 'Description' content, and absent individual 'Investment' amounts).; Lack of pricing transparency due to missing individual service investment figures, rendering the quote unusable for a client. (+1 more) |

**Client Readiness Note:** The generated quote has critical errors in its line item presentation. It lacks individual service categories, duplicates descriptions, and completely omits the investment amount for each service, making it impossible to verify the subtotal or understand the pricing breakdown. This is a severe functional and professional failing.

### 04_quick_handyman
**Business:** Quick Fix Handyman Services  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Field Style:** `brackets`  |  **Columns:** Job Description, Price

**Total Score: 49/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 9/10 | Status field indicates 'Draft', which is not ideal for a final client-facing document. |

**Client Readiness Note:** The generated quote is professionally presented, complete, and highly accurate with all placeholders correctly filled and calculations verified. The only minor point is the 'Status: Draft', which ideally should be 'Final' or 'Sent' for a client-ready document.

### 05_vet_clinic
**Business:** Happy Paws Veterinary Clinic  |  **Currency:** AUD  |  **Tax:** 10.0%  |  **Field Style:** `labels`  |  **Columns:** Procedure / Item, Qty, Cost (inc GST)

**Total Score: 39/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 7/10 | Expected subtotal 'A$505.00' not found in output |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Costs are missing for all line items ('Annual Vaccination & Health Check', 'Dental Scale and Polish', 'Antibiotic Course (10 days)').; The 'TERMS & CONDITIONS:' section is a raw placeholder and was not filled. (+3 more) |

**Client Readiness Note:** The quote is critically incomplete, missing costs for all individual line items, which makes it unusable. It also contains unaddressed placeholders like 'TERMS & CONDITIONS:' and an inappropriate 'Draft' status, rendering it unsuitable for client delivery.

### 06_solar_rebate
**Business:** Eco-Power Solar Solutions  |  **Currency:** AUD  |  **Tax:** 0.0%  |  **Field Style:** `sample`  |  **Columns:** System Component, Qty, Price

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | The value for "Govt Rebate (STCs)" is missing, leaving a blank field.; The "NET AMOUNT PAYABLE" is incorrect as it simply mirrors the "Gross System Total" without applying any rebate, despite the rebate line item being present. (+1 more) |

**Client Readiness Note:** The quote is critically incomplete and inaccurate. The "Govt Rebate (STCs)" amount is entirely missing, leading to an incorrect "NET AMOUNT PAYABLE" calculation that equals the gross total. This lack of essential financial detail makes the document unprofessional and unsuitable for client delivery.

### 07_move_easy
**Business:** Move Easy Logisitics  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Field Style:** `labels`  |  **Columns:** Service Description, Volume (cu.ft), Rate/cu.ft, Total

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | Content for 'TERMS & CONDITIONS' is missing.; The 'BILL TO:' label is missing before the client's name. (+4 more) |

**Client Readiness Note:** The generated quote is not client-ready due to multiple significant issues. It lacks the actual content for 'TERMS & CONDITIONS,' omits the 'BILL TO:' label, and has missing data points for line items like 'Volume' and 'Fuel Surcharge.' Crucially, the 'ESTIMATED TOTAL' is inaccurate as it does not incorporate the listed fuel surcharge, and line item columns are incorrectly formatted.

### 08_code_crafters
**Business:** Code Crafters Software  |  **Currency:** EUR  |  **Tax:** 19.0%  |  **Field Style:** `brackets`  |  **Columns:** Software Service, Seats, Monthly Fee, Yearly Total

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | The 'Seats' column is empty for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'.; For 'Enterprise License - CRM Suite', the 'Monthly Fee' column shows '€540.00' (total monthly) instead of the per-seat monthly fee '€45.00'. (+1 more) |

**Client Readiness Note:** The quote has critical data errors within the line item table. The 'Seats' column is empty for both services, and the 'Monthly Fee' column contains incorrect values (total monthly cost for CRM, annual cost for Support Add-on). These errors make the document highly unprofessional and not client-ready.

### 09_gourmet_catering
**Business:** Gourmet Garden Catering  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `sample`  |  **Columns:** Item Description, Price Per Head, Quantity, Total

**Total Score: 43/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 3/10 | Missing content for 'TERMS & CONDITIONS' section.; Missing value for 'Staffing Fee' line item, resulting in an unclear total. (+1 more) |

**Client Readiness Note:** The generated quote is incomplete and unprofessional due to critical omissions: the content for 'TERMS & CONDITIONS' is entirely missing, and the 'Staffing Fee' line item has no specified value. This ambiguity makes the document unready for a client, lacking essential contractual information and a clear final cost breakdown.

### 10_fit_pro
**Business:** FitPro Personal Training  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Field Style:** `labels`  |  **Columns:** Training Package, Cost

**Total Score: 42/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 2/10 | Missing 'BILL TO:' label for the customer's name.; Costs for all line items ('10 Session Kickstart Pack', 'Nutritional Consultation', 'FitPro T-Shirt & Water Bottle') are missing. (+2 more) |

**Client Readiness Note:** The quote is highly incomplete and inaccurate, missing all individual item costs and failing to update the total to include a newly added item. The 'BILL TO:' label is also absent, making it unsuitable for client presentation.

## All Issues Found

| Template | Dimension | Issue |
|---|---|---|
| `01_aura_design` | Client Readiness | The 'Status' is 'Draft', which is unsuitable for a quote sent to a client. |
| `01_aura_design` | Client Readiness | Lacks crucial payment details/instructions (e.g., bank account information, detailed payment terms). |
| `02_global_steel` | Client Readiness | The 'BILL TO:' label is missing, making the customer name less clearly contextualized. |
| `02_global_steel` | Client Readiness | The 'Weight (lbs)' column is entirely blank for all line items, which is critical information for steel products and was present in the template's example data. |
| `02_global_steel` | Client Readiness | The 'Project Code' and 'Department' fields are left empty. |
| `03_azure_estate` | Client Readiness | Column misalignment and missing data for service line items (missing 'Service Category' entries, duplicated 'Description' content, and absent individual 'Investment' amounts). |
| `03_azure_estate` | Client Readiness | Lack of pricing transparency due to missing individual service investment figures, rendering the quote unusable for a client. |
| `03_azure_estate` | Client Readiness | Unprofessional appearance makes the document unsuitable for client delivery. |
| `04_quick_handyman` | Client Readiness | Status field indicates 'Draft', which is not ideal for a final client-facing document. |
| `05_vet_clinic` | Calculation Accuracy | Expected subtotal 'A$505.00' not found in output |
| `05_vet_clinic` | Client Readiness | Costs are missing for all line items ('Annual Vaccination & Health Check', 'Dental Scale and Polish', 'Antibiotic Course (10 days)'). |
| `05_vet_clinic` | Client Readiness | The 'TERMS & CONDITIONS:' section is a raw placeholder and was not filled. |
| `05_vet_clinic` | Client Readiness | 'Patient Record #' is blank. |
| `05_vet_clinic` | Client Readiness | 'Visit Date' is blank. |
| `05_vet_clinic` | Client Readiness | The 'Status' is marked as 'Draft', which is not appropriate for a client-facing document. |
| `06_solar_rebate` | Client Readiness | The value for "Govt Rebate (STCs)" is missing, leaving a blank field. |
| `06_solar_rebate` | Client Readiness | The "NET AMOUNT PAYABLE" is incorrect as it simply mirrors the "Gross System Total" without applying any rebate, despite the rebate line item being present. |
| `06_solar_rebate` | Client Readiness | The label "Expiry Date" is potentially confusing when paired with "Valid Until", as 'Expiry Date' typically signifies the end of validity, which would contradict 'Valid Until'. |
| `07_move_easy` | Client Readiness | Content for 'TERMS & CONDITIONS' is missing. |
| `07_move_easy` | Client Readiness | The 'BILL TO:' label is missing before the client's name. |
| `07_move_easy` | Client Readiness | The 'Volume (cu.ft)' is missing for 'Residential Move - 3 Bedroom House'. |
| `07_move_easy` | Client Readiness | The 'Volume (cu.ft)' and 'Rate/cu.ft' columns are incorrectly populated or missing for 'Packing & Unpacking Services' and 'Full Insurance Coverage', showing the 'Total' value twice instead. |
| `07_move_easy` | Client Readiness | The value for 'Fuel Surcharge (10%)' is missing. |
| `07_move_easy` | Client Readiness | The 'ESTIMATED TOTAL' is incorrect as it does not include the 'Fuel Surcharge (10%)' listed above it. |
| `08_code_crafters` | Client Readiness | The 'Seats' column is empty for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'. |
| `08_code_crafters` | Client Readiness | For 'Enterprise License - CRM Suite', the 'Monthly Fee' column shows '€540.00' (total monthly) instead of the per-seat monthly fee '€45.00'. |
| `08_code_crafters` | Client Readiness | For 'Premium Support Add-on', the 'Monthly Fee' column shows '€2,400.00' (yearly total) instead of the monthly fee '€200.00'. |
| `09_gourmet_catering` | Client Readiness | Missing content for 'TERMS & CONDITIONS' section. |
| `09_gourmet_catering` | Client Readiness | Missing value for 'Staffing Fee' line item, resulting in an unclear total. |
| `09_gourmet_catering` | Client Readiness | TOTAL QUOTE does not account for a Staffing Fee, making it potentially incorrect or misleading given the blank line item. |
| `10_fit_pro` | Client Readiness | Missing 'BILL TO:' label for the customer's name. |
| `10_fit_pro` | Client Readiness | Costs for all line items ('10 Session Kickstart Pack', 'Nutritional Consultation', 'FitPro T-Shirt & Water Bottle') are missing. |
| `10_fit_pro` | Client Readiness | The total amount is inaccurate because it does not reflect the added 'FitPro T-Shirt & Water Bottle' item. |
| `10_fit_pro` | Client Readiness | The document status is 'Draft', which is not appropriate for a client-ready quote. |

## Recommended Fixes & Next Steps

### Client Readiness
- **[01_aura_design]** The 'Status' is 'Draft', which is unsuitable for a quote sent to a client.
- **[01_aura_design]** Lacks crucial payment details/instructions (e.g., bank account information, detailed payment terms).
- **[02_global_steel]** The 'BILL TO:' label is missing, making the customer name less clearly contextualized.
- **[02_global_steel]** The 'Weight (lbs)' column is entirely blank for all line items, which is critical information for steel products and was present in the template's example data.
- **[02_global_steel]** The 'Project Code' and 'Department' fields are left empty.
- **[03_azure_estate]** Column misalignment and missing data for service line items (missing 'Service Category' entries, duplicated 'Description' content, and absent individual 'Investment' amounts).
- **[03_azure_estate]** Lack of pricing transparency due to missing individual service investment figures, rendering the quote unusable for a client.
- **[03_azure_estate]** Unprofessional appearance makes the document unsuitable for client delivery.
- **[04_quick_handyman]** Status field indicates 'Draft', which is not ideal for a final client-facing document.
- **[05_vet_clinic]** Costs are missing for all line items ('Annual Vaccination & Health Check', 'Dental Scale and Polish', 'Antibiotic Course (10 days)').
- **[05_vet_clinic]** The 'TERMS & CONDITIONS:' section is a raw placeholder and was not filled.
- **[05_vet_clinic]** 'Patient Record #' is blank.
- **[05_vet_clinic]** 'Visit Date' is blank.
- **[05_vet_clinic]** The 'Status' is marked as 'Draft', which is not appropriate for a client-facing document.
- **[06_solar_rebate]** The value for "Govt Rebate (STCs)" is missing, leaving a blank field.
- **[06_solar_rebate]** The "NET AMOUNT PAYABLE" is incorrect as it simply mirrors the "Gross System Total" without applying any rebate, despite the rebate line item being present.
- **[06_solar_rebate]** The label "Expiry Date" is potentially confusing when paired with "Valid Until", as 'Expiry Date' typically signifies the end of validity, which would contradict 'Valid Until'.
- **[07_move_easy]** Content for 'TERMS & CONDITIONS' is missing.
- **[07_move_easy]** The 'BILL TO:' label is missing before the client's name.
- **[07_move_easy]** The 'Volume (cu.ft)' is missing for 'Residential Move - 3 Bedroom House'.
- **[07_move_easy]** The 'Volume (cu.ft)' and 'Rate/cu.ft' columns are incorrectly populated or missing for 'Packing & Unpacking Services' and 'Full Insurance Coverage', showing the 'Total' value twice instead.
- **[07_move_easy]** The value for 'Fuel Surcharge (10%)' is missing.
- **[07_move_easy]** The 'ESTIMATED TOTAL' is incorrect as it does not include the 'Fuel Surcharge (10%)' listed above it.
- **[08_code_crafters]** The 'Seats' column is empty for both 'Enterprise License - CRM Suite' and 'Premium Support Add-on'.
- **[08_code_crafters]** For 'Enterprise License - CRM Suite', the 'Monthly Fee' column shows '€540.00' (total monthly) instead of the per-seat monthly fee '€45.00'.
- **[08_code_crafters]** For 'Premium Support Add-on', the 'Monthly Fee' column shows '€2,400.00' (yearly total) instead of the monthly fee '€200.00'.
- **[09_gourmet_catering]** Missing content for 'TERMS & CONDITIONS' section.
- **[09_gourmet_catering]** Missing value for 'Staffing Fee' line item, resulting in an unclear total.
- **[09_gourmet_catering]** TOTAL QUOTE does not account for a Staffing Fee, making it potentially incorrect or misleading given the blank line item.
- **[10_fit_pro]** Missing 'BILL TO:' label for the customer's name.
- **[10_fit_pro]** Costs for all line items ('10 Session Kickstart Pack', 'Nutritional Consultation', 'FitPro T-Shirt & Water Bottle') are missing.
- **[10_fit_pro]** The total amount is inaccurate because it does not reflect the added 'FitPro T-Shirt & Water Bottle' item.
- **[10_fit_pro]** The document status is 'Draft', which is not appropriate for a client-ready quote.

### Calculation Accuracy
- **[05_vet_clinic]** Expected subtotal 'A$505.00' not found in output

---
*Generated by `test_runner.py` on 2026-05-03 19:32*