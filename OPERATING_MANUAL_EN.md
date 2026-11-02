# Universal Procurement Agent – Operating Manual

## 1. Purpose

Universal Procurement Agent is a personal procurement copilot designed to support strategic and operational purchasing tasks across different employers, categories and industries.

The agent helps with:

- RFQ / RFP preparation
- supplier quotation comparison
- TCO analysis
- supplier negotiation preparation
- category strategy
- spend baseline analysis
- supplier portfolio review
- supplier scorecards
- commercial contract review
- supplier counterproposals
- Excel procurement analysis
- email procurement analysis
- Word/PDF document review
- management reporting

The agent is intentionally employer-independent. Company-specific context should be provided only through a company profile or directly in the task.

---

## 2. Core usage principle

For best results, always provide:

1. what you want to analyze,
2. the input data or document,
3. the expected output,
4. the preferred output level.

Example:

```text
Analyze this supplier offer.
I want a standard procurement review with risks, missing data, recommendation and next steps.
```

---

## 3. Output levels

The agent supports three output levels.

### Short

Use when you need a concise management-ready answer.

Use phrases like:

```text
briefly
management summary
for leadership
executive summary
max. 1 page
```

### Standard

Default mode.

Use for normal procurement work:

```text
standard analysis
structured output
include risks and recommendation
```

### Detailed

Use when you need a full working document.

Use phrases like:

```text
detailed
complete analysis
include tables
working document
prepare supporting material
```

---

## 4. Recommended prompt structure

Use this structure:

```text
Task:
[What the agent should do]

Context:
[Brief explanation of the situation]

Input data:
[Text / table / file / email / offer]

I want:
1. list the officially used skills,
2. separate analytical steps,
3. prepare the output in the requested structure,
4. identify risks,
5. provide a recommendation,
6. propose next steps.

Output:
[short / standard / detailed]
```

---

## 5. RFQ / RFP tasks

Use when preparing a supplier request, tender or quotation package.

Example prompt:

```text
Prepare an RFQ for the packaging material category.

Context:
- we need to contact 3 suppliers
- we want comparable offers
- we do not yet have unified prices or specifications

I want:
1. list the used skills,
2. prepare an RFQ email,
3. propose a supplier response table,
4. propose evaluation criteria,
5. list missing inputs.
```

Expected skills:

- RFQ / RFP Preparation
- Procurement Category Strategy
- Supplier Portfolio Review
- Excel Procurement Analysis if a response matrix is needed

---

## 6. Supplier quotation comparison

Use when comparing supplier offers.

Example prompt:

```text
Compare these two offers:

Supplier A:
Price 100 EUR / pcs
Incoterms EXW
Lead time 4 weeks
Payment terms 30 days
MOQ 1,000 pcs

Supplier B:
Price 108 EUR / pcs
Incoterms DAP plant
Lead time 2 weeks
Payment terms 60 days
MOQ 500 pcs

Annual volume is 5,000 pcs.

I want:
1. list the used skills,
2. prepare a comparison table,
3. highlight comparability risks,
4. explain the TCO impact,
5. recommend the next step.
```

Expected skills:

- Supplier Quotation Comparison
- TCO Analysis
- Management Procurement Reporting if management output is needed

---

## 7. Excel procurement analysis

Use when uploading or describing Excel files.

Typical files:

- price lists
- RFQ matrices
- spend data
- supplier scorecards
- supplier lists
- TCO models
- order data
- invoice data

Example prompt:

```text
Analyze this Excel file as an RFQ matrix.

I want:
1. check the data structure,
2. identify missing or inconsistent data,
3. compare suppliers,
4. highlight different units, currencies and Incoterms,
5. prepare a management summary.
```

Expected skills:

- Excel Procurement Analysis
- Supplier Quotation Comparison
- TCO Analysis
- Management Procurement Reporting

Important rule:

```text
Do not calculate savings without a clear baseline.
```

---

## 8. Email procurement analysis

Use when pasting supplier emails or email threads.

Example prompt:

```text
Analyze this supplier email:

"Hello, we confirm the price of 2.40 EUR/pcs. Price validity is 14 days. Delivery EXW, lead time 4 weeks, MOQ 5,000 pcs. Payment 100% in advance. Technical specification and certificates will be sent later."

I want:
1. summarize the email,
2. extract key procurement information,
3. distinguish confirmed commitments from unclear points,
4. list risks,
5. propose a reply to the supplier.
```

Expected skills:

- Email Procurement Analysis
- Contract Commercial Review
- Supplier Counterproposal

---

## 9. Word / PDF document review

Use when reviewing:

- supplier offers
- PDF commercial terms
- Word contracts
- datasheets
- technical specifications
- SDS / REACH documents
- certificates
- supplier presentations

Example prompt:

```text
Review this PDF document from a procurement perspective.

I want:
1. summarize the document,
2. extract key commercial and technical information,
3. list red flags,
4. identify missing points,
5. recommend next steps for the buyer.
```

Expected skills:

- Document Review Word PDF
- Contract Commercial Review if commercial terms are included
- Supplier Counterproposal if supplier response is needed

---

## 10. Contract commercial review

Use when reviewing supplier commercial terms.

Example prompt:

```text
Review these commercial terms:

- price valid for 14 days
- delivery EXW
- payment 14 days in advance
- MOQ 5,000 pcs
- claims within 3 days
- SLA missing
- contract auto-renews for 12 months

I want:
1. commercial contract review,
2. red flags,
3. risk rating,
4. negotiation points,
5. recommended next steps.
```

Expected skills:

- Contract Commercial Review
- Supplier Counterproposal
- Negotiation Brief if negotiation strategy is needed

Important rule:

```text
The agent does not provide final legal advice. Legal wording must be confirmed by Legal.
```

---

## 11. Supplier counterproposal

Use when preparing supplier-facing replies.

Example prompt:

```text
Prepare a professional counterproposal email to the supplier.

Requested changes:
- change EXW to DAP plant
- change 100% prepayment to 30 days after delivery
- extend price validity to 60 days
- reduce MOQ to 1,000 pcs
- add SLA
- extend the claim period to 15 business days

I want:
1. negotiation tone,
2. supplier email,
3. must-have requirements,
4. fallback position.
```

Expected skills:

- Supplier Counterproposal
- Contract Commercial Review
- Negotiation Brief

Important rule:

```text
Do not reveal the fallback position to the supplier in the first email unless the user explicitly asks.
```

---

## 12. Category strategy

Use for strategic category work.

Example prompt:

```text
Prepare a management summary for the new packaging material category.

Context:
- the category is not centrally managed
- purchasing is done from local suppliers
- prices and specifications are not unified
- spend baseline is unclear

I want:
1. describe the current state,
2. propose a category strategy,
3. propose a spend baseline process,
4. propose a supplier portfolio review,
5. list quick wins,
6. propose a 90-day roadmap,
7. prepare an executive summary.
```

Expected skills:

- Procurement Category Strategy
- Spend Baseline Analysis
- Supplier Portfolio Review
- Management Procurement Reporting

---

## 13. Supplier scorecard

Use for supplier performance review.

Example prompt:

```text
Prepare a supplier scorecard.

Supplier A:
- spend 500,000 EUR
- OTIF 92%
- 8 complaints per year
- lead time 4 weeks
- payment terms 30 days
- compliance documentation complete

Supplier B:
- spend 420,000 EUR
- OTIF 98%
- 2 complaints per year
- lead time 2 weeks
- payment terms 60 days
- compliance documentation partially missing

I want:
1. supplier scorecard,
2. supplier status,
3. risks,
4. recommended next steps.
```

Expected skills:

- Supplier Scorecard
- Supplier Portfolio Review
- Management Procurement Reporting

---

## 14. Management reporting

Use when preparing board or management outputs.

Example prompt:

```text
Prepare a short management summary for leadership.

Topic:
[briefly describe the situation]

I want:
1. main message,
2. financial impact,
3. risks,
4. recommended decision,
5. next steps.
```

Expected skills:

- Management Procurement Reporting
- Other supporting skills depending on task

Recommended output:

```text
Short, executive, decision-oriented.
```

---

## 15. Procurement Task Router

Use when the task is complex or mixed.

Example prompt:

```text
Test Procurement Task Router.

I have a supplier email with an offer and a PDF with commercial terms.

I want:
1. identify the procurement task type,
2. select the primary skill,
3. select supporting skills,
4. propose a workflow,
5. define what output the buyer should receive.
```

Expected skill:

- Procurement Task Router

Supporting skills are selected according to input type.

---

## 16. Data quality rules

The agent must always check:

- unit of measure
- currency
- Incoterms
- logistics cost
- payment terms
- MOQ
- lead time
- offer validity
- technical comparability
- compliance documentation
- baseline
- supplier dependency
- source document quality

Do not accept supplier recommendation based only on the lowest unit price.

---

## 17. Confidentiality rules

Do not put highly confidential employer information into GitHub skills.

Use:

```text
company-profiles/current-employer-profile.md
```

only for controlled company context.

Avoid storing:

- confidential supplier prices
- internal contracts
- personal data
- sensitive negotiations
- customer confidential data
- legal advice
- HR-sensitive information

For sensitive tasks, paste only the minimum necessary context.

---

## 18. Updating the agent

Current workflow:

1. Update or add `SKILL.md` in GitHub.
2. Update `skills.yaml`.
3. Create a new ZIP version.
4. Upload the ZIP to Custom GPT Knowledge.
5. Test the new skill.

Recommended versioning:

```text
v1.0 initial skills
v1.1 spend baseline + supplier portfolio
v1.2 supplier scorecard
v1.3 contract commercial review
v1.4 supplier counterproposal
v1.5 Word/PDF document review
v1.6 Excel + email analysis
v1.7 procurement task router
```

---

## 19. Good prompt examples

### Short management output

```text
Prepare an executive summary for leadership. Briefly, max. 1 page.
```

### Standard buyer output

```text
Prepare a standard procurement analysis with risks, recommendation and next steps.
```

### Detailed working document

```text
Prepare a detailed working document including tables, assumptions, risks and an action plan.
```

### Supplier-facing email

```text
Prepare a professional supplier email. Standard, factual and non-aggressive tone.
```

---

## 20. Final rule

The agent supports procurement decision-making, but final commercial commitments, supplier nominations, contract approvals and legal interpretations must always be confirmed by the responsible human owner.
