# Fact table grain

The grain says what one row of a fact table means. It is declared before any columns are chosen. Every measure and dimension must be true at that grain, and anything that isn't belongs in a different table. These three statements cover the core facts in the [bus matrix](bus-matrix.md).

| Fact table | Grain | Expected rows (current dataset) |
| --- | --- | --- |
| `fact_claim_line` | One billed service line on one claim. | 311,338 |
| `fact_payment` | One payment, adjustment or balance transfer posted against one claim line. | 724,280 |
| `fact_claim_lifecycle` | One claim as submitted to one payer (primary or secondary), updated in place as it moves through its milestones. | 140,733 |

## `fact_claim_line`

**Grain:** one billed service line on one claim.

**Why this grain:**
- It's the most atomic level the source has. A claim total, or a claim rolled up to the encounter, can always be summed up from lines, but lines can never be recovered from a total.
- Procedure codes and units only exist per line. At claim grain, "revenue by procedure" would be impossible.
- Lines with a zero charge are kept. They record services that were performed but not billed separately, and dropping them would undercount utilisation.

**Measures:** billed amount, units, unit price. All three are additive across every dimension except unit price, which is non-additive and is stored to be averaged, never summed.

**Identifying a line:** the source has no line ID. Each claim's transactions share one sequence counter, and a line starts at each `CHARGE` row. The line key is therefore (claim ID, sequence number of the charge row), and silver assigns a line number from it. A procedure code can't be used, because the same code can appear twice on one claim.

## `fact_payment`

**Grain:** one payment, adjustment or balance transfer posted against one claim line.

**Why this grain:**
- Money moves per line: each payment row in the source follows the charge it settles. Keeping that link is what makes "paid vs billed per procedure" and the rule "payments never exceed the billed amount" testable.
- Transfers are included because they move the balance between responsible parties: primary payer, then secondary payer, then patient. They don't change the total owed, but they decide who owes it, and AR by payer is wrong without them. Each transfer is two source rows (out and in), kept as two signed fact rows so the balance per party always nets correctly.
- One table, with the transaction type in `dim_payment_type`, rather than separate payment and transfer tables. Collections and AR both need payments and transfers side by side, and a single table avoids a union in every query.

**Measures:** payment amount, adjustment amount, transfer amount. Each is additive. Outstanding balance is not stored here, because it is a running total and belongs in the AR snapshot.

**Who paid:** the source doesn't put the payer on a payment row. Silver derives it by replaying the transfers on each claim, with three rules:

1. A payment belongs to whichever party held the balance when it was posted.
2. A copay is always paid by the patient, even while the primary payer holds the balance.
3. On a claim with no insurance, every payment is the patient's.

With those rules, payers pay only by e-check, and patients pay only by cash, card, check or copay. That clean split is how the rules were checked. In the current data, primary payers made 182,120 payments, secondary payers 64,925 and patients 142,707.

## `fact_claim_lifecycle`

**Grain:** one claim as submitted to one payer (primary or secondary), updated in place as it moves through its milestones.

**Why this grain:**
- It's an accumulating snapshot: there is one row per submission, and its milestone dates are filled in as they happen (submitted, adjudicated, paid, denied, closed). Lags such as days from submitted to paid are a subtraction on one row.
- It's per payer, not per claim, because a claim with secondary coverage goes through adjudication twice, with different dates and possibly different outcomes. One row per claim would have to choose one payer's dates and lose the other's, and "days to payment by payer" and "denial rate by payer" would be wrong.
- Self-pay claims (9,223, with no insurance) have no lifecycle row, because nothing is submitted or adjudicated. Their balances are tracked in the AR snapshot instead.

**Measures:** billed, allowed and paid amounts for that submission; a lag in days for each pair of milestones; a denied flag (1/0, so that summing it gives a denial count and averaging it gives the denial rate).

**Expected rows:** 107,979 primary submissions + 32,754 secondary submissions = 140,733.

## Where adjudication events come from

The source records claims and payments but not adjudication. 99.7% of claims are closed, there are no denials, and most claims are paid on the day of service. So the adjudicated and denied milestones, and the allowed amount, cannot be filled from the source alone.

**Decision:** a seeded adjudication simulator produces them as a separate source.

- It reads claim submissions and writes adjudication events (adjudicated date, outcome, allowed amount, CARC reason code) to its own bronze table. The source data is never changed.
- Its rules are explicit and configurable per payer: denial rate, top denial reasons, and the distribution of adjudication and payment delay. The seed makes every run reproducible.
- Every simulated row carries a `source = 'adjudication_sim'` column, so it can always be told apart from source data.
- The same rules later drive the billing service's traffic generator. Batch and streaming then produce events with the same distributions.

The grain statements above don't depend on this decision. They hold whether the milestone dates come from the source, the simulator or a real payer feed.
