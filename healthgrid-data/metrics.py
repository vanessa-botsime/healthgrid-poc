"""
IMISI HealthGrid PoC - operations metrics for the dashboard (Flask Blueprint).

Endpoint
    GET /api/metrics/operations                  all data
    GET /api/metrics/operations?from=2026-10-20&to=2026-10-28   filter on request creation date

Computed live from the database, so the numbers move during the demo as
Vanessa's workflow creates requests and status-change events.
All values are computed on SYNTHETIC demo data (PRD FR-16): never present
them as real industry figures.
"""

from datetime import datetime
from statistics import median

from flask import Blueprint, jsonify, request

from eligibility import get_db

bp = Blueprint("metrics", __name__)

ALL_STATUSES = ["draft", "submitted", "under_review", "more_info_needed",
                "approved", "declined", "cancelled", "closed"]
DECISIONS = ("approved", "declined")


def _parse(ts):
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")


def _percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


@bp.get("/api/metrics/operations")
def operations_metrics():
    db = get_db()
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    where, params = [], []
    if date_from:
        where.append("substr(created_at, 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        where.append("substr(created_at, 1, 10) <= ?")
        params.append(date_to)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        "SELECT request_id, status, urgency, service_category, missing_fields, created_at "
        "FROM authorisation_requests" + clause, params).fetchall()
    ids = {r["request_id"] for r in rows}

    by_status = {s: 0 for s in ALL_STATUSES}
    by_category, urgent_pending, incomplete = {}, 0, 0
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_category[r["service_category"]] = by_category.get(r["service_category"], 0) + 1
        if r["status"] in ("submitted", "under_review") and r["urgency"] == "urgent":
            urgent_pending += 1
        if r["missing_fields"] and r["missing_fields"] not in ("[]", "null"):
            incomplete += 1

    # Turnaround = first "submitted" event -> first approved/declined event (hours)
    events = db.execute(
        "SELECT request_id, to_state, created_at FROM workflow_events ORDER BY created_at").fetchall()
    first_submit, first_decision = {}, {}
    for e in events:
        rid = e["request_id"]
        if rid not in ids:
            continue
        if e["to_state"] == "submitted" and rid not in first_submit:
            first_submit[rid] = _parse(e["created_at"])
        if e["to_state"] in DECISIONS and rid not in first_decision:
            first_decision[rid] = _parse(e["created_at"])
    turnaround_h = [round((first_decision[r] - first_submit[r]).total_seconds() / 3600, 1)
                    for r in first_decision if r in first_submit]

    decided = by_status["approved"] + by_status["declined"]

    # Eligibility checks logged by the mock adapter
    elig = {r["result"]: r["n"] for r in db.execute(
        "SELECT result, COUNT(*) AS n FROM eligibility_checks GROUP BY result")}

    pending_queue = [dict(r) for r in db.execute(
        "SELECT request_id, member_id, provider_id, service_category, urgency, status, created_at "
        "FROM authorisation_requests WHERE status IN ('submitted', 'under_review', 'more_info_needed')"
        + (" AND " + " AND ".join(where) if where else "")
        + " ORDER BY CASE urgency WHEN 'urgent' THEN 0 ELSE 1 END, created_at LIMIT 10", params)]

    return jsonify({
        "simulated": True,
        "note": "Computed on synthetic demo data. Not real industry figures.",
        "filters": {"from": date_from, "to": date_to},
        "requests": {
            "total": len(rows),
            "by_status": by_status,
            "by_service_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
            "pending_queue_count": by_status["submitted"] + by_status["under_review"],
            "awaiting_more_info": by_status["more_info_needed"],
            "urgent_pending": urgent_pending,
            "incomplete_requests": incomplete,
            "decided": decided,
            "approval_rate_pct": round(100 * by_status["approved"] / decided, 1) if decided else None,
        },
        "turnaround_hours": {
            "sample_size": len(turnaround_h),
            "median": median(turnaround_h) if turnaround_h else None,
            "p90": round(_percentile(turnaround_h, 0.9), 1) if turnaround_h else None,
        },
        "eligibility_checks": {
            "total": sum(elig.values()),
            "by_result": {k: elig.get(k, 0) for k in ("eligible", "ineligible", "unknown", "unavailable")},
        },
        "oldest_pending": pending_queue,
    })
