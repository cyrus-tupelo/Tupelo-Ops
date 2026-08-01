#!/usr/bin/env python3
"""Growth-vs-Enterprise switch-point analysis for the Homeworks CRM plan.

Usage:
    python model/homeworks_plan_analysis.py

Answers one question: how far is this business from the point at which
upgrading Homeworks from Growth to Enterprise pays for itself? Per
CONTEXT.md Follow-Up #30 that is not one number but three independent
triggers, any ONE of which can force the upgrade on its own:

  1. Revenue/margin -- the card-processing rate gap plus the SMS allowance,
     weighed against the plan-price delta. This is the only trigger this
     script can actually evaluate, because it is the only one whose inputs
     exist in the repo.
  2. Contact cap -- a hard limit, not a cost tradeoff. NOT COMPUTABLE HERE:
     no repo file records a CRM contact count.
  3. Seat count -- see delta_effective(). Not an independent trigger at all
     (proven below); it only modulates trigger 1's delta.

Deliberate design: the two unknown inputs (outbound SMS segment volume,
seat count) are NOT guessed. The script prints trigger 1 as a threshold
SURFACE across a range of both, so the reader can locate the business once
the real figures are pulled. Inventing a midpoint would produce a
confident wrong answer, which this repo treats as worse than a flagged gap.

Every pricing constant is read from model/data/assumptions.csv (category
saas_pricing), which is sourced in turn from a dated immutable snapshot of
the vendor's published pricing -- never hardcoded here, per D6 and
CLAUDE.md's no-hardcoded-numbers rule. The only bare numerals below are
unit conversions (months per year, percent-to-fraction), not financial
facts.

This is analysis, not ledger construction: it is NOT one of
model/refresh_all.py's seven pipeline stages and writes no file. It is
also imported by model/build_model.py, which renders the same computation
into the workbook's "Plan Tier Analysis" sheet -- the math lives here
once so the sheet and the CLI cannot drift.
"""
import calendar
import csv
import glob
import re
from collections import defaultdict

ASSUMPTIONS_PATH = "model/data/assumptions.csv"
OVERHEAD_LEDGER_PATH = "model/data/ledger-overhead.csv"
STRIPE_BALANCE_HISTORY_GLOB = "reference/stripe-balance-history-*.csv"
RELAY_GLOB = "reference/Relay*.csv"

# The ledger category/subcategory pair identifying the CRM subscription.
CRM_CATEGORY = "Homeworks (CRM)"
CRM_SUBCATEGORY = "crm-subscription"
# Payee substrings Homeworks has billed under. "Copilot" is the product's
# prior name (per the ledger's own row notes) -- both must be matched or the
# pre-2026-06 history is invisible.
HOMEWORKS_PAYEE_RE = re.compile(r"homeworks|copilot", re.IGNORECASE)

MONTHS_PER_YEAR = 12  # unit conversion, not an assumption


# --------------------------------------------------------------------------
# Data-layer loading
# --------------------------------------------------------------------------

def load_assumptions(path=ASSUMPTIONS_PATH):
    with open(path, newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    return list(csv.DictReader(lines))


def constant(assumptions, assumption_id):
    """Return one REFERENCE/CONTRACTED constant's float value.

    Raises on a BLOCKED row rather than returning its placeholder 0.00 --
    a BLOCKED figure is deliberately not modelled, and silently reading it
    as zero is exactly the substitution this repo's flag-gaps rule forbids.
    """
    rows = [r for r in assumptions if r["assumption_id"] == assumption_id]
    if len(rows) != 1:
        raise ValueError(f"{assumption_id}: expected exactly 1 row, got {len(rows)}")
    row = rows[0]
    if row["status"] == "BLOCKED":
        raise ValueError(
            f"{assumption_id} is BLOCKED ({row['trigger_condition']}) -- "
            "not modelled; do not read its placeholder value as a real figure."
        )
    return float(row["value"])


def is_blocked(assumptions, assumption_id):
    rows = [r for r in assumptions if r["assumption_id"] == assumption_id]
    return bool(rows) and rows[0]["status"] == "BLOCKED"


def load_pricing(assumptions):
    return {
        "ent_monthly": constant(assumptions, "homeworks_enterprise_monthly_price"),
        "ent_annual": constant(assumptions, "homeworks_enterprise_annual_effective_price"),
        "growth_annual": constant(assumptions, "homeworks_growth_annual_effective_price"),
        "seat_price": constant(assumptions, "homeworks_additional_seat_price"),
        "growth_seats": int(constant(assumptions, "homeworks_growth_included_users")),
        "ent_seats": int(constant(assumptions, "homeworks_enterprise_included_users")),
        "growth_contacts": int(constant(assumptions, "homeworks_growth_contact_limit")),
        "ent_contacts": int(constant(assumptions, "homeworks_enterprise_contact_limit")),
        "growth_card_pct": constant(assumptions, "homeworks_growth_card_rate_pct"),
        "ent_card_pct": constant(assumptions, "homeworks_enterprise_card_rate_pct"),
        "card_fixed": constant(assumptions, "homeworks_card_fixed_fee"),
        "sms_rate": constant(assumptions, "homeworks_sms_segment_rate"),
        "sms_included": int(constant(assumptions, "homeworks_enterprise_sms_included_segments")),
    }


def growth_current_cost(path=OVERHEAD_LEDGER_PATH):
    """Derive the Growth side of the plan-cost delta from what the business
    is actually charged, not from a stored list price.

    Deliberate: assumptions.csv holds no Growth price constant. The real
    contracted cost lives in the ledger, already ground-truthed against
    Relay, and self-corrects if the rate ever changes or is negotiated --
    a stored duplicate could silently drift from it (the H-041 pattern).

    Returns (amount, month, all_rows_newest_first).
    """
    with open(path, newline="") as f:
        rows = [
            r for r in csv.DictReader(f)
            if r["category"] == CRM_CATEGORY and r["subcategory"] == CRM_SUBCATEGORY
        ]
    if not rows:
        raise RuntimeError(
            f"no {CRM_CATEGORY}/{CRM_SUBCATEGORY} rows in {path} -- cannot derive "
            "the current Growth plan cost. Refusing to substitute a list price."
        )
    rows.sort(key=lambda r: r["date"], reverse=True)
    return float(rows[0]["amount"]), rows[0]["date"][:7], rows


def monthly_card_volume(pattern=STRIPE_BALANCE_HISTORY_GLOB):
    """Sum gross card-charge dollars per calendar month from Stripe's own export.

    Modelling decisions, both verified against the export rather than assumed:

    * Only `Type == "charge"` rows count. `payout` rows are settlement sweeps
      of those same charges (double-counting), and the single `refund` row is
      excluded because Stripe did NOT reverse the processing fee on it -- the
      refund row carries Fee 0.00 while the original charge retains its full
      fee. The plan-rate saving is therefore earned on the original gross,
      which a refund does not claw back.
    * `Amount` is gross (customer-facing, pre-fee); `Net` is post-fee. The
      percentage rate applies to gross, so gross is the correct base.
    * Bucketed by `Created (UTC)`, the transaction date, not `Available On`,
      which is the settlement date and can fall in the next month.
    * Deduplicated by Stripe's own `id`, matching match_payments.py -- once a
      second export exists the date windows will overlap.

    Returns (amount_by_month, charge_count_by_month, files, coverage_end).
    Counts are returned per month, not as one total, so any figure quoted
    for a sub-window (e.g. a trailing-12 slice) carries its own charge count
    rather than borrowing the whole export's -- the exact error this
    return shape exists to prevent.

    `coverage_end` is the latest `Created (UTC)` date across ALL row types,
    not just charges -- the export's true coverage boundary. It is returned
    so callers can detect the case where the window's final month is only
    partially covered: a month cut off after a few days looks like a
    genuinely low month, which silently understates any window containing
    it. A zero-activity month and an unobserved month are not the same
    thing, and nothing else in the data distinguishes them.
    """
    files = sorted(glob.glob(pattern))
    if not files:
        return {}, {}, [], None

    seen = set()
    by_month = defaultdict(float)
    count_by_month = defaultdict(int)
    coverage_end = None
    for fn in files:
        with open(fn, newline="") as f:
            for row in csv.DictReader(f):
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                created = row["Created (UTC)"][:10]
                if coverage_end is None or created > coverage_end:
                    coverage_end = created
                if row["Type"] != "charge":
                    continue
                by_month[row["Created (UTC)"][:7]] += float(row["Amount"])
                count_by_month[row["Created (UTC)"][:7]] += 1
    return dict(by_month), dict(count_by_month), files, coverage_end


def homeworks_usage_charges(assumptions, pattern=RELAY_GLOB):
    """Find Homeworks debits in Relay that are NOT the flat subscription.

    Why this exists: CONTEXT.md Follow-Up #30's SMS input is nominally
    unknowable from the repo. But Relay records Homeworks debits that the
    overhead ledger does not carry, and if any is an exact whole-segment
    multiple of the published SMS rate, that is real (if circumstantial)
    evidence of outbound segment volume -- the one unknown input the repo
    may actually be able to speak to. Reported as candidates requiring
    confirmation against a real Homeworks invoice, never as fact.
    """
    sms_rate = constant(assumptions, "homeworks_sms_segment_rate")
    _, _, subscription_rows = growth_current_cost()
    known = {(r["date"], round(float(r["amount"]), 2)) for r in subscription_rows}

    seen = set()
    found = []
    for fn in sorted(glob.glob(pattern)):
        with open(fn, newline="") as f:
            for row in csv.DictReader(f):
                payee = row.get("Payee") or ""
                if not HOMEWORKS_PAYEE_RE.search(payee):
                    continue
                amount = float(row["Amount"])
                if amount >= 0:
                    continue
                m, d, y = row["Date"].split("/")
                iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                key = (iso, round(abs(amount), 2), payee)
                if key in seen:  # partial-window Relay files overlap
                    continue
                seen.add(key)
                if (iso, round(abs(amount), 2)) in known:
                    continue  # the flat subscription, already booked
                segments = abs(amount) / sms_rate
                found.append({
                    "date": iso,
                    "payee": payee,
                    "amount": round(abs(amount), 2),
                    "segments": segments,
                    "exact": abs(segments - round(segments)) < 1e-9,
                })
    found.sort(key=lambda r: r["date"])
    return found, sms_rate


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------

def plan_cost(base, included_seats, seats, seat_price):
    """Monthly cost of a plan at a given seat count."""
    return base + seat_price * max(0, seats - included_seats)


def delta_effective(seats, growth_base, ent_base, p):
    """Enterprise cost minus Growth cost, at a given total seat count.

    This is the whole of trigger 3. There is no seat count at which it goes
    negative: Enterprise's extra included seats are worth
    (ent_seats - growth_seats) * seat_price, which is less than either
    plan-price gap, and beyond ent_seats both plans slope identically at
    seat_price per seat -- so the delta shrinks to a floor and pins there.
    Seats therefore never justify an upgrade on their own; they only reduce
    the revenue volume trigger 1 needs.
    """
    return (plan_cost(ent_base, p["ent_seats"], seats, p["seat_price"])
            - plan_cost(growth_base, p["growth_seats"], seats, p["seat_price"]))


def sms_saving(segments, p):
    """Monthly SMS saving from Enterprise's included allowance.

    Assumes Enterprise's overage rate equals Growth's. That rate is NOT
    published (assumptions.csv row homeworks_enterprise_sms_overage_rate is
    BLOCKED). If it is higher than Growth's, this saving DECLINES above the
    allowance and can go negative -- so the ceiling below is conditional.
    """
    return p["sms_rate"] * min(segments, p["sms_included"])


def breakeven_card_volume(delta, segments, p):
    """Monthly card-processed gross dollars at which upgrading breaks even.

    Returns None when the SMS saving alone already exceeds the plan delta,
    i.e. the threshold is crossed at any card volume including zero.
    """
    rate_gap = (p["growth_card_pct"] - p["ent_card_pct"]) / 100.0
    residual = delta - sms_saving(segments, p)
    if residual <= 0:
        return None
    return residual / rate_gap


def calendar_window(last_month, n):
    """The n consecutive calendar months ending at last_month (YYYY-MM)."""
    y, m = map(int, last_month.split("-"))
    out = []
    for back in range(n - 1, -1, -1):
        mm = m - back
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        out.append(f"{yy:04d}-{mm:02d}")
    return out


def seat_scenarios(p):
    """Seat brackets to display, derived from the plans' own included counts."""
    mid = (p["growth_seats"] + p["ent_seats"]) // 2
    beyond = p["ent_seats"] + (p["ent_seats"] - mid)
    return [p["growth_seats"], mid, p["ent_seats"], beyond]


def sms_scenarios(p):
    """Segment-volume brackets, derived from the allowance itself."""
    return [0, p["sms_included"] // 2, p["sms_included"]]


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def money(x):
    return f"${x:,.2f}"


def build_report_rows(assumptions):
    """Produce the analysis as a list of row-lists.

    Shared verbatim by the CLI below and build_model.py's "Plan Tier
    Analysis" sheet, so the workbook and the terminal cannot disagree.
    """
    p = load_pricing(assumptions)
    growth_now, growth_month, sub_rows = growth_current_cost()
    by_month, count_by_month, stripe_files, coverage_end = monthly_card_volume()
    usage, sms_rate = homeworks_usage_charges(assumptions)

    rows = []
    add = rows.append

    add(["Homeworks Growth vs Enterprise -- switch-point analysis"])
    add(["Pricing constants: model/data/assumptions.csv (category saas_pricing),"])
    add(["sourced from reference/homeworks-pricing-2026-07-31.md. Live vendor page --"])
    add(["re-verify per reference/HOMEWORKS-PRICING-UPDATE.md before acting on this."])
    add([])

    # --- Current state -----------------------------------------------------
    add(["CURRENT STATE (derived, not stored)"])
    add(["Growth cost actually paid", money(growth_now), f"most recent ledger month {growth_month}"])
    add(["  source", OVERHEAD_LEDGER_PATH, f"{len(sub_rows)} crm-subscription rows"])
    add(["Enterprise list price (monthly)", money(p["ent_monthly"])])
    add(["Plan delta at current seats", money(p["ent_monthly"] - growth_now)])
    add(["Annual-cadence counterfactual",
         money(p["ent_annual"] - p["growth_annual"]),
         f"Growth {money(p['growth_annual'])} vs Enterprise {money(p['ent_annual'])} -- business is on MONTHLY billing"])
    add([])

    # --- Trigger 3 first: it sets trigger 1's delta ------------------------
    add(["TRIGGER 3 -- SEATS (not an independent trigger)"])
    seat_gain = (p["ent_seats"] - p["growth_seats"]) * p["seat_price"]
    add([f"Enterprise's {p['ent_seats'] - p['growth_seats']} extra included seats are worth",
         money(seat_gain),
         f"= ({p['ent_seats']} - {p['growth_seats']}) x {money(p['seat_price'])}"])
    add(["Monthly plan-price gap", money(p["ent_monthly"] - growth_now)])
    add(["Annual plan-price gap", money(p["ent_annual"] - p["growth_annual"])])
    add(["=> Enterprise NEVER becomes cheaper on seats alone, at any seat count."])
    add(["   Seats only shrink the delta trigger 1 must overcome:"])
    add(["Seats", "Growth cost", "Enterprise cost", "Delta (monthly)", "Delta (annual cadence)"])
    for n in seat_scenarios(p):
        add([n,
             money(plan_cost(growth_now, p["growth_seats"], n, p["seat_price"])),
             money(plan_cost(p["ent_monthly"], p["ent_seats"], n, p["seat_price"])),
             money(delta_effective(n, growth_now, p["ent_monthly"], p)),
             money(delta_effective(n, p["growth_annual"], p["ent_annual"], p))])
    add(["UNKNOWN: how many Homeworks seats are actually in use, and whether"])
    add(["Field Force (crew mobile app) users consume one. Neither is in any repo"])
    add(["file; employee-role-map.csv holds payroll roles, not CRM seat assignments."])
    add([])

    # --- Trigger 1 ---------------------------------------------------------
    rate_gap = p["growth_card_pct"] - p["ent_card_pct"]
    add(["TRIGGER 1 -- REVENUE / MARGIN"])
    add([f"Card rate gap: {p['growth_card_pct']}% - {p['ent_card_pct']}% = {rate_gap}%",
         f"per-charge fixed fee {money(p['card_fixed'])} is identical on both plans and cancels"])
    add(["=> transaction COUNT is irrelevant; only card dollar VOLUME matters."])
    add([f"SMS allowance ceiling: {p['sms_included']} x {money(p['sms_rate'])} = "
         f"{money(p['sms_included'] * p['sms_rate'])}/mo -- a CEILING, worth $0.00 below that volume."])
    add([])
    add(["Break-even monthly card-processed gross, by seats and outbound segments:"])
    header = ["Seats", "Delta"] + [f"{s} seg/mo" for s in sms_scenarios(p)]
    add(header)
    for n in seat_scenarios(p):
        d = delta_effective(n, growth_now, p["ent_monthly"], p)
        line = [n, money(d)]
        for s in sms_scenarios(p):
            be = breakeven_card_volume(d, s, p)
            line.append("already crossed" if be is None else money(be))
        add(line)
    add(["(annual-billing cadence, for comparison -- business is NOT on this)"])
    add(header)
    for n in seat_scenarios(p):
        d = delta_effective(n, p["growth_annual"], p["ent_annual"], p)
        line = [n, money(d)]
        for s in sms_scenarios(p):
            be = breakeven_card_volume(d, s, p)
            line.append("already crossed" if be is None else money(be))
        add(line)
    add([])

    # --- Where the business actually sits ---------------------------------
    add(["ACTUAL CARD VOLUME (from Stripe's own export -- the one input the repo has)"])
    if not by_month:
        add(["No reference/stripe-balance-history-*.csv present -- card volume unknown."])
    else:
        months = sorted(by_month)
        total = sum(by_month.values())
        add(["Source", "; ".join(stripe_files)])
        add(["Charges counted", sum(count_by_month.values()),
             f"in {len(months)} months with activity, spanning {months[0]} to {months[-1]}"])
        add(["Total gross card volume", money(total)])
        add(["Mean per month", money(total / len(months))])
        peak = max(months, key=lambda m: by_month[m])
        add(["Peak month", peak, money(by_month[peak])])
        add(["Month", "Card gross", "Charges"])
        for m in months:
            add([m, money(by_month[m]), count_by_month[m]])
        add([])
        add(["Annualized comparison (the right frame -- revenue is seasonal,"])
        add(["a plan decision is not; a threshold met in June is not met in January):"])
        # Sum over the trailing 12 CALENDAR months, not the trailing 12
        # months that happen to have activity -- a month with no card charge
        # is a real $0, and dropping it would understate the annual window's
        # length and so overstate the business's position against the
        # threshold. Zero-activity months are counted as zero, not skipped.
        window = calendar_window(months[-1], MONTHS_PER_YEAR)
        v_year = sum(by_month.get(m, 0.0) for m in window)
        gaps = [m for m in window if m not in by_month]
        n_window = sum(count_by_month.get(m, 0) for m in window)
        add([f"Card gross, trailing {MONTHS_PER_YEAR} calendar months",
             money(v_year), f"{window[0]} to {window[-1]}",
             f"{n_window} charges (NOT the export's full "
             f"{sum(count_by_month.values())} -- earlier months fall outside this window)"])
        # The export's coverage can end mid-month. That final month then
        # looks like a genuinely low month rather than an unobserved one,
        # which understates the whole window. Detected from the data, not
        # assumed from the filename.
        if coverage_end and coverage_end[:7] == window[-1]:
            y, mo = map(int, window[-1].split("-"))
            days_in_month = calendar.monthrange(y, mo)[1]
            day_covered = int(coverage_end[-2:])
            if day_covered < days_in_month:
                add([f"  *** PARTIAL FINAL MONTH: the export ends {coverage_end}, so "
                     f"{window[-1]} covers only {day_covered} of {days_in_month} days."])
                add([f"      {money(v_year)} therefore UNDERSTATES true trailing-{MONTHS_PER_YEAR}-month volume."])
                add(["      Treat it as directional. Refresh against a newer Stripe export"])
                add(["      (reference/STRIPE-UPDATE.md) before relying on it as a measurement."])
        if gaps:
            add(["  zero-activity months in that window", ", ".join(gaps),
                 "counted as $0.00, not skipped"])
        for label, gb, eb in (("monthly cadence", growth_now, p["ent_monthly"]),
                              ("annual cadence", p["growth_annual"], p["ent_annual"])):
            d = delta_effective(p["growth_seats"], gb, eb, p)
            for s in (0, p["sms_included"]):
                be = breakeven_card_volume(d, s, p)
                if be is None:
                    add([f"Annual threshold ({label}, {s} seg/mo)", "already crossed"])
                    continue
                need = be * MONTHS_PER_YEAR
                add([f"Annual threshold ({label}, {s} seg/mo)", money(need),
                     f"business is at {100 * v_year / need:.1f}% of it"])
    add([])

    # --- Trigger 2 ---------------------------------------------------------
    add(["TRIGGER 2 -- CONTACT CAP (hard limit, NOT COMPUTABLE FROM THIS REPO)"])
    add(["Growth cap", p["growth_contacts"], "contacts"])
    add(["Enterprise cap", p["ent_contacts"], "contacts"])
    add(["At or near the Growth cap an upgrade is FORCED regardless of triggers 1 and 3."])
    add(["No repo file records a CRM contact count. This must be pulled from Homeworks."])
    add(["Note: canvassing (Follow-Ups #5, #11) generates contacts far faster than it"])
    add(["generates revenue, so this trigger can fire while trigger 1 is nowhere close."])
    add(["Also unpublished: what Homeworks does AT the cap (block / auto-upgrade /"])
    add(["overage bill) -- that determines urgency."])
    add([])

    # --- The SMS lead ------------------------------------------------------
    add(["OUTBOUND SMS VOLUME -- candidate evidence found in Relay"])
    add(["Homeworks debits in reference/Relay*.csv with no crm-subscription ledger row."])
    add(["A whole-number segment count is circumstantial evidence of SMS billing,"])
    add(["NOT proof. Confirm against a real Homeworks invoice before relying on it."])
    if not usage:
        add(["None found."])
    else:
        add(["Date", "Payee", "Amount", f"/ {money(sms_rate)}", "Whole segments?"])
        for u in usage:
            add([u["date"], u["payee"], money(u["amount"]),
                 f"{u['segments']:.2f}", "EXACT" if u["exact"] else "no"])
        exact = [u for u in usage if u["exact"]]
        if exact:
            add([f"{len(exact)} of {len(usage)} are exact whole-segment multiples."])
            biggest = max(exact, key=lambda u: u["segments"])
            add([f"Largest implies {round(biggest['segments'])} outbound segments in one month",
                 f"vs the {p['sms_included']}-segment allowance"])
            if round(biggest["segments"]) > p["sms_included"]:
                add(["=> If confirmed, volume EXCEEDS the allowance: the SMS saving would"])
                add([f"   reach its full {money(p['sms_included'] * p['sms_rate'])}/mo ceiling, AND the unpublished"])
                add(["   Enterprise overage rate would become load-bearing for the excess."])
    add([])

    # --- ACH: why it contributes nothing to the upgrade case ---------------
    add(["ACH -- WHY IT PRODUCES NO UPGRADE SAVING (Follow-Up #32 interaction)"])
    if is_blocked(assumptions, "homeworks_ach_rate_pct"):
        add(["ACH rate is BLOCKED; only the $5 cap is known."])
    else:
        ach_rate = constant(assumptions, "homeworks_ach_rate_pct")
        ach_cap = constant(assumptions, "homeworks_ach_fee_cap")
        # Derived, not stored: the transaction size at which the flat cap
        # starts binding instead of the percentage.
        cap_at = ach_cap / (ach_rate / 100.0)
        add([f"ACH rate {ach_rate}% capped at {money(ach_cap)}",
             f"cap binds at {money(cap_at)} ({ach_rate}% x {money(cap_at)} = {money(ach_cap)})"])
        add(["Above that the effective rate FALLS with transaction size -- unlike card,"])
        add([f"whose {p['growth_card_pct']}% + {money(p['card_fixed'])} has no ceiling. The clients being migrated"])
        add(["are the commercial ones, i.e. the largest invoices, i.e. above the cap."])
    add(["Identical on BOTH plans, and Homeworks adds NO markup to ACH (owner-confirmed)"])
    add([f"-- unlike card, where it adds 1% below Enterprise (H-063) to make the {p['growth_card_pct']}%."])
    add(["So an upgrade removes a card markup that has no ACH equivalent: ACH dollars"])
    add(["save exactly $0.00. Follow-Up #32 migrates commercial clients from card to"])
    add(["portal ACH -- shrinking the very base trigger 1 depends on."])
    add([])

    # --- Blocked inputs ----------------------------------------------------
    add(["BLOCKED INPUTS -- deliberately not modelled"])
    blocked_any = False
    for aid in ("homeworks_enterprise_sms_overage_rate", "homeworks_ach_rate_pct"):
        if is_blocked(assumptions, aid):
            row = [r for r in assumptions if r["assumption_id"] == aid][0]
            add([aid, row["trigger_condition"]])
            blocked_any = True
    if not blocked_any:
        add(["None."])
    return rows


def main():
    rows = build_report_rows(load_assumptions())
    for row in rows:
        print("  ".join(str(c) for c in row))


if __name__ == "__main__":
    main()
