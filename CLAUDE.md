# CLAUDE.md — Operating Instructions for Tupelo-Ops

## Project identity

Tupelo Landscaping LLC is a residential and commercial landscaping business in Arlington, Virginia, running one truck and a small crew, growing toward owner-absent operation ahead of the owner's January 2027 relocation for school. This repository (`Tupelo-Ops`) is its business-operations and financial-model home: strategic planning documents, biweekly check-ins, a from-scratch financial model built on an atomic ledger, and the raw source data (CRM exports, bank statements, contracts) that everything else reconciles against. Full background, locked decisions, and reasoning live in `CONTEXT.md` — read it before undertaking any non-trivial task here.

## Standing rules (govern all work)

1. **Prompt before editing any repository file.** Ask before modifying a file you access in the course of answering — do not edit opportunistically. The business and its timeline are still evolving away from initial predictions, so unreviewed edits compound risk.
2. **Review for staleness at check-ins or plan revisions.** Sequencing and timeline files drift as action items are carried out; when touching them, check whether their content still matches current progress.
3. **Verify quantitative structure before reasoning on it.** Before using any figure from the model or any quantitative file, trace how it is actually computed — read the formulas and the cells/rows they reference, not just displayed values. Never infer a model's internal logic from memory or from what it "should" do. If a needed number isn't explicitly modeled, say so and state what can't be determined from the file alone. Never substitute a plausible assumption for a verified fact and present it as established. A confident wrong answer is worse than a flagged gap — surface uncertainty first, reason second. This applies to every count or dollar figure stated in an explanation, summary, or report to the owner — not just to committed files. Derive it fresh from the actual source at the moment it's stated; do not recall it from an earlier turn's narration, a prior summary, or memory of a similar prior count, even within the same session. If a figure can't be quickly re-verified at the moment of stating it, say so explicitly ("carried over from earlier in this session, not re-checked") rather than presenting it with the same confidence as a freshly-derived one.
4. **Never hardcode numbers into the projection layer.** Every projection value must trace to the data layer (`model/data/`) or a clearly-labeled assumptions file. If a number is needed but doesn't yet exist there, add it as a flagged input — don't inline it into a formula or script.
5. **Flag gaps rather than guess — and ask for the missing data at the point of need.** When information needed to answer or build something isn't in the repository, say so explicitly and propose how to retrieve it, rather than filling the gap with an inference.

    **When a task requires source data that doesn't yet exist here** — a fresh export, an updated bank statement, a document the owner hasn't provided — do **not** wait to be told this in advance, and do **not** silently skip the task:

    a. **Request the specific data, explicitly.** Name exactly what is needed and why the task can't proceed without it. Be precise about the artifact (which export, which date range, which system it comes from), not vague about "more information."
    b. **Do everything that doesn't depend on it.** Complete every independent part in full, and mark only the genuinely dependent part as waiting on the named prerequisite. Use the existing `BLOCKED` convention for this — the same mechanism `model/data/assumptions.csv` already uses, carrying a named `trigger_condition` describing exactly what would unblock it. Extend that established pattern rather than inventing a new one.
    c. **Never fill the gap in the meantime** with a guess, a plausible-looking placeholder, or a stale figure carried over from an earlier session or a prior version of the file.

    The owner has confirmed they will supply updated reports and exports as needed. Requesting them at the moment the need arises is the expected behavior — it is not an imposition, and it is strictly better than proceeding on stale or invented data. Do not require the owner to anticipate in advance what a task will turn out to need.

## Engagement preferences

- Layered answers: direct answer first, then reasoning. Formal, analytical, precise tone — no motivational language or shallow summaries. Optimize for precision, nuance, completeness, and learning value over speed.
- No hallucination or false certainty. Surface assumptions, tradeoffs, risks, and counterarguments explicitly.
- Beginner-friendly explanations that still push toward expert depth — the owner is a self-described technical beginner with a growing interest in AI. Favor iterative collaboration over one-shot comprehensive dumps.
- Actively support the owner's growth in AI use: better prompting, better questions, iterative refinement, token efficiency. Teach engineering-first thinking (structure before function). During ideation, think independently and push back or offer alternatives rather than reflexively agreeing.

## Architecture summary (see CONTEXT.md Section 9 for full spec)

- **D5 — Atomic ledger + derived views.** A single atomic actuals ledger (`model/data/`) is the source of truth: one row per atomic financial event. Every summary (P&L, rollups, revenue by service/customer, blended labor rate) is derived from the ledger by formula, never typed in.
- **D5a — Billing and payment are separate events.** An invoice (billed) and each payment against it (collected), including partial payments, are distinct ledger rows. Billed = sum of invoice events; collected = sum of payment events. Relay bank statements are the source of truth for collected cash, not CRM payment records.
- **D6 — Data layer vs. projection layer, separated.** The data layer (CSV: actuals + flagged estimates) is physically separate from the projection layer (the forward model). The projection layer may only reference derived data-layer values or labeled assumption cells — never a hardcoded number.
- **D7 — Generated workbook.** `model/build_model.py` reads the CSV data layer and generates `model/financial-model.xlsx` as disposable output. The workbook is gitignored, not committed; reproducibility comes from a pinned `model/requirements.txt`, not a stored binary. Dated snapshots are committed to `reference/` only at genuine milestones.

## Model-update operating procedure

This is the standing default for any change to the financial model:

1. Edit the data file(s) or `build_model.py` — never the generated workbook directly.
2. Immediately regenerate the workbook (`python model/build_model.py`) so data and workbook are never out of sync.
3. Report what changed (which rows/cells, which derived views are affected).
4. **Stop for owner review before committing.** Never auto-commit.

**Never hand-edit `financial-model.xlsx`.** If something in the workbook looks wrong, fix the source data or the build script and regenerate — the workbook itself is never a place to make a correction.

The owner may override this per-instance (e.g., "batch several edits before regenerating"), but absent that instruction, follow the loop above every time.

## Pipeline and data-source rules

- **Refresh a `reference/` source → run the pipeline, not just that one step.** Whenever a Relay pull, invoice PDF, payroll export, or catalog snapshot is refreshed, run `model/refresh_all.py` (see `README.md`'s "Model data-refresh pipeline") before treating `build_model.py`'s output as current — or explicitly state which specific downstream scripts are affected and why a full run isn't needed. Never assume refreshing one source alone keeps every derived file in sync.
- **New external data source → the established pattern, not ad hoc handling.** A dated immutable snapshot + an explicit "active" pointer + a standing `*-UPDATE.md` refresh procedure (per `CATALOG-UPDATE.md`/`REVENUE-UPDATE.md`/`PAYROLL-UPDATE.md`) is now a proven, repeated convention — follow it for any new source rather than inventing a new mechanism each time.
- **New `assumptions.csv` row category or ledger schema field → check `build_model.py`'s sheets for it.** New data that isn't surfaced anywhere in the generated workbook is a silent gap, not a neutral addition.

## Ground-truth rule

`reference/` holds raw source data — CRM exports, the P&L report, Relay bank statements, sourced overhead contract figures — and is **never edited**. It is the fixed point everything else (the model, the reconciliation tab, any derived claim) reconciles against. If a figure in `reference/` looks wrong, that's a finding to raise with the owner, not something to silently correct in place.

## File conventions

- Plain text (Markdown/CSV) preferred over binary formats wherever the content allows it.
- Every quantitative row in the data layer carries a status tag: `ACTUAL`, `ESTIMATE`, or `BLOCKED`. Estimates are always flagged as such, never presented as measured. `BLOCKED` means the figure is deliberately not modeled pending a named prerequisite — not silently omitted.
- All repository files use lowercase kebab-case naming (e.g., `execution-timeline.md`), except two intentional uppercase categories: (1) the conventional uppercase root files (`README.md`, `CLAUDE.md`, `CONTEXT.md`, `SETUP.md`, `HISTORY.md`), and (2) the standing `*-UPDATE.md` / `*-PLAN.md` procedure and planning-document pattern, wherever it lives in the tree — `reference/CATALOG-UPDATE.md`, `reference/REVENUE-UPDATE.md`, `reference/PAYROLL-UPDATE.md`, `reference/STRIPE-UPDATE.md`, `model/PHASE7-PLAN.md`, `model/PROJECTION-PLAN.md`, `model/CROSSREF-AUDIT-PLAN.md`. Found and formalized 2026-07-13 (Follow-Up #22 audit, Finding 5): this second category was already established, repeated practice, never previously written into this rule.

## Cross-reference check on structured edits

When editing or revising any multi-section document, verify the *joins*, not only the parts: after a change, confirm that a reader arriving at the changed section can reach any justification, dependency, or definition it relies on without already knowing where that lives — a reason stated in one section must be pointed to from the section where a reader would ask about it. Unlinked or contradictory cross-references, not wrong content, are the dominant failure mode of structured documents like this one. This check is triggered by edits to structured docs (the strategy files, `CONTEXT.md`, this file) — it is not an always-on rule for every file touch.

### Assumption-cell sync (a specific instance of the above)

`model/data/assumptions.csv`'s TARGET/POLICY rows (peak revenue target, cash-buffer composition, Xavier/owner-truck-debt amounts, Konji's phase-switch terms) are sourced from `strategy/strategic-plan.md` and `CONTEXT.md`, not independently authored. Treat each such row and its source figure as a **linked pair, not two facts that happen to currently agree** — the Xavier Assumptions Log row's drift from the Equipment Investment Plan table (H-041) is exactly the failure mode to avoid recurring here. Any edit to a TARGET/POLICY figure in `strategy/` or `CONTEXT.md` must trigger a check of whether `assumptions.csv`'s corresponding row needs the same update, and vice versa.

## History-logging rule

Significant decisions, milestones, revisions, data changes, and tooling changes each get one appended entry in `HISTORY.md` — the master, append-only audit log. Per-file changelog tables embedded in individual documents are secondary convenience only, never the source of truth.

**Arithmetic self-check.** Any `HISTORY.md` entry that presents a total derived from stated sub-figures (a sum, a count, a breakdown by category) must show its addends, not just the total — the entry should be self-verifying by a reader without re-deriving anything. Before such an entry is finalized (staged, not yet committed), recompute the stated sum from its own listed parts and confirm it matches the stated total — the same discipline `parse_invoices.py` and `match_payments.py` apply to their own output before writing it. If it doesn't match, fix the entry before staging it. This extends to illustrative or shorthand arithmetic shown as supporting detail (e.g., a "$X×N + $Y..." breakdown) alongside a total — that shorthand must itself be independently verified to sum correctly, even when the entry's main stated total has already been confirmed correct elsewhere; a correct total does not excuse unverified supporting arithmetic sitting next to it. This rule governs `HISTORY.md` specifically, not every file — it is the canonical audit log, so its own numbers warrant the same rigor as the ledger's.

## RAG-readiness conventions

Keep the repository retrieval-ready at no extra cost: clean semantic sections, front-matter metadata (date, type, status, tags) on documents, atomic well-named files. This is a structural habit maintained now; no vector database or retrieval layer is being adopted yet (see Deferred tooling below).

## Deferred tooling (stated affirmatively)

This project runs a lean stack. Two capabilities are intentionally deferred and **not in use**:

- **Multi-agent orchestration** (Ruflo / claude-flow) — per D9, deferred until a task actually justifies parallel agents. Do not introduce multi-agent orchestration behaviors for this project.
- **Vector database / RAG retrieval layer** (e.g., RuVector) — per D10, deferred until the corpus outgrows the context window or recurring semantic search becomes necessary. Do not adopt RuVector or any specific vector-database dependency for this project preemptively.

This statement holds for this project regardless of any machine-global Claude Code configuration that might otherwise apply. (Checked at authoring time: no `~/.claude/CLAUDE.md` exists in this Codespace, so no global file currently contradicts this — but the instruction is stated here explicitly so it holds even if one is added later or this repo is used from a different machine.)
