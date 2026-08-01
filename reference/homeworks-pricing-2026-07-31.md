# Homeworks Published Pricing — Snapshot 2026-07-31

**Source:** `https://www.home.works/pricing`
**Fetched:** 2026-07-31
**Method:** direct page fetch, transcribed verbatim. No export exists for this source — it is a live marketing page, read by hand.
**Status:** immutable snapshot. Never edit this file. A refresh creates a new dated file; see `reference/HOMEWORKS-PRICING-UPDATE.md`.

This is the vendor's own published price list for **all three plan tiers**, independent of what this business currently pays. What the business actually pays is a separate fact recorded in `model/data/ledger-overhead.csv` (`Homeworks (CRM)` / `crm-subscription` rows) and summarized in `reference/fixed-overhead.md` — see "Relationship to other files" below.

---

## Plan tiers

| | Solo | Growth | Enterprise |
| --- | --- | --- | --- |
| Monthly billing | — | **$299 /mo** | **$499 /mo** |
| Annual billing (effective monthly) | — | **$219 /mo** | **$379 /mo** |
| Stated annual saving | — | "Save $960 with annual plan" | "Save $1440 with annual plan" |
| Included users | — | **up to 10** | **up to 20** |
| Contact limit | **50** | **1,000** | **5,000** |
| Card processing | 3.9% + 30¢ | **3.9% + 30¢** | **2.9% + 30¢** |
| SMS | 3¢ per segment | 3¢ per segment | **1,000 segments/month included** |
| ACH | — | "reduced ACH processing fees, capped at $5" | "reduced ACH processing fees, capped at $5" |

Solo-tier figures are transcribed only where the page states them; this business is on Growth and the Solo tier is not under consideration.

## Verbatim quotes

- Growth monthly: `$299 /mo`
- Growth annual: `$299 219 /mo` — struck-through list price beside the discounted figure; page copy: `Save $960 with annual plan`
- Enterprise monthly: `$499 /mo`
- Enterprise annual: `$499 379 /mo`; page copy: `Save $1440 with annual plan`
- Additional seats: `Add more seats for $15/month per user.` — appears in the shared feature-comparison table under the `Included users` row, i.e. presented as a policy spanning all tiers, **not** inside any single plan's own section.
- Annual billing generally: `OVER 20% OFF`
- ACH: `Reduce your costs with reduced ACH processing fees, capped at $5.`
- SMS rate: `3¢ per segment`
- Enterprise SMS allowance: `1,000` segments monthly included

### Arithmetic self-check on the transcribed figures

- Growth cadence delta: `$299 − $219 = $80/mo`; `$80 × 12 = $960` — matches the page's stated "Save $960".
- Enterprise cadence delta: `$499 − $379 = $120/mo`; `$120 × 12 = $1,440` — matches the page's stated "Save $1440".
- Monthly-billing plan gap: `$499 − $299 = $200/mo`.
- Annual-billing plan gap: `$379 − $219 = $160/mo`.
- Enterprise included-seat advantage: `(20 − 10) × $15 = $150/mo` — **less than both plan gaps** (see `CONTEXT.md` Follow-Up #30, trigger 3).

---

## Stated nowhere on this page

Recorded so a future session does not re-search for these and conclude they were simply missed. Each was actively looked for on 2026-07-31 and is **absent**:

1. **Enterprise's SMS overage rate past the 1,000 included segments.** The page gives Growth's 3¢/segment and Enterprise's 1,000-segment allowance, but never states what an Enterprise segment costs beyond the allowance. It is *plausibly* also 3¢, but the page does not say so and this is not assumed anywhere in this repo.
2. **Whether Field Force (the separate Homeworks mobile app for crews, formerly Copilot CRM) consumes a plan user seat**, or whether mobile-only crew users are a distinct seat type from full CRM users. The page draws no such distinction. Not found in public documentation either.
3. **The ACH percentage rate.** Only the `$5` cap is published. The owner has separately stated 0.8% (see `CONTEXT.md` Follow-Up #32) — the cap is now corroborated by the vendor's own copy, the percentage is not.
4. **Whether annual billing is charged as a single upfront lump sum** or as twelve monthly installments at the discounted rate. Materially different cash-flow events.
5. **Contract or commitment length** on the annual plan.
6. **What happens on reaching the contact cap** — hard block on new contacts, forced/auto upgrade, or an overage charge. This determines how urgent the contact-count trigger is.

No footnotes, asterisks, or fine print anywhere on the page address any of the above.

---

## Relationship to other files — read before adding any figure to the model

Three files now touch Homeworks pricing. They are **not** interchangeable:

- **This file** — the vendor's published list prices for every tier, including tiers the business is not on. Sourced from the public page, dated, immutable.
- **`model/data/ledger-overhead.csv`** — what the business has actually been charged, per month, per Relay. The ground truth for real cost. Shows `$139.00/mo` (payee "Copilot", the prior product name) through 2026-05-25, then `$299.00/mo` (payee "HOMEWORKS SOFTWARE") from 2026-06-25.
- **`reference/fixed-overhead.md`** — the contracted-overhead summary; its Homeworks row already records the `$299/mo` current cost and the `$2,628/yr` annual option as "a future election 'when capital allows,' not current."

**Deliberate non-duplication:** `model/data/assumptions.csv` stores the *Enterprise* and *annual-option* figures from this file as `REFERENCE` rows, but does **not** store a Growth `$299` constant. The Growth side of any plan-cost comparison is derived at run time from the most recent `crm-subscription` ledger row, because that is the real contracted cost and it self-corrects if the rate changes. Adding a fourth copy of `$299` would recreate the H-041 drift failure mode.

Also per `reference/fixed-overhead.md`'s own note: the flat monthly subscription and the transactional 1% Homeworks platform markup on card payments (H-063) are structurally unrelated costs that merely share the Homeworks name. Never conflate them.

---

## Caveat on this source type

Unlike every other source in `reference/`, this one has **no export and no gate**. It is a live vendor marketing page that can change at any time with no notification and no diff. A stale snapshot fails silently — the numbers simply become wrong while continuing to look authoritative. Re-verify before acting on any decision that rests on it; see `reference/HOMEWORKS-PRICING-UPDATE.md`.
