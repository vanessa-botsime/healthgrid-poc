"""
IMISI HealthGrid PoC - synthetic seed data.

Creates healthgrid.db (SQLite) from schema.sql and fills it with
SYNTHETIC payers, plans, providers, members and sample authorisation
requests. Nothing here describes a real person or organisation.

Usage:
    python seed.py                 # creates ./healthgrid.db
    python seed.py path/to/my.db   # custom location

The output is deterministic (fixed random seed), so every teammate
gets exactly the same IDs for the demo.
"""

import json
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "healthgrid.db"
TODAY = date(2026, 10, 28)  # demo day, keeps dates stable
rng = random.Random(2026)

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
PAYERS = [
    ("PAY-001", "Harmony Care HMO", "HMO"),
    ("PAY-002", "Sunrise Health Insurance", "INSURER"),
    ("PAY-003", "Unity Micro-Health Cooperative", "HMO"),
]

# plan_id, payer_id, name, tier, annual_limit, auth_threshold
PLANS = [
    ("PLN-001", "PAY-001", "Harmony Essential", "basic", 500_000, 50_000),
    ("PLN-002", "PAY-001", "Harmony Family Plus", "standard", 1_500_000, 100_000),
    ("PLN-003", "PAY-002", "Sunrise Corporate Gold", "premium", 5_000_000, 250_000),
    ("PLN-004", "PAY-002", "Sunrise Individual", "basic", 600_000, 50_000),
    ("PLN-005", "PAY-003", "Unity Micro Cover", "micro", 150_000, 20_000),
    ("PLN-006", "PAY-003", "Unity Micro Family", "micro", 300_000, 30_000),
]

SERVICE_CATEGORIES = [
    "outpatient_consultation",
    "laboratory",
    "imaging",
    "maternity",
    "surgery",
    "specialist_consultation",
    "inpatient_admission",
    "physiotherapy",
    "dental",
]

# Coverage rules per tier: (covered, requires_auth)
TIER_RULES = {
    "micro": {
        "outpatient_consultation": (1, 0), "laboratory": (1, 0), "imaging": (0, 0),
        "maternity": (1, 1), "surgery": (0, 0), "specialist_consultation": (0, 0),
        "inpatient_admission": (1, 1), "physiotherapy": (0, 0), "dental": (0, 0),
    },
    "basic": {
        "outpatient_consultation": (1, 0), "laboratory": (1, 0), "imaging": (1, 1),
        "maternity": (1, 1), "surgery": (1, 1), "specialist_consultation": (1, 1),
        "inpatient_admission": (1, 1), "physiotherapy": (0, 0), "dental": (0, 0),
    },
    "standard": {
        "outpatient_consultation": (1, 0), "laboratory": (1, 0), "imaging": (1, 1),
        "maternity": (1, 1), "surgery": (1, 1), "specialist_consultation": (1, 0),
        "inpatient_admission": (1, 1), "physiotherapy": (1, 1), "dental": (1, 0),
    },
    "premium": {
        "outpatient_consultation": (1, 0), "laboratory": (1, 0), "imaging": (1, 0),
        "maternity": (1, 1), "surgery": (1, 1), "specialist_consultation": (1, 0),
        "inpatient_admission": (1, 1), "physiotherapy": (1, 0), "dental": (1, 0),
    },
}

PROVIDERS = [
    ("PRV-001", "Lagoon View General Hospital", "hospital", "Lagos", "Lagos"),
    ("PRV-002", "Ikeja Family Clinic", "clinic", "Ikeja", "Lagos"),
    ("PRV-003", "Central Diagnostics Lab", "laboratory", "Abuja", "FCT"),
    ("PRV-004", "Garki Specialist Centre", "hospital", "Abuja", "FCT"),
    ("PRV-005", "Ibadan Mother & Child Clinic", "clinic", "Ibadan", "Oyo"),
    ("PRV-006", "Port Harcourt Medical Centre", "hospital", "Port Harcourt", "Rivers"),
    ("PRV-007", "Kano Community Health Post", "primary_care", "Kano", "Kano"),
    ("PRV-008", "Enugu Imaging & Scan", "imaging_centre", "Enugu", "Enugu"),
]

FIRST_F = ["Adaeze", "Funmilayo", "Ngozi", "Aisha", "Temitope", "Chiamaka", "Halima",
           "Bisola", "Ifeoma", "Zainab", "Kemi", "Amarachi", "Fatima", "Yetunde"]
FIRST_M = ["Chinedu", "Oluwaseun", "Ibrahim", "Emeka", "Tunde", "Musa", "Obinna",
           "Babatunde", "Usman", "Kelechi", "Segun", "Abdullahi", "Ikenna", "Femi"]
LAST = ["Okafor", "Adeyemi", "Bello", "Eze", "Ogunleye", "Abubakar", "Nwosu",
        "Balogun", "Okonkwo", "Danjuma", "Afolabi", "Chukwu", "Lawal", "Oyelaran",
        "Ibekwe", "Suleiman", "Adebayo", "Onyeka"]

SERVICE_DESCRIPTIONS = {
    "imaging": ["Abdominal ultrasound", "Chest X-ray", "Pelvic ultrasound", "CT scan, head"],
    "maternity": ["Antenatal package, 3rd trimester", "Normal delivery", "Caesarean section"],
    "surgery": ["Appendectomy", "Hernia repair", "Laparoscopic cholecystectomy"],
    "specialist_consultation": ["Cardiology review", "Orthopaedic review", "ENT review"],
    "inpatient_admission": ["Admission for malaria with complications", "Admission for pneumonia",
                            "Admission for observation, 3 days"],
    "physiotherapy": ["Post-surgery physiotherapy, 6 sessions", "Back pain physiotherapy"],
    "laboratory": ["Full blood count + malaria test", "Lipid profile", "HbA1c test"],
    "outpatient_consultation": ["General consultation"],
    "dental": ["Tooth extraction", "Scaling and polishing"],
}

COST_RANGE = {
    "imaging": (25_000, 180_000),
    "maternity": (80_000, 450_000),
    "surgery": (250_000, 1_200_000),
    "specialist_consultation": (15_000, 60_000),
    "inpatient_admission": (90_000, 400_000),
    "physiotherapy": (30_000, 120_000),
    "laboratory": (8_000, 40_000),
    "outpatient_consultation": (5_000, 20_000),
    "dental": (10_000, 60_000),
}


def iso(d):
    return d.isoformat()


def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# --------------------------------------------------------------------------
# Members: a fixed set of "demo scenario" members first, then random ones
# --------------------------------------------------------------------------
def build_members():
    members = []

    # Hand-picked members so the demo script always has the same stories.
    scenarios = [
        # id, first, last, dob, sex, plan, status, from, to, used, note
        ("SYN-100001", "Adaeze", "Okafor", "1991-04-12", "F", "PLN-002", "active",
         "2026-01-01", "2026-12-31", 120_000, "Happy path: active, standard plan"),
        ("SYN-100002", "Chinedu", "Eze", "1985-09-30", "M", "PLN-004", "expired",
         "2025-01-01", "2025-12-31", 0, "Expired policy -> ineligible"),
        ("SYN-100003", "Aisha", "Bello", "1998-02-05", "F", "PLN-005", "active",
         "2026-03-01", "2027-02-28", 30_000, "Micro plan: imaging NOT covered"),
        ("SYN-100004", "Tunde", "Adeyemi", "1979-11-18", "M", "PLN-001", "suspended",
         "2026-01-01", "2026-12-31", 0, "Suspended (premium unpaid)"),
        ("SYN-100005", "Funmilayo", "Balogun", "1994-07-22", "F", "PLN-006", "active",
         "2026-02-01", "2027-01-31", 285_000, "Micro family: limit almost reached"),
        ("SYN-100006", "Ibrahim", "Abubakar", "1988-05-09", "M", "PLN-003", "active",
         "2026-01-01", "2026-12-31", 400_000, "Premium corporate member"),
        ("SYN-100007", "Ngozi", "Nwosu", "2001-12-01", "F", "PLN-002", "pending",
         "2026-11-01", "2027-10-31", 0, "Pending: cover starts next month"),
    ]
    for s in scenarios:
        members.append({
            "member_id": s[0], "first_name": s[1], "last_name": s[2],
            "date_of_birth": s[3], "sex": s[4], "plan_id": s[5], "status": s[6],
            "effective_from": s[7], "effective_to": s[8], "used_amount_ngn": s[9],
        })

    # Random members SYN-100008 .. SYN-100040
    plan_ids = [p[0] for p in PLANS]
    for i in range(8, 41):
        sex = rng.choice("FM")
        first = rng.choice(FIRST_F if sex == "F" else FIRST_M)
        last = rng.choice(LAST)
        dob = date(rng.randint(1958, 2005), rng.randint(1, 12), rng.randint(1, 28))
        plan_id = rng.choice(plan_ids)
        status = rng.choices(["active", "expired", "suspended"], weights=[85, 10, 5])[0]
        if status == "expired":
            start = date(2025, rng.randint(1, 9), 1)
        else:
            start = date(2026, rng.randint(1, 9), 1)
        end = start.replace(year=start.year + 1) - timedelta(days=1)
        limit = next(p[4] for p in PLANS if p[0] == plan_id)
        used = rng.randint(0, int(limit * 0.6)) // 1000 * 1000
        members.append({
            "member_id": f"SYN-{100000 + i}", "first_name": first, "last_name": last,
            "date_of_birth": iso(dob), "sex": sex, "plan_id": plan_id, "status": status,
            "effective_from": iso(start), "effective_to": iso(end), "used_amount_ngn": used,
        })
    for m in members:
        m["payer_member_ref"] = "HMO-" + m["member_id"][4:] + "-" + m["plan_id"][-1]
        m["phone_masked"] = "+234 80* *** " + f"{rng.randint(0, 9999):04d}"
    return members


# --------------------------------------------------------------------------
# Sample authorisation requests with a realistic event history
# --------------------------------------------------------------------------
STATUS_MIX = (
    ["approved"] * 9 + ["declined"] * 3 + ["under_review"] * 5 +
    ["submitted"] * 4 + ["more_info_needed"] * 3 + ["cancelled"] * 1
)


def build_requests(members):
    auth_categories = ["imaging", "maternity", "surgery", "specialist_consultation",
                       "inpatient_admission", "physiotherapy"]
    eligible_members = [m for m in members if m["status"] == "active"]
    requests, events = [], []

    for n, final_status in enumerate(STATUS_MIX, start=1):
        m = rng.choice(eligible_members)
        cat = rng.choice(auth_categories)
        prov = rng.choice(PROVIDERS)[0]
        lo, hi = COST_RANGE[cat]
        cost = rng.randint(lo, hi) // 1000 * 1000
        urgency = rng.choices(["routine", "urgent"], weights=[75, 25])[0]

        # created between 1 and 14 days before demo day, during working hours
        created = datetime.combine(TODAY - timedelta(days=rng.randint(1, 14)),
                                   datetime.min.time()) + timedelta(hours=rng.randint(8, 16),
                                                                   minutes=rng.randint(0, 59))
        missing = []
        if final_status == "more_info_needed":
            missing = rng.choice([["referral_letter"], ["clinical_notes"],
                                  ["referral_letter", "estimated_cost_ngn"]])

        rid = f"AUTH-{n:04d}"
        t = created
        history = [("provider_user", None, "submitted", None, t)]
        if final_status != "submitted":
            t = t + timedelta(hours=rng.randint(1, 20))
            if final_status == "cancelled":
                history.append(("provider_user", "submitted", "cancelled",
                                "Patient transferred to another facility", t))
            else:
                history.append(("insurer_reviewer", "submitted", "under_review", None, t))
                if final_status in ("approved", "declined", "more_info_needed"):
                    t = t + timedelta(hours=rng.randint(2, 48) if urgency == "routine"
                                      else rng.randint(1, 6))
                    reason = {
                        "approved": "Meets plan criteria",
                        "declined": rng.choice(["Service excluded under plan",
                                                "Annual limit exceeded",
                                                "Pre-existing condition waiting period"]),
                        "more_info_needed": "Missing: " + ", ".join(missing),
                    }[final_status]
                    history.append(("insurer_reviewer", "under_review", final_status, reason, t))

        requests.append({
            "request_id": rid, "member_id": m["member_id"], "provider_id": prov,
            "service_category": cat,
            "service_description": rng.choice(SERVICE_DESCRIPTIONS[cat]),
            "requested_date": iso(TODAY + timedelta(days=rng.randint(1, 10))),
            "urgency": urgency, "estimated_cost_ngn": cost,
            "reason": "Clinically indicated per attending physician (synthetic)",
            "status": final_status,
            "missing_fields": json.dumps(missing) if missing else None,
            "created_at": ts(created), "updated_at": ts(t),
        })
        for actor, frm, to, reason, at in history:
            events.append((rid, actor, frm, to, reason, ts(at)))
    return requests, events


# --------------------------------------------------------------------------
def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript((HERE / "schema.sql").read_text())

    con.executemany("INSERT INTO payers (payer_id, name, type) VALUES (?, ?, ?)", PAYERS)
    con.executemany("INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?)", PLANS)
    for plan_id, _, _, tier, _, _ in PLANS:
        for cat, (covered, auth) in TIER_RULES[tier].items():
            con.execute("INSERT INTO plan_services VALUES (?, ?, ?, ?)",
                        (plan_id, cat, covered, auth))
    con.executemany(
        "INSERT INTO providers (provider_id, name, facility_type, city, state) VALUES (?, ?, ?, ?, ?)",
        PROVIDERS)

    members = build_members()
    con.executemany(
        """INSERT INTO members (member_id, payer_member_ref, first_name, last_name, date_of_birth,
           sex, phone_masked, plan_id, status, effective_from, effective_to, used_amount_ngn)
           VALUES (:member_id, :payer_member_ref, :first_name, :last_name, :date_of_birth, :sex,
           :phone_masked, :plan_id, :status, :effective_from, :effective_to, :used_amount_ngn)""",
        members)

    requests, events = build_requests(members)
    con.executemany(
        """INSERT INTO authorisation_requests VALUES (:request_id, :member_id, :provider_id,
           :service_category, :service_description, :requested_date, :urgency,
           :estimated_cost_ngn, :reason, :status, :missing_fields, :created_at, :updated_at)""",
        requests)
    con.executemany(
        """INSERT INTO workflow_events (request_id, actor, from_state, to_state, reason, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""", events)
    con.commit()

    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ["payers", "plans", "plan_services", "providers", "members",
                        "authorisation_requests", "workflow_events"]}
    con.close()
    print(f"Seeded {DB_PATH}")
    for t, c in counts.items():
        print(f"  {t:<24}{c}")


if __name__ == "__main__":
    main()
