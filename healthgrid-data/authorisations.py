"""
IMISI HealthGrid PoC - care authorisation workflow API.

Synthetic-data demonstration only.
This module provides request creation, retrieval, listing, status transitions,
and workflow event logging.
"""

import json
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from eligibility import get_db

bp = Blueprint("authorisations", name)

VALID_STATUSES = {
"draft",
"submitted",
"under_review",
"more_info_needed",
"approved",
"declined",
"cancelled",
"closed",
}

TRANSITIONS = {
"draft": {"submitted", "cancelled"},
"submitted": {"under_review", "cancelled"},
"under_review": {
"more_info_needed",
"approved",
"declined",
"cancelled",
},
"more_info_needed": {"submitted", "cancelled"},
"approved": {"closed"},
"declined": {"closed"},
"cancelled": set(),
"closed": set(),
}

def now_ts():
return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def json_body():
body = request.get_json(silent=True)
return body if isinstance(body, dict) else None

def record_event(db, request_id, from_state, to_state, actor, reason=None):
"""Record a workflow transition in the audit/event table."""
db.execute(
"""
INSERT INTO workflow_events
(event_id, request_id, from_state, to_state, actor, reason, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
(
"EVT-" + uuid.uuid4().hex[:10].upper(),
request_id,
from_state,
to_state,
actor,
reason,
now_ts(),
),
)

@bp.post("/api/authorisations")
def create_authorisation():
body = json_body()
if body is None:
return jsonify({
"error": "validation_error",
"message": "A JSON object is required.",
}), 400

required = [
    "member_id",
    "provider_id",
    "service_category",
    "description",
]
missing = [
    field for field in required
    if not isinstance(body.get(field), str) or not body[field].strip()
]
if missing:
    return jsonify({
        "error": "validation_error",
        "missing_fields": missing,
    }), 400

member_id = body["member_id"].strip().upper()
provider_id = body["provider_id"].strip().upper()
category = body["service_category"].strip().lower()
description = body["description"].strip()

urgency = body.get("urgency", "routine")
if urgency not in {"routine", "urgent"}:
    return jsonify({
        "error": "validation_error",
        "message": "urgency must be routine or urgent.",
    }), 400

cost = body.get("estimated_cost", 0)
if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
    return jsonify({
        "error": "validation_error",
        "message": "estimated_cost must be a non-negative number.",
    }), 400

db = get_db()

member = db.execute(
    "SELECT member_id FROM members WHERE member_id = ?",
    (member_id,),
).fetchone()
if member is None:
    return jsonify({
        "error": "validation_error",
        "message": "Unknown member_id.",
    }), 400

provider = db.execute(
    "SELECT provider_id FROM providers WHERE provider_id = ?",
    (provider_id,),
).fetchone()
if provider is None:
    return jsonify({
        "error": "validation_error",
        "message": "Unknown provider_id.",
    }), 400

request_id = "AUTH-" + uuid.uuid4().hex[:10].upper()
created_at = now_ts()

try:
    db.execute(
        """
        INSERT INTO authorisation_requests
            (request_id, member_id, provider_id, service_category,
             description, estimated_cost, urgency, status,
             missing_fields, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            member_id,
            provider_id,
            category,
            description,
            cost,
            urgency,
            "submitted",
            "[]",
            created_at,
            created_at,
        ),
    )

    record_event(
        db,
        request_id,
        None,
        "submitted",
        "demo-provider",
        "Authorisation request created",
    )
    db.commit()

except Exception:
    db.rollback()
    raise

return jsonify({
    "request_id": request_id,
    "status": "submitted",
    "created_at": created_at,
    "simulated": True,
}), 201

@bp.get("/api/authorisations")
def list_authorisations():
status = request.args.get("status")

if status and status not in VALID_STATUSES:
    return jsonify({
        "error": "validation_error",
        "message": "Invalid status filter.",
    }), 400

db = get_db()

if status:
    rows = db.execute(
        """
        SELECT * FROM authorisation_requests
        WHERE status = ?
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (status,),
    ).fetchall()
else:
    rows = db.execute(
        """
        SELECT * FROM authorisation_requests
        ORDER BY created_at DESC
        LIMIT 100
        """
    ).fetchall()

return jsonify({
    "results": [dict(row) for row in rows],
    "count": len(rows),
    "simulated": True,
})

@bp.get("/api/authorisations/<request_id>")
def get_authorisation(request_id):
db = get_db()

row = db.execute(
    "SELECT * FROM authorisation_requests WHERE request_id = ?",
    (request_id,),
).fetchone()

if row is None:
    return jsonify({
        "error": "not_found",
        "message": "Authorisation request not found.",
    }), 404

events = db.execute(
    """
    SELECT event_id, from_state, to_state, actor, reason, created_at
    FROM workflow_events
    WHERE request_id = ?
    ORDER BY created_at, event_id
    """,
    (request_id,),
).fetchall()

return jsonify({
    "request": dict(row),
    "events": [dict(event) for event in events],
    "simulated": True,
})

@bp.patch("/api/authorisations/<request_id>/status")
def update_authorisation_status(request_id):
body = json_body()
if body is None:
return jsonify({
"error": "validation_error",
"message": "A JSON object is required.",
}), 400

new_status = body.get("status")
actor = body.get("actor")
reason = body.get("reason")

if new_status not in VALID_STATUSES:
    return jsonify({
        "error": "validation_error",
        "message": "A valid status is required.",
    }), 400

# Demo attribution only; this is not verified authentication.
if not isinstance(actor, str) or not actor.strip():
    return jsonify({
        "error": "validation_error",
        "message": "actor is required for the demo.",
    }), 400

if reason is not None and not isinstance(reason, str):
    return jsonify({
        "error": "validation_error",
        "message": "reason must be a string.",
    }), 400

db = get_db()

try:
    row = db.execute(
        "SELECT status FROM authorisation_requests WHERE request_id = ?",
        (request_id,),
    ).fetchone()

    if row is None:
        return jsonify({
            "error": "not_found",
            "message": "Authorisation request not found.",
        }), 404

    old_status = row["status"]

    if new_status not in TRANSITIONS.get(old_status, set()):
        return jsonify({
            "error": "invalid_transition",
            "message": f"Cannot transition from {old_status} to {new_status}.",
        }), 409

    if new_status in {"approved", "declined"} and not (
        isinstance(reason, str) and reason.strip()
    ):
        return jsonify({
            "error": "validation_error",
            "message": "A reason is required for approval or decline.",
        }), 400

    db.execute(
        """
        UPDATE authorisation_requests
        SET status = ?, updated_at = ?
        WHERE request_id = ?
        """,
        (new_status, now_ts(), request_id),
    )

    record_event(
        db,
        request_id,
        old_status,
        new_status,
        actor.strip(),
        reason.strip() if isinstance(reason, str) and reason.strip() else None,
    )

    db.commit()

except Exception:
    db.rollback()
    raise

return jsonify({
    "request_id": request_id,
    "previous_status": old_status,
    "status": new_status,
    "simulated": True,
})