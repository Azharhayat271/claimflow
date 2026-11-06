# Bus matrix

The bus matrix is the plan for the gold layer. Each row is a business process, and each process becomes one fact table. Each column is a dimension. A mark in a cell means that fact table joins to that dimension.

A dimension used by more than one row is **conformed**: it is built once, with one set of keys, and every fact table shares it. Because of that, a query can combine facts, for example comparing claims billed to payments received by payer and month, and the numbers agree.

## The matrix

| Business process | Fact table | Fact type | Date | Patient | Payer | Provider | Facility | Procedure | Diagnosis | Encounter class | Claim status | Payment type | Adjustment reason | Degenerate ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Billing a service | `fact_claim_line` | Transaction | service, billed | ✓ | ✓ | rendering, supervising, referring | ✓ | ✓ | ✓ (bridge) | ✓ | ✓ | | | claim number |
| Receiving payments and adjustments | `fact_payment` | Transaction | posted, service | ✓ | ✓ | rendering | ✓ | ✓ | | | | ✓ | ✓ | claim number, payment ID |
| Claim lifecycle | `fact_claim_lifecycle` | Accumulating snapshot | service, submitted, adjudicated, paid, denied, closed | ✓ | ✓ | rendering | ✓ | | ✓ (bridge) | ✓ | ✓ | | ✓ | claim number |
| Patient encounters | `fact_encounter` | Transaction | start, end | ✓ | ✓ | ✓ | ✓ | | ✓ (reason) | ✓ | | | | encounter ID |
| Insurance coverage | `fact_coverage_month` | Periodic snapshot | month | ✓ | primary, secondary | | | | | | | | | |
| Accounts receivable | `fact_ar_month_end` | Periodic snapshot | snapshot month-end | ✓ | ✓ | rendering | ✓ | | | | ✓ | | | claim number |

When a cell names something instead of showing a tick, that dimension is used in more than one **role**: the same table is joined more than once, under different names. For example, `fact_claim_lifecycle` joins `dim_date` six times, once for each milestone.

## Build order

| Fact table | Status | Why |
| --- | --- | --- |
| `fact_claim_line` | Core | It's the base of all revenue reporting: what was billed, to whom, for what. |
| `fact_payment` | Core | Together with claim lines, it gives collections, write-offs and the outstanding balance. |
| `fact_claim_lifecycle` | Core | It gives days to payment, denial rate and the bottlenecks in the claim workflow. |
| `fact_ar_month_end` | Next | AR ageing trends. It's derived from claim lines and payments, so it needs no new source data. |
| `fact_coverage_month` | Next | Member months, the denominator for per-member-per-month (PMPM) cost. |
| `fact_encounter` | Later | Utilisation by visit type. It's useful context but not on the billing critical path. |

## Conformed dimensions

| Dimension | Used by | Source | Notes |
| --- | --- | --- | --- |
| `dim_date` | 6 of 6 | Generated | One row per calendar day. It plays many roles (service, posted, paid and so on) through separate foreign keys. |
| `dim_patient` | 6 of 6 | `patients`, `payer_transitions` | SCD Type 2. A new row is added whenever the patient's coverage changes, so a claim joins to the coverage that was in force on its service date. |
| `dim_payer` | 6 of 6 | `payers` | 10 payers across Medicare, Medicaid, commercial plans and self-pay. Self-pay is a real row, not a NULL. |
| `dim_provider` | 5 of 6 | `providers` | The clinician, with specialty and NPI. It plays the rendering, supervising and referring roles. |
| `dim_facility` | 5 of 6 | `organizations` | Where the service happened (the place of service). |
| `dim_claim_status` | 3 of 6 | Claim status fields | A junk dimension: status for each responsible party (primary, secondary, patient) combined into one small table. |
| `dim_diagnosis` | 3 of 6 | Claim diagnosis codes | A claim carries up to 8 diagnoses, so facts join through `bridge_claim_diagnosis` rather than a single key. |
| `dim_encounter_class` | 3 of 6 | Encounter class | Ambulatory, emergency, inpatient, outpatient, urgent care, wellness and so on. |
| `dim_procedure` | 2 of 6 | Line procedure codes | Carries a code-system column, because billed lines mix visit, procedure, medication and immunisation codes. |
| `dim_adjustment_reason` | 2 of 6 | Adjudication simulation | CARC-style reason codes for denials and adjustments. The source data has no denials, so this depends on the simulated adjudication step. |
| `dim_payment_type` | 1 of 6 | Transaction type, method, responsible party | A junk dimension: payment, adjustment or transfer × e-check, card, cash, check or copay × primary, secondary or patient. |

The degenerate IDs (claim number, payment ID, encounter ID) stay on the fact rows as plain columns. They have no attributes of their own, so a separate dimension table would add a join without adding information.

## Design decisions

- **Coverage history lives in `dim_patient` (SCD Type 2), not in the facts.** The payer on a claim is the payer that was billed. The patient dimension answers a different question: what coverage did this person hold on that date? Keeping both lets you find claims billed to the wrong payer.
- **The lifecycle is an accumulating snapshot, not a status log.** There is one row per claim, and its milestone dates are filled in as the claim moves forward. Each lag is a single subtraction on one row, for example days from submitted to paid.
- **Unknown values point to real rows, never NULL keys.** Every dimension has "Unknown" and "Not applicable" rows, so inner joins never silently drop facts.
- **Facts that can't be built from the source are shown, not hidden.** The source data has no denials and almost no payment delay, so the denied and adjudicated milestones and `dim_adjustment_reason` depend on the simulated adjudication step. They are marked in the matrix so it's clear what comes from the source and what is simulated.
