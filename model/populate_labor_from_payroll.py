#!/usr/bin/env python3
"""Rebuild the labor ledger from real Gusto payroll data (Sequencing Step 5).

Usage:
    python model/populate_labor_from_payroll.py

Replaces the synthetic 66-row ESTIMATE ledger-labor.csv entirely with real,
per-employee, per-pay-period ACTUAL rows sourced from the two payroll journal
exports in reference/. Also populates the employer-payroll-tax-burden
overhead category (one aggregated row per pay period) in
model/data/ledger-overhead.csv, and generates model/data/employee-role-map.csv
(time-varying: employee,role,effective_date -- one row per role-period, not
one static row per person, because Xavier's Gusto title changed from "Crew
Lead" to "Crew Member" coinciding with his pay-rate drop).

Design, confirmed this session:
  - Column mapping is by name (dict(zip(header, row))), never fixed position
    -- the two payroll files' schemas differ (File 1 has a Commission column
    File 2 lacks; the employer-tax columns appear in a different order).
  - Two "Reversal Payroll"-marked payday-blocks are skipped entirely (their
    reversal rows net exactly to the original, and Gusto's own convenience
    "Payroll Totals" row for a reversed payday is NOT reliable -- it reflects
    only the reversal batch, not zero); the later, clean resubmission payday
    for the same period is kept instead. A third, unmarked reversal
    (03/24-04/06/2025, $508.84) needs no special handling: that period's own
    "Payroll Totals" already shows the correct final resubmitted amount.
  - The ledger mirrors the source exactly: one row per (employee, period)
    pair Gusto's own export actually lists, including genuine $0/zero-hour
    rows for still-active-but-idle employees, and no row at all for periods
    before hire or after dismissal (confirmed: dismissed employees simply
    stop appearing in the source, they are never listed with a $0 row).
  - `amount` is the recorded Gross Earnings/Regular Amount value directly,
    never quantity*unit_rate re-derived (a real, small rounding gap exists:
    e.g. Xavier's 2026-04-20 period shows 11.67 hrs * $25.00 = $291.75
    computed, but Gusto's own recorded amount is $291.67).
  - Employer-side payroll tax (Employee Taxes + Employer Taxes, the
    "Employer Cost" component beyond wages) is booked as overhead, not
    labor, one aggregated row per pay period -- keeps ledger-labor.csv's
    `amount` meaning "wages paid to a person," not "fully-loaded cost."
"""
import csv
import glob
import sys
from datetime import datetime

sys.path.insert(0, "model")
import match_payments as mp  # noqa: E402

PAYROLL_GLOB = "reference/tupelo-landscaping-llc-payroll-summary-*.csv"
ROLE_MAP_PATH = "model/data/employee-role-map.csv"
LEDGER_LABOR_PATH = "model/data/ledger-labor.csv"
LEDGER_OVERHEAD_PATH = "model/data/ledger-overhead.csv"
LEDGER_FIELDS = [
    "date", "type", "event", "category", "subcategory", "customer",
    "quantity", "unit_rate", "amount", "status", "source",
]

# Gusto job titles, owner-confirmed 2026-07-10. Xavier's changed; nobody
# else has a confirmed prior title different from their current one --
# Katherine's rate changed ($20 -> $30) but no prior *title* was stated by
# the owner, so she gets a single constant role, not a time-varying one
# (flagged explicitly in the script output, not assumed silently).
#
# `status` (added 2026-07-14, HISTORY.md H-072, closing the gap H-071 flagged):
# one of "active" / "dismissed" / "resigned" / "unknown" -- an explicit,
# owner-confirmed employment-status flag, not inferred from payroll absence.
# "unknown" is a real, distinct value, not a placeholder to avoid filling in --
# it means a long payroll gap exists but the owner has NOT confirmed dismissal:
# do NOT guess "dismissed" for a long gap alone, the same mistake H-071
# corrected for Xavier's "departure" wording. Only set "dismissed"/"resigned"
# on explicit owner confirmation (e.g. Littlejohn, Daschke, H-071; Archuletta,
# Cook, H-080). For Xavier's two role-period rows, status describes his
# current employment (active), not a per-period value -- there is no
# indication either row's period should carry a different status.
#
# Roster settled 2026-08-01 (HISTORY.md H-080, closing CONTEXT.md Follow-Up #1):
# Archuletta and Cook confirmed dismissed; no `unknown` row remains.
# ONE ROW CARRIES A PENDING CONFIRMATION -- Knauer, Nathaniel. His "active" is
# owner-OBSERVED (the owner directly witnessed him continuing to work), which is
# stronger evidence than the "unknown" it replaces but is NOT the same as
# independently verified: no Gusto export in reference/ yet covers a pay period
# showing his recent activity. Treated per CLAUDE.md rule 5 as an owner-stated
# fact awaiting its named prerequisite, the same way assumptions.csv's
# anais_hourly_rate_pending is (H-070). reference/PAYROLL-UPDATE.md step 7
# makes the next payroll refresh check and report this automatically -- do not
# rely on anyone remembering to re-check it by hand. There is deliberately no
# new CSV column for this: the schema stays employee/role/effective_date/
# status/alias, and the pending flag lives in the refresh procedure, which is
# where the check actually has to fire.
ROLE_MAP_ROWS = [
    {"employee": "Archuletta, Cyrus", "role": "Crew Member", "effective_date": "", "status": "dismissed"},
    {"employee": "Beauvais, Anais", "role": "Crew Member", "effective_date": "", "status": "active"},
    {"employee": "Beauvais, Cyrus", "role": "CEO", "effective_date": "", "status": "active"},
    {"employee": "Beauvais, Xavier", "role": "Crew Lead", "effective_date": "", "status": "active"},
    {"employee": "Beauvais, Xavier", "role": "Crew Member", "effective_date": "2026-06-15", "status": "active"},
    {"employee": "Bunek, Parker", "role": "Crew Member", "effective_date": "", "status": "active"},
    {"employee": "Cook, Jason", "role": "Crew Member", "effective_date": "", "status": "dismissed"},
    {"employee": "Daschke, August", "role": "Crew Member", "effective_date": "", "status": "dismissed"},
    {"employee": "Driscoll, Katherine", "role": "Landscape Consultant", "effective_date": "", "status": "active"},
    {"employee": "Gaspar, Caleb", "role": "Crew Member", "effective_date": "", "status": "active"},
    {"employee": "Gorman, Konjinet", "role": "Crew Lead", "effective_date": "", "status": "active"},
    {"employee": "Kiflu, Rimon", "role": "Crew Member", "effective_date": "", "status": "active"},
    # active = owner-OBSERVED, pending payroll confirmation -- see the note above.
    {"employee": "Knauer, Nathaniel", "role": "Crew Member", "effective_date": "", "status": "active"},
    {"employee": "Littlejohn, James", "role": "Crew Member", "effective_date": "", "status": "dismissed"},
    {"employee": "Lordos, Zavier", "role": "Crew Member", "effective_date": "", "status": "active"},
    {"employee": "Moore, Max", "role": "Crew Member", "effective_date": "", "status": "active"},
]
ROLE_MAP_ALIASES = {
    "Gorman, Konjinet": "Konji",
    "Driscoll, Katherine": "Katie",
    "Knauer, Nathaniel": "Nate",
}


def parse_payroll_file(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw_rows = list(csv.reader(f))
    idx = next(i for i, r in enumerate(raw_rows) if r and r[0] == "Employee Earnings")
    detail_rows = raw_rows[idx + 1:]

    periods = []
    cur = None

    def flush():
        if cur is not None and (cur["period"] or cur["offcycle"] or cur["tax_reconciliation"]):
            periods.append(cur)

    cur = {"period": None, "payday": None, "offcycle": False, "tax_reconciliation": False,
           "header": None, "employees": [], "totals": None, "reversal": False}
    i = 0
    while i < len(detail_rows):
        row = detail_rows[i]
        if not row or (len(row) == 1 and row[0] == ""):
            i += 1
            continue
        if row[0] == "Payroll period":
            flush()
            cur = {"period": row[1].strip(), "payday": None, "offcycle": False, "tax_reconciliation": False,
                   "header": None, "employees": [], "totals": None, "reversal": False}
            i += 1
            cur["payday"] = detail_rows[i][1].strip(); i += 1
            cur["header"] = detail_rows[i]; i += 1
            continue
        if row[0] == "Off Cycle Payroll":
            flush()
            cur = {"period": None, "payday": None, "offcycle": True, "tax_reconciliation": False,
                   "header": None, "employees": [], "totals": None, "reversal": False}
            i += 1
            cur["payday"] = detail_rows[i][1].strip(); i += 1
            cur["header"] = detail_rows[i]; i += 1
            continue
        if row[0] == "Tax Reconciliation Payroll":
            # Employer-tax-only correction (e.g. a VA Unemployment rate true-up):
            # zero wages/hours (blank, not "0.00" -- structurally distinct from an
            # idle work period), so no labor row is emitted for it, only an
            # employer-payroll-tax-burden overhead adjustment. See main().
            flush()
            cur = {"period": None, "payday": None, "offcycle": False, "tax_reconciliation": True,
                   "header": None, "employees": [], "totals": None, "reversal": False}
            i += 1
            cur["payday"] = detail_rows[i][1].strip(); i += 1
            cur["header"] = detail_rows[i]; i += 1
            continue
        if row[0] == "Reversal Payroll":
            cur["reversal"] = True
            i += 1
            continue
        if row[0] == "Payroll Totals":
            cur["totals"] = row
            i += 1
            continue
        if cur["reversal"] and row[0] in ("Pay day", "Last Name"):
            i += 1
            continue
        cur["employees"].append(row)
        i += 1
    flush()
    return periods


def period_start_date(period_str):
    # "MM/DD/YYYY - MM/DD/YYYY" -> the first date, as YYYY-MM-DD
    start = period_str.split(" - ")[0].strip()
    return datetime.strptime(start, "%m/%d/%Y").strftime("%Y-%m-%d")


def load_role_map():
    # role-period rows, sorted per employee by effective_date ("" sorts first)
    by_employee = {}
    for r in ROLE_MAP_ROWS:
        by_employee.setdefault(r["employee"], []).append(r)
    for emp in by_employee:
        by_employee[emp].sort(key=lambda r: r["effective_date"])
    return by_employee


def role_for(role_map, employee, date_str):
    rows = role_map.get(employee)
    if not rows:
        return "UNLISTED -- needs owner ID"
    applicable = [r for r in rows if r["effective_date"] == "" or r["effective_date"] <= date_str]
    return applicable[-1]["role"] if applicable else rows[0]["role"]


def write_role_map():
    with open(ROLE_MAP_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["employee", "role", "effective_date", "status", "alias"])
        w.writeheader()
        for r in ROLE_MAP_ROWS:
            w.writerow({**r, "alias": ROLE_MAP_ALIASES.get(r["employee"], "")})


def write_ledger(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        for r in w_rows(rows):
            w.writerow(r)


def w_rows(rows):
    return rows


def read_ledger(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    files = sorted(glob.glob(PAYROLL_GLOB))
    print(f"[parse] {len(files)} payroll files")
    all_periods = []
    for fn in files:
        periods = parse_payroll_file(fn)
        for p in periods:
            p["source_file"] = fn
        all_periods.extend(periods)
    print(f"[parse] {len(all_periods)} payday-blocks total (incl. reversed ones)")

    reversed_blocks = [p for p in all_periods if p["reversal"]]
    kept_periods = [p for p in all_periods if not p["reversal"]]
    print(f"[filter] {len(reversed_blocks)} reversed payday-blocks skipped entirely "
          f"(their resubmission payday, kept separately, carries the real amount):")
    for p in reversed_blocks:
        print(f"    skipped: period={p['period']}  payday={p['payday']}  ({p['source_file']})")
    print(f"[filter] {len(kept_periods)} payday-blocks kept")

    role_map = load_role_map()
    write_role_map()
    print(f"[role-map] {len(ROLE_MAP_ROWS)} role-period rows written for "
          f"{len(role_map)} distinct employees ({ROLE_MAP_PATH})")

    labor_rows = []
    overhead_rows = []
    unlisted = set()
    for p in kept_periods:
        header = p["header"]
        date = period_start_date(p["period"]) if p["period"] else \
            datetime.strptime(p["payday"], "%m/%d/%Y").strftime("%Y-%m-%d")
        period_label = p["period"] or (
            "tax-reconciliation, payday " + p["payday"] if p["tax_reconciliation"]
            else "off-cycle, payday " + p["payday"])

        period_emp_tax = 0.0
        period_er_tax = 0.0
        any_employee_row = False
        for e in p["employees"]:
            if len(e) != len(header):
                continue
            d_row = dict(zip(header, e))
            name = f"{d_row['Last Name']}, {d_row['First Name']}"
            if d_row["Last Name"] in ("Payroll Totals", "Totals"):
                continue
            any_employee_row = True

            emp_tax = float(d_row.get("Employee Taxes", "") or 0)
            er_tax = float(d_row.get("Employer Taxes", "") or 0)
            period_emp_tax += emp_tax
            period_er_tax += er_tax

            if p["tax_reconciliation"]:
                # Employer-tax-only correction: no wage event, so no labor row.
                continue

            hours = d_row.get("Regular (Hours)", "") or "0"
            rate = d_row.get("Regular (Rate)", "") or "0"
            gross = d_row.get("Gross Earnings", "") or "0"

            role = role_for(role_map, name, date)
            if role.startswith("UNLISTED"):
                unlisted.add(name)

            labor_rows.append({
                "date": date, "type": "labor", "event": "", "category": name,
                "subcategory": role, "customer": "",
                "quantity": f"{float(hours):.2f}", "unit_rate": f"{float(rate):.2f}",
                "amount": f"{float(gross):.2f}", "status": "ACTUAL",
                "source": f"{p['source_file']}; period {period_label}, payday {p['payday']}",
            })

        if any_employee_row and (period_emp_tax != 0 or period_er_tax != 0):
            total_tax = period_emp_tax + period_er_tax
            overhead_rows.append({
                "date": date, "type": "overhead", "event": "", "category": "Gusto",
                "subcategory": "employer-payroll-tax-burden", "customer": "",
                "quantity": "1", "unit_rate": f"{total_tax:.2f}", "amount": f"{total_tax:.2f}",
                "status": "ACTUAL",
                "source": (f"{p['source_file']}; period {period_label}, payday {p['payday']}; "
                           f"Employee Taxes {period_emp_tax:.2f} + Employer Taxes {period_er_tax:.2f}"),
            })

    if unlisted:
        print(f"GATE FAILED: {len(unlisted)} employee(s) not found in role map: {sorted(unlisted)} -- "
              f"add them to ROLE_MAP_ROWS (owner-confirmed job title) before re-running. "
              f"Not writing the ledger with a placeholder role.")
        raise SystemExit(1)

    labor_rows.sort(key=lambda r: (r["date"], r["category"]))
    overhead_rows.sort(key=lambda r: r["date"])

    write_ledger(LEDGER_LABOR_PATH, labor_rows)
    print(f"[labor] {len(labor_rows)} rows written (full replacement of the old 66-row ESTIMATE ledger)")

    existing_overhead = read_ledger(LEDGER_OVERHEAD_PATH)
    kept_overhead = [r for r in existing_overhead
                     if not (r["category"] == "Gusto" and r["subcategory"] == "employer-payroll-tax-burden")]
    write_ledger(LEDGER_OVERHEAD_PATH, kept_overhead + overhead_rows)
    print(f"[overhead] {len(kept_overhead)} pre-existing rows kept + "
          f"{len(overhead_rows)} employer-payroll-tax-burden rows written")

    total_labor = sum(float(r["amount"]) for r in labor_rows)
    total_tax_overhead = sum(float(r["amount"]) for r in overhead_rows)
    print(f"[totals] labor (wages only): ${total_labor:,.2f} across {len(labor_rows)} rows")
    print(f"[totals] employer-payroll-tax-burden: ${total_tax_overhead:,.2f} across {len(overhead_rows)} periods")

    return kept_periods, all_periods


if __name__ == "__main__":
    main()
