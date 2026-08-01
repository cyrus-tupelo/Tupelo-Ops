# reference/ — Ground Truth

This directory holds only **immutable raw sources**: CRM exports, the P&L report, Relay bank statements, invoice PDFs, and sourced overhead contract figures. Everything here is appended, never altered, and never regenerated — nothing in `reference/` is script output. If a figure here looks wrong, that's a finding to raise with the owner, not something to correct in place — corrections flow from here into derived docs (`CONTEXT.md`, the strategy files, `model/data/`), never the other way.

Script-regenerated derivatives (data extracted and reconciled from these raw sources) live in `model/data/` instead — see that directory's contents, `reference/REVENUE-UPDATE.md` for the revenue ledger's update procedure, and `reference/CATALOG-UPDATE.md` for the service catalog's.

## Relay account map

Confirmed by the owner, 2026-07-05 (see `HISTORY.md` H-026):

| Account # | Role | Status |
| --- | --- | --- |
| 8735 | Income | Active |
| 3549 | OpEx | Active |
| 3550 | Reserve | $0 across all 17 months of statements |
| 8737 | Taxes | $0 across all 17 months of statements |
| 8736 | Owner's Comp | Deleted in Relay, 2026-07-05. $0 across all 17 months of statements. |

The `Relay YYYY-MM-DD #NNNN.csv` (or `Relay (Partial) YYYY-MM-DD #NNNN.csv`) files are named by account number. Statements for 3550, 8737, and 8736 are retained even though they're empty — they are the audit substantiation for H-026's $0-balance claim, not dead weight to prune.

## Revenue ledger source

- `invoices_2025-06_2026-06.pdf` — source. 68 invoices, Jun 2025–Jun 2026, as issued. Immutable; never edited or regenerated.

The extracted, reconciled revenue ledgers (`revenue-invoices.csv`, `revenue-line-items.csv`) are **script-regenerated derivatives**, not raw sources, so they live in `model/data/` — not here — and are overwritten only by `model/parse_invoices.py`, never by hand (see `HISTORY.md` H-035 and `reference/REVENUE-UPDATE.md`).

## Payroll journal exports

- `tupelo-landscaping-llc-payroll-summary-2025-04-11-to-2026-04-11.csv` — Gusto "Payroll Journal Report" export, per-employee/per-pay-period detail (hours, rate, gross earnings, employee/employer taxes, net pay), covering pay days 2025-04-11 through 2026-04-11.
- `tupelo-landscaping-llc-payroll-summary-2026-04-11-to-2026-07-09.csv` — the same report type, covering pay days 2026-04-11 through 2026-07-09. Confirmed directly (not assumed): the two files cleanly abut with zero overlapping pay days — the shared "2026-04-11" boundary in both filenames is the report-generation cutoff, not a duplicated period.

Both are owner-supplied, immutable raw sources — filed here verbatim, byte-identical to the originals. **Gusto only exports a rolling window (roughly one year) at a time**, so future pulls will periodically be needed to keep coverage current, the same structural situation the Relay statements and the service catalog are already in.

**The payroll-integration decision has been made (Sequencing Step 5, H-049):** these exports now feed `model/data/ledger-labor.csv` (real, ACTUAL, per-employee/per-pay-period rows, replacing the prior synthetic ESTIMATE) and the `employer-payroll-tax-burden` rows in `model/data/ledger-overhead.csv`, via `model/populate_labor_from_payroll.py`, gated by `model/reconcile_payroll_relay.py`'s full-history reconciliation against Relay. See `reference/PAYROLL-UPDATE.md` for the refresh procedure (how to pull a fresh export, re-run the loader and gate, and what to check).

## Stripe balance-history export

- `stripe-balance-history-2025-07-07-to-2026-07-03.csv` — Stripe's own "balance transaction history" export (74 rows: 40 `charge`, 33 `payout`, 1 `refund`), covering every Stripe-side transaction from the earliest recorded charge (2025-07-07) through the most recent payout (2026-07-03). Owner-supplied, immutable, filed here verbatim — **this is Stripe's own record, independent of both the Relay bank statements and the Homeworks CRM**, not derived from either.

Each `charge` row is one card payment against one or more Homeworks invoices (`Description` field, e.g. `Invoice#74` or `Invoice#34, Invoice#36` for a batched payment), carrying the customer-facing `Amount`, Stripe's actual `Fee`, and the resulting `Net`. Each `payout` row is one batch settlement to the connected bank account (Relay); its `Source`/`Transfer` fields (`po_...` IDs) tie it to the specific `charge` rows swept into it — this is the linkage `model/match_payments.py` did not have when it built the existing `ledger-revenue.csv`/`ledger-overhead.csv` Stripe rows, which is why those rows are tagged `unattributed [aggregated]` rather than matched to individual invoices. The one `refund` row (`REFUND FOR CHARGE (Invoice#40)`, $38.16, 2026-04-07) is a genuine partial refund, not a chargeback — see `HISTORY.md`'s filing entry for this export for the full finding, including why it explains the previously-unresolved $38.16 Stripe debit (Follow-Up #18).

The `(metadata)`-suffixed columns (`stripeProcessingFee`, `customerProcessingFee`, `subtotal`, `tip`, `paymentScope`, `paymentMethodType`, `origin`, `invoiceId`, `companyId`, `customerId`, `estimateId`) are Homeworks' own invoice-side annotations passed through to Stripe at charge time, not Stripe-native fields — see the filing entry for what each was found to represent (confirmed empirically, not assumed) and which of them (`stripeProcessingFee`) does **not** reflect the account's real, negotiated Stripe rate.

**Refresh cadence — resolved (2026-07-12, H-064).** This is now a confirmed live pipeline input: `model/match_payments.py`'s `load_stripe_fee_lookup()` reads every `stripe-balance-history-*.csv` file present and uses it as the ground-truth source for Stripe fee amounts on any payout it covers (true per-charge sums, replacing the 3.9%+$0.30 back-solved estimate for those rows), falling back to the formula only for payouts no export covers — a coverage gap that will otherwise silently grow for any new Stripe payout past 2026-07-03. Following the same established pattern as the payroll and Relay exports, this now has its own dated-snapshot + active-pointer + refresh procedure: see `reference/STRIPE-UPDATE.md`. Unlike Relay/payroll, this refresh has no correctness gate riding on it (the fallback always produces a valid result) — it's a precision refresh, not a data-integrity one; see that file's "Cadence" section.

## Service catalog

**Active snapshot: `service-catalog-2026-07-13.csv`** (21 rows: `Name, Rate Charged to Client, Tax1 %, Tax2 %, Category, Description`; saved verbatim from the Homeworks "Items and Services" export, including its trailing `null` row — not cleaned). This pointer line is the one piece of catalog-tracking data that is allowed to change in place; see `reference/CATALOG-UPDATE.md` for the refresh procedure and the reasoning for using an explicit pointer rather than glob-latest.

**Tax-rate change, 2026-07-13 (H-066):** the owner corrected the catalog's tax settings to match Virginia's actual sales-tax basis — only the 3 `item`-kind rows (`Bagged Mulch`, `Landscaping Blocks (stone)`, `New Plants`) now carry 6% tax; all 18 `service`-kind rows (labor is not taxable in Virginia) carry 0%, down from a prior blanket-6%-on-nearly-everything practice. See `CONTEXT.md` Follow-Up #10 (resolved) for the full history and forward-looking treatment. This snapshot also drops **"Weeding Maintenance"**, discontinued in Homeworks and merged into the existing **"Weeding"** item (owner-confirmed: it was an unused separate name for the same recurring-weeding concept) — mapped as a new legacy alias in `model/data/service-name-map.csv` rather than a rename or reclassification, so no historical invoice re-parse changes any dollar figure.

`model/parse_invoices.py`'s fail-closed gate reads valid catalog names from the active snapshot named above — never a hardcoded list.

**Packages (unbilled):** `service-packages-2026-07-09.csv` transcribes the two Package definitions (`General Maintenance`, `Lawn Care`) from Homeworks' "Packages" tab, owner-confirmed 2026-07-09 by screenshot. As of this snapshot, the Packages feature has **never been used to bill an invoice** — it is a distinct mechanism from the informal `General Maintenance` / `Lawn Care` / `Lawn Maintenance` bundle labels already present as literal invoice text in `model/data/revenue-line-items.csv`. Same names, different mechanism — see `reference/CATALOG-UPDATE.md`'s "Packages feature vs. bundle labels" section before conflating the two in any file.

Item-vs-service classification (which of the 21 catalog rows are billable materials vs. labor) lives in `model/data/catalog-type-map.csv` — a script-input derivative, not a raw source, so it's in `model/data/` rather than here.

## Homeworks published pricing

**Active pricing snapshot: `homeworks-pricing-2026-07-31.md`** — the vendor's own published price list for all three plan tiers (Solo / Growth / Enterprise), transcribed verbatim from `https://www.home.works/pricing` on 2026-07-31. Covers plan prices at both billing cadences, included-user counts, additional-seat rate, contact caps, card-processing rates, SMS segment pricing, and the ACH fee cap. See `reference/HOMEWORKS-PRICING-UPDATE.md` for the refresh procedure.

**This section's pointer label is deliberately `Active pricing snapshot`, not `Active snapshot`.** The latter is the service catalog's pointer above, which `model/parse_invoices.py:118` regex-searches for across this entire file, taking the first match — a second `**Active snapshot:**` line would silently redirect the invoice parser to the wrong file. Keep the labels distinct. This section is also placed *after* the Service catalog section so the catalog's pointer is reached first regardless.

Unlike every other source here, this one is **not an export** — it is a live vendor marketing page read by hand, so it has no coverage window, no machine-readable original, and no gate. A stale snapshot fails silently rather than erroring. The binding refresh trigger is therefore behavioural, not scheduled: re-read the page in the same session any decision under `CONTEXT.md` Follow-Up #30 is actually made.

Snapshots are the authority for **tiers the business is not on** (Enterprise pricing, the annual-billing option) and for structural facts (seat counts, contact caps, published rates). They are **not** the authority for what the business actually pays — that is `model/data/ledger-overhead.csv`'s `Homeworks (CRM)` / `crm-subscription` rows, summarized in `reference/fixed-overhead.md`. `model/data/assumptions.csv` deliberately stores no Growth `$299` constant for this reason; see the snapshot's "Relationship to other files" section.

## Canonical record & change protocol

This table is the **canonical** repo record of the Relay account map. It is also restated, as context, in `CONTEXT.md`'s Relay line. If the account structure ever changes: update this table and `CONTEXT.md`'s Relay line — the two live copies — and add a **new** `HISTORY.md` entry. Never edit H-026 or any past entry; H-026 is a frozen 2026-07-05 snapshot, not a live copy.
