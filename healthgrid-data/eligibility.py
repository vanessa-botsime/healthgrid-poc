"""
IMISI HealthGrid PoC - member lookup + MOCK eligibility adapter (Flask Blueprint).

Endpoints
    GET  /api/members/<member_id>        member summary (minimum necessary fields)
    GET  /api/members?q=<text>           search by member ID or last name (max 10)
    GET  /api/reference                  providers + service categories (for dropdowns)
    POST /api/eligibility-checks         run a simulated eligibility check

Everything returned is SYNTHETIC and labelled "simulated": true.
Eligibility is NOT a guarantee of payment or authorisation (PRD section 9).

Demo scenarios (member IDs created by seed.py)
    SYN-100001  active, standard plan               -> eligible
    SYN-100002  policy expired                      -> ineligible
    SYN-100003  micro plan, imaging not covered     -> ineligible for "imaging"
    SYN-100004  suspended                           -> ineligible
    SYN-100005  limit almost reached                -> eligible, low remaining limit
    SYN-100007  cover starts next month             -> ineligible (pending)
    SYN-999999  simulates the payer system being down -> 503 "unavailable"
    anything else unknown                           -> 404 "unknown"
"""

import sqlite3
import uuid
from datetime import date, datetime

from flask import Blueprint, current_app, g, jsonify, request

bp = Blueprint("eligibility", __name__)

ADAPTER_NAME = "mock-payer-adapter v0.1 (simulated)"
OUTAGE_MEMBER_ID = "SYN-999999"
DISCLAIMER = "Simulated response on synthetic data. Eligibility is not a guarantee of payment or authorisation."


# --------------------------------------------------------------------------
# DB helper (shared with metrics.py)
# --------------------------------------------------------------------------
def get_db():
    if "healthgrid_db" not in g:
        con = sqlite3.connect(current_app.config["HEALTHGRID_DB"])
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        g.healthgrid_db = con
    return g.healthgrid_db


@bp.teardown_app_request
def close_db(_exc):
    con = g.pop("healthgrid_db", None)
    if con is not None:
        con.close()


def today():
    # Lets the demo pin "today" (e.g. HEALTHGRID_TODAY = "2026-10-28"), else real date.
    pinned = current_app.config.get("HEALTHGRID_TODAY")
    return date.fromisoformat(pinned) if pinned else date.today()


def now_ts():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def member_summary(row):
    """Minimum necessary fields: no full DOB, masked phone (PRD section 14)."""
    return {
        "member_id": row["member_id"],
        "payer_member_ref": row["payer_member_ref"],
        "name": f'{row["first_name"]} {row["last_name"]}',
        "year_of_birth": int(row["date_of_birth"][:4]),
        "sex": row["sex"],
        "phone_masked": row["phone_masked"],
        "status": row["status"],
        "plan": {
            "plan_id": row["plan_id"],
            "name": row["plan_name"],
            "tier": row["tier"],
            "payer": row["payer_name"],
        },
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
    }


MEMBER_SQL = """
    SELECT m.*, p.name AS plan_name, p.tier, p.annual_limit_ngn, p.requires_auth_above_ngn,
           y.name AS payer_name
    FROM members m
    JOIN plans p  ON p.plan_id = m.plan_id
    JOIN payers y ON y.payer_id = p.payer_id
"""


# --------------------------------------------------------------------------
# Member lookup
# --------------------------------------------------------------------------
@bp.get("/api/members/<member_id>")
def get_member(member_id):
    row = get_db().execute(MEMBER_SQL + " WHERE m.member_id = ?",
                           (member_id.strip().upper(),)).fetchone()
    if row is None:
        return jsonify({"error": "member_not_found",
                        "message": f"No member found with ID {member_id}.",
                        "simulated": True}), 404
    return jsonify({"member": member_summary(row), "simulated": True})


@bp.get("/api/members")
def search_members():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"error": "query_too_short",
                        "message": "Type at least 2 characters (member ID or last name)."}), 400
    rows = get_db().execute(
        MEMBER_SQL + " WHERE m.member_id LIKE ? OR m.last_name LIKE ? ORDER BY m.member_id LIMIT 10",
        (q.upper() + "%", q + "%")).fetchall()
    return jsonify({"results": [member_summary(r) for r in rows],
                    "count": len(rows), "simulated": True})


@bp.get("/api/reference")
def reference():
    db = get_db()
    providers = [dict(r) for r in db.execute(
        "SELECT provider_id, name, facility_type, city, state FROM providers ORDER BY provider_id")]
    categories = [r[0] for r in db.execute(
        "SELECT DISTINCT service_category FROM plan_services ORDER BY service_category")]
    return jsonify({"providers": providers, "service_categories": categories, "simulated": True})


# --------------------------------------------------------------------------
# Eligibility check (mock payer adapter)
# --------------------------------------------------------------------------
def log_check(db, member_id, provider_id, category, result, reason):
    check_id = "ELG-" + uuid.uuid4().hex[:8].upper()
    checked_at = now_ts()
    db.execute(
        """INSERT INTO eligibility_checks
           (check_id, member_id, provider_id, service_category, result, reason, source, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (check_id, member_id, provider_id, category, result, reason, ADAPTER_NAME, checked_at))
    db.commit()
    return check_id, checked_at


@bp.post("/api/eligibility-checks")
def eligibility_check():
    body = request.get_json(silent=True) or {}
    member_id = (body.get("member_id") or "").strip().upper()
    provider_id = (body.get("provider_id") or "").strip().upper() or None
    category = (body.get("service_category") or "").strip().lower() or None

    if not member_id:
        return jsonify({"error": "validation_error",
                        "missing_fields": ["member_id"],
                        "message": "member_id is required."}), 400

    db = get_db()

    if provider_id and db.execute("SELECT 1 FROM providers WHERE provider_id = ?",
                                  (provider_id,)).fetchone() is None:
        return jsonify({"error": "validation_error",
                        "message": f"Unknown provider_id {provider_id}."}), 400

    # Scenario: payer system unreachable
    if member_id == OUTAGE_MEMBER_ID:
        check_id, at = log_check(db, member_id, provider_id, category, "unavailable",
                                 "Payer system did not respond (simulated timeout)")
        return jsonify({
            "check_id": check_id, "result": "unavailable",
            "reason": "The payer system did not respond. Please retry in a few minutes.",
            "retryable": True, "source": ADAPTER_NAME, "checked_at": at,
            "simulated": True, "disclaimer": DISCLAIMER,
        }), 503

    row = db.execute(MEMBER_SQL + " WHERE m.member_id = ?", (member_id,)).fetchone()

    # Scenario: unknown member
    if row is None:
        check_id, at = log_check(db, None, provider_id, category, "unknown",
                                 f"Member {member_id} not found")
        return jsonify({
            "check_id": check_id, "result": "unknown",
            "reason": "No member found with this ID. Check the ID on the member's card.",
            "source": ADAPTER_NAME, "checked_at": at,
            "simulated": True, "disclaimer": DISCLAIMER,
        }), 404

    d = today()
    start, end = date.fromisoformat(row["effective_from"]), date.fromisoformat(row["effective_to"])
    remaining = max(row["annual_limit_ngn"] - row["used_amount_ngn"], 0)

    result, reason = "eligible", "Member is active and covered on this date."
    requires_auth = None
    service_covered = None

    if row["status"] == "suspended":
        result, reason = "ineligible", "Policy is suspended (e.g. unpaid premium)."
    elif row["status"] == "pending" or d < start:
        result, reason = "ineligible", f"Cover has not started yet (starts {row['effective_from']})."
    elif row["status"] == "expired" or d > end:
        result, reason = "ineligible", f"Policy expired on {row['effective_to']}."
    elif remaining <= 0:
        result, reason = "ineligible", "Annual benefit limit has been reached."

    if category:
        svc = db.execute(
            "SELECT covered, requires_auth FROM plan_services WHERE plan_id = ? AND service_category = ?",
            (row["plan_id"], category)).fetchone()
        if svc is None:
            return jsonify({"error": "validation_error",
                            "message": f"Unknown service_category '{category}'."}), 400
        service_covered = bool(svc["covered"])
        requires_auth = bool(svc["requires_auth"])
        if result == "eligible" and not service_covered:
            result = "ineligible"
            reason = f"'{category}' is not covered under the {row['plan_name']} plan."

    limitations = []
    if result == "eligible" and remaining < 0.1 * row["annual_limit_ngn"]:
        limitations.append(f"Low remaining annual limit: NGN {remaining:,}.")
    if requires_auth:
        limitations.append("Prior care authorisation is required for this service.")

    check_id, at = log_check(db, member_id, provider_id, category, result, reason)

    return jsonify({
        "check_id": check_id,
        "result": result,                       # eligible | ineligible | unknown | unavailable
        "reason": reason,
        "member": member_summary(row),
        "service_category": category,
        "service_covered": service_covered,
        "requires_authorisation": requires_auth,
        "auth_threshold_ngn": row["requires_auth_above_ngn"],
        "annual_limit_ngn": row["annual_limit_ngn"],
        "remaining_limit_ngn": remaining,
        "limitations": limitations,
        "next_step": ("create_authorisation_request" if result == "eligible" and requires_auth
                      else "proceed_with_care" if result == "eligible" else "contact_payer"),
        "source": ADAPTER_NAME,
        "checked_at": at,
        "simulated": True,
        "disclaimer": DISCLAIMER,
    })
