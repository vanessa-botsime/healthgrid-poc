-- IMISI HealthGrid PoC - database schema (SQLite)
-- ALL DATA IS SYNTHETIC. No real members, patients or organisations.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS workflow_events;
DROP TABLE IF EXISTS authorisation_requests;
DROP TABLE IF EXISTS eligibility_checks;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS plan_services;
DROP TABLE IF EXISTS plans;
DROP TABLE IF EXISTS providers;
DROP TABLE IF EXISTS payers;

-- Insurers / HMOs
CREATE TABLE payers (
    payer_id        TEXT PRIMARY KEY,           -- e.g. PAY-001
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('HMO', 'INSURER')),
    country         TEXT NOT NULL DEFAULT 'NG',
    status          TEXT NOT NULL DEFAULT 'active'
);

-- Insurance plans offered by payers
CREATE TABLE plans (
    plan_id             TEXT PRIMARY KEY,       -- e.g. PLN-001
    payer_id            TEXT NOT NULL REFERENCES payers(payer_id),
    name                TEXT NOT NULL,
    tier                TEXT NOT NULL CHECK (tier IN ('micro', 'basic', 'standard', 'premium')),
    annual_limit_ngn    INTEGER NOT NULL,
    requires_auth_above_ngn INTEGER NOT NULL    -- requests above this amount need prior authorisation
);

-- Which service categories each plan covers
CREATE TABLE plan_services (
    plan_id             TEXT NOT NULL REFERENCES plans(plan_id),
    service_category    TEXT NOT NULL,
    covered             INTEGER NOT NULL CHECK (covered IN (0, 1)),
    requires_auth       INTEGER NOT NULL CHECK (requires_auth IN (0, 1)),
    PRIMARY KEY (plan_id, service_category)
);

-- Hospitals, clinics, labs, pharmacies
CREATE TABLE providers (
    provider_id     TEXT PRIMARY KEY,           -- e.g. PRV-001
    name            TEXT NOT NULL,
    facility_type   TEXT NOT NULL,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
);

-- Insured members (synthetic)
CREATE TABLE members (
    member_id       TEXT PRIMARY KEY,           -- e.g. SYN-100001
    payer_member_ref TEXT NOT NULL,             -- the payer's own reference
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    date_of_birth   TEXT NOT NULL,              -- ISO date
    sex             TEXT NOT NULL CHECK (sex IN ('F', 'M')),
    phone_masked    TEXT NOT NULL,              -- masked, never a real number
    plan_id         TEXT NOT NULL REFERENCES plans(plan_id),
    status          TEXT NOT NULL CHECK (status IN ('active', 'expired', 'suspended', 'pending')),
    effective_from  TEXT NOT NULL,
    effective_to    TEXT NOT NULL,
    used_amount_ngn INTEGER NOT NULL DEFAULT 0
);

-- Every eligibility check made through the mock adapter
CREATE TABLE eligibility_checks (
    check_id        TEXT PRIMARY KEY,           -- e.g. ELG-xxxxxxxx
    member_id       TEXT,                       -- nullable: not-found lookups are logged too
    provider_id     TEXT,
    service_category TEXT,
    result          TEXT NOT NULL CHECK (result IN ('eligible', 'ineligible', 'unknown', 'unavailable')),
    reason          TEXT,
    source          TEXT NOT NULL,              -- adapter name
    checked_at      TEXT NOT NULL
);

-- Care authorisation requests (Vanessa's workflow owns the transitions)
CREATE TABLE authorisation_requests (
    request_id      TEXT PRIMARY KEY,           -- e.g. AUTH-0001
    member_id       TEXT NOT NULL REFERENCES members(member_id),
    provider_id     TEXT NOT NULL REFERENCES providers(provider_id),
    service_category TEXT NOT NULL,
    service_description TEXT,
    requested_date  TEXT,
    urgency         TEXT NOT NULL CHECK (urgency IN ('routine', 'urgent')),
    estimated_cost_ngn INTEGER,
    reason          TEXT,
    status          TEXT NOT NULL CHECK (status IN (
                        'draft', 'submitted', 'under_review', 'more_info_needed',
                        'approved', 'declined', 'cancelled', 'closed')),
    missing_fields  TEXT,                       -- JSON array of missing field names, if any
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Append-only audit trail of status changes
CREATE TABLE workflow_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      TEXT NOT NULL REFERENCES authorisation_requests(request_id),
    actor           TEXT NOT NULL,
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_members_plan ON members(plan_id);
CREATE INDEX idx_auth_status ON authorisation_requests(status);
CREATE INDEX idx_events_request ON workflow_events(request_id);
