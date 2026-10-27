# HealthGrid PoC: data layer (DB, seed data, mock eligibility, metrics)

Covers the 3 items Vanessa asked for:
1. Database schema + synthetic seed data (members, plans, providers, sample requests)
2. Mock eligibility adapter + member lookup
3. Metrics endpoint for the dashboard

**All data is synthetic.** Every response carries `"simulated": true` (PRD FR-05, FR-16).

## Run it (2 minutes)

```bash
pip install flask
python seed.py        # creates healthgrid.db (deterministic: same IDs for everyone)
python app.py         # http://localhost:5001
```

## Plug into the main backend

```python
from eligibility import bp as eligibility_bp
from metrics import bp as metrics_bp

app.config["HEALTHGRID_DB"] = "healthgrid.db"
app.config["HEALTHGRID_TODAY"] = "2026-10-28"   # optional: pins the demo date
app.register_blueprint(eligibility_bp)
app.register_blueprint(metrics_bp)
```

The `authorisation_requests` and `workflow_events` tables are ready for the
workflow/state machine. Statuses allowed: `draft, submitted, under_review,
more_info_needed, approved, declined, cancelled, closed`. The metrics endpoint
reads these tables live, so new requests and events show up on the dashboard
immediately.

Using PostgreSQL instead? `schema.sql` is plain SQL, and `seed_data.json`
contains every row if you prefer to load it another way.

## Files

| File | What it is |
|---|---|
| `schema.sql` | Tables: payers, plans, plan_services, providers, members, eligibility_checks, authorisation_requests, workflow_events |
| `seed.py` | Builds `healthgrid.db`: 3 payers, 6 plans, 8 providers, 40 members, 25 requests, 61 audit events |
| `eligibility.py` | Blueprint: member lookup, search, reference data, mock eligibility check |
| `metrics.py` | Blueprint: dashboard metrics |
| `app.py` | Standalone runner (with CORS for the frontend) |
| `seed_data.json` | Same seed data as JSON (for frontend mocks or Postgres import) |

## Endpoints

### `GET /api/members/<member_id>`
```json
{ "member": { "member_id": "SYN-100001", "payer_member_ref": "HMO-100001-2",
  "name": "Adaeze Okafor", "year_of_birth": 1991, "sex": "F",
  "phone_masked": "+234 80* *** 1234", "status": "active",
  "plan": { "plan_id": "PLN-002", "name": "Harmony Family Plus", "tier": "standard", "payer": "Harmony Care HMO" },
  "effective_from": "2026-01-01", "effective_to": "2026-12-31" }, "simulated": true }
```
404 `{ "error": "member_not_found" }` if unknown.

### `GET /api/members?q=Oka`
Search by member ID prefix or last name, max 10 results.

### `GET /api/reference`
Providers and service categories, for the frontend dropdowns.

### `POST /api/eligibility-checks`
Request:
```json
{ "member_id": "SYN-100001", "provider_id": "PRV-001", "service_category": "imaging" }
```
Only `member_id` is required. Response (200):
```json
{ "check_id": "ELG-3F2A91BC", "result": "eligible",
  "reason": "Member is active and covered on this date.",
  "member": { "...": "same as member lookup" },
  "service_category": "imaging", "service_covered": true,
  "requires_authorisation": true, "auth_threshold_ngn": 100000,
  "annual_limit_ngn": 1500000, "remaining_limit_ngn": 1380000,
  "limitations": ["Prior care authorisation is required for this service."],
  "next_step": "create_authorisation_request",
  "source": "mock-payer-adapter v0.1 (simulated)", "checked_at": "2026-10-28T10:15:02",
  "simulated": true, "disclaimer": "Simulated response on synthetic data. ..." }
```
`result` is one of `eligible | ineligible | unknown | unavailable`.
`next_step` is one of `create_authorisation_request | proceed_with_care | contact_payer`.
Every check is logged in `eligibility_checks`.

### `GET /api/metrics/operations?from=YYYY-MM-DD&to=YYYY-MM-DD`
Filters are optional. Returns totals, `by_status`, `by_service_category`,
`pending_queue_count`, `awaiting_more_info`, `urgent_pending`,
`incomplete_requests`, `approval_rate_pct`, turnaround hours (median, p90),
eligibility checks by result, and the 10 oldest pending requests (urgent first).

## Demo scenarios (fixed member IDs)

| Member ID | Story | Result |
|---|---|---|
| SYN-100001 | Active, standard plan (happy path) | eligible, imaging needs authorisation |
| SYN-100002 | Policy expired | ineligible |
| SYN-100003 | Micro plan, try `imaging` | ineligible: service not covered |
| SYN-100004 | Suspended (unpaid premium) | ineligible |
| SYN-100005 | Micro family, try `maternity` | eligible, low remaining limit warning |
| SYN-100006 | Premium corporate member | eligible |
| SYN-100007 | Cover starts next month | ineligible: not started |
| SYN-999999 | Payer system down | 503 unavailable, retryable |
| any other ID | Unknown member | 404 unknown |

These cover the error/retry/unknown-member/unavailable-adapter scenarios
required by the PRD acceptance criteria (section 20).
