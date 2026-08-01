# Tupelo-Ops

Business-operations and financial-model repository for Tupelo Landscaping LLC — strategic planning, biweekly check-ins, a from-scratch financial model built on an atomic ledger, and the raw source data everything reconciles against.

## Structure

```
strategy/     One-year strategic plan, operational toolkit, execution timeline.
check-ins/    Biweekly check-in template + dated check-in logs.
model/
  data/         Atomic ledger + assumption tables (CSV) — source of truth.
  build_model.py  Generates the workbook from data/.
  requirements.txt  Pinned Python dependencies (e.g. openpyxl).
  homeworks_plan_analysis.py  Standalone Growth-vs-Enterprise plan analysis (not a pipeline stage).
  financial-model.xlsx  Generated output — gitignored, regenerated on demand, never hand-edited.
reference/    Raw source data (CRM exports, P&L, bank statements, overhead contracts, Gusto payroll exports) — ground truth, never edited.
.gitignore    Excludes the generated workbook and transient build artifacts.
```

## Model data-refresh pipeline

The five ledgers in `model/data/` are built and kept current by a fixed sequence of scripts, each owning a disjoint set of ledger rows and safe to re-run on its own. `python model/refresh_all.py` runs all seven stages in the correct order and halts immediately if any stage's reconciliation check fails:

1. **`model/parse_invoices.py`** — Homeworks invoice PDF → `revenue-invoices.csv` / `revenue-line-items.csv`.
2. **`model/build_ledger_revenue.py`** — those CSVs → `ledger-revenue.csv`'s invoice/surcharge/tip rows.
3. **`model/match_payments.py`** — Relay bank statements → `ledger-revenue.csv`'s payment rows + `ledger-overhead.csv`'s Stripe fee rows. Also reads `reference/stripe-balance-history-*.csv` when present, using it as the ground-truth source for those Stripe fee amounts (true per-charge sums) rather than the back-solved 3.9%+$0.30 fallback formula (H-062).
4. **`model/populate_step4.py`** — Relay bank statements → `ledger-overhead.csv`'s remaining categories, `ledger-materials.csv`, `ledger-capital.csv`.
5. **`model/populate_labor_from_payroll.py`** — Gusto payroll exports → `ledger-labor.csv` + `ledger-overhead.csv`'s employer-payroll-tax-burden rows.
6. **`model/reconcile_payroll_relay.py`** — full-history gate: payroll totals vs. Relay bank transactions.
7. **`model/build_model.py`** — all five ledgers → `financial-model.xlsx`.

See `reference/CATALOG-UPDATE.md`, `reference/REVENUE-UPDATE.md`, `reference/PAYROLL-UPDATE.md`, `reference/STRIPE-UPDATE.md`, and `reference/HOMEWORKS-PRICING-UPDATE.md` for when and how to refresh the underlying raw sources (`reference/`) before re-running this pipeline.

## Analysis scripts (outside the pipeline)

`model/homeworks_plan_analysis.py` is **not** one of the seven stages above — it builds no ledger and writes no file. It evaluates the Homeworks Growth-vs-Enterprise switch point (`CONTEXT.md` Follow-Up #30) from `model/data/assumptions.csv`'s `saas_pricing` constants plus real card volume from the Stripe export, and prints where the business currently sits against three independent triggers. `model/build_model.py` imports the same functions to render the workbook's "Plan Tier Analysis" sheet, so the two cannot disagree. Run it directly with `python model/homeworks_plan_analysis.py`.

## Start here

- **`CONTEXT.md`** — full project background, locked decisions, and reasoning.
- **`CLAUDE.md`** — operating rules for Claude Code in this repository.
- **`SETUP.md`** — environment setup for a fresh Codespace.
- **`HISTORY.md`** — append-only audit log of decisions, milestones, and data changes.
