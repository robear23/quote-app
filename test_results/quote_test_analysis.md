# Quote Generation Test Results — 2026-04-23 10:23

**Templates tested:** 10  |  **Run date:** 2026-04-23 10:23

## Summary

| Template | Plac. | Line. | Calc. | Temp. | Clie. | **Total /50** | Status |
|---|---|---|---|---|---|---|---|
| `01_plumber` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `02_web_agency` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `03_interior_design` | 10 | 10 | 10 | 10 | 6 | **46** | ✅ PASS |
| `04_construction` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `05_accounting` | 10 | 10 | 10 | 10 | 5 | **45** | ✅ PASS |
| `06_photography` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `07_it_services` | 10 | 10 | 10 | 10 | 5 | **45** | ✅ PASS |
| `08_landscaping` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `09_event_planning` | 10 | 10 | 10 | 10 | 10 | **50** | ✅ PASS |
| `10_legal_services` | 10 | 10 | 10 | 10 | 7 | **47** | ✅ PASS |

### Scoring Dimensions

| Dimension | What is measured |
|---|---|
| Placeholder Accuracy | No `{{ }}` Jinja2 or `[bracket]` placeholders remain |
| Line Items Integrity | All requested line item descriptions appear in the output |
| Calculation Accuracy | Subtotal, tax, and total figures are mathematically correct |
| Template Fidelity | Business identity (name, address) and customer name are present |
| Client Readiness | Gemini qualitative review — is this ready to send? |

## Per-Template Detail

### 01_plumber
**Business:** Waters & Sons Plumbing Services  |  **Currency:** GBP  |  **Tax:** 20.0%  |  **Columns:** Description, Qty, Unit Price, Total

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professional, complete, and accurate. All template placeholders are correctly filled with plausible data, calculations are mathematically sound, and the document is well-formatted. It is entirely ready to be sent to a client.

### 02_web_agency
**Business:** Pixel Forge Studio  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Columns:** Service, Hours, Rate, Total

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professional, complete, and accurate. All placeholders have been correctly filled with relevant information, and the calculations for line items and the grand total are precise, including the addition of a new service. It is client-ready and suitable for immediate dispatch.

### 03_interior_design
**Business:** Elara Interiors Ltd  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Description, Qty, Unit, Unit Price, Total

**Total Score: 46/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 6/10 | Missing 'Unit' values for all line items |

**Client Readiness Note:** The quote is well-structured, all placeholders are correctly filled, and calculations are accurate. However, the 'Unit' column for all line items is completely blank, which is a critical omission for clarity and completeness. This issue prevents the document from being client-ready.

### 04_construction
**Business:** Blue Ridge Construction Pty Ltd  |  **Currency:** AUD  |  **Tax:** 10.0%  |  **Columns:** Item, Units, Rate, Amount

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professionally presented, complete with all required sections including accurate line items and totals, and all placeholders have been correctly filled. It is fully ready for client delivery.

### 05_accounting
**Business:** Meridian Advisory Services  |  **Currency:** GBP  |  **Tax:** 20.0%  |  **Columns:** Description, Hours, Rate, Amount

**Total Score: 45/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 5/10 | The hourly rate for 'Statutory accounts preparation and filing' at £1,200.00/hour for 1 hour, and 'Management accounts — quarterly review' at £450.00/hour, are extremely high and implausible for the services described, especially when compared to the original template's rates. |

**Client Readiness Note:** The generated quote is complete and professionally formatted, with all necessary details and calculated totals present. However, the hourly rates for the services listed are highly implausible, significantly differing from the template and likely market rates. This makes the quote potentially confusing and embarrassing to send to a client.

### 06_photography
**Business:** Luminary Photography Co.  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Package, Price

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professionally formatted, complete, and accurate. All placeholders are correctly filled, and the details, including dates and pricing, are plausible and well-presented. It is ready to be sent to a client.

### 07_it_services
**Business:** TechStream Solutions GmbH  |  **Currency:** EUR  |  **Tax:** 0.0%  |  **Columns:** Service, Hours, Rate (EUR), Total (EUR)

**Total Score: 45/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 5/10 | None |

**Client Readiness Note:** Scoring error: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 08_landscaping
**Business:** GreenPath Landscapes Ltd  |  **Currency:** NZD  |  **Tax:** 15.0%  |  **Columns:** Description, Qty, Unit Price, Total

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is professionally presented, complete with all necessary details, and accurate calculations. All template placeholders have been correctly filled, making it entirely client-ready.

### 09_event_planning
**Business:** Occasions Unlimited Events  |  **Currency:** USD  |  **Tax:** 0.0%  |  **Columns:** Service / Item, Qty, Price, Total

**Total Score: 50/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 10/10 | None |

**Client Readiness Note:** The generated quote is exceptionally well-structured and complete, successfully filling all template placeholders with accurate and plausible data. All calculations are correct, and the document presents a professional and client-ready appearance.

### 10_legal_services
**Business:** Thornton & Associates Solicitors  |  **Currency:** GBP  |  **Tax:** 0.0%  |  **Columns:** Professional Service, Hours, Fee (GBP)

**Total Score: 47/50**

| Dimension | Score | Issues |
|---|---|---|
| Placeholder Accuracy | 10/10 | None |
| Line Items Integrity | 10/10 | None |
| Calculation Accuracy | 10/10 | None |
| Template Fidelity | 10/10 | None |
| Client Readiness | 7/10 | The 'Hours' for 'Residential conveyancing' is listed as 1 hour for a £1,500 fee, which may be an inaccurate representation of the work involved or could cause client confusion, especially when compared to the template's 6-hour example for a lower fee. |

**Client Readiness Note:** The generated quote is professionally presented and complete, with all required fields filled and accurate calculations. However, the listing of '1 hour' for the 'Residential conveyancing' service is significantly different from the template's example and could be misleading or confusing to a client.

## All Issues Found

| Template | Dimension | Issue |
|---|---|---|
| `03_interior_design` | Client Readiness | Missing 'Unit' values for all line items |
| `05_accounting` | Client Readiness | The hourly rate for 'Statutory accounts preparation and filing' at £1,200.00/hour for 1 hour, and 'Management accounts — quarterly review' at £450.00/hour, are extremely high and implausible for the services described, especially when compared to the original template's rates. |
| `10_legal_services` | Client Readiness | The 'Hours' for 'Residential conveyancing' is listed as 1 hour for a £1,500 fee, which may be an inaccurate representation of the work involved or could cause client confusion, especially when compared to the template's 6-hour example for a lower fee. |

## Recommended Fixes & Next Steps

### Client Readiness
- **[03_interior_design]** Missing 'Unit' values for all line items
- **[05_accounting]** The hourly rate for 'Statutory accounts preparation and filing' at £1,200.00/hour for 1 hour, and 'Management accounts — quarterly review' at £450.00/hour, are extremely high and implausible for the services described, especially when compared to the original template's rates.
- **[10_legal_services]** The 'Hours' for 'Residential conveyancing' is listed as 1 hour for a £1,500 fee, which may be an inaccurate representation of the work involved or could cause client confusion, especially when compared to the template's 6-hour example for a lower fee.

---
*Generated by `test_runner.py` on 2026-04-23 10:23*