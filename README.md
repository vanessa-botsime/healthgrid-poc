IMISI HealthGrid PoC

A Flask-based proof of concept for healthcare member eligibility checks, care-authorisation workflows, and operational reporting.

Overview

HealthGrid demonstrates a workflow between healthcare providers and medical scheme administrators:

1. A provider looks up a member.
2. The system performs a simulated eligibility check.
3. The provider submits a care-authorisation request.
4. The request moves through a review workflow.
5. Workflow events are recorded for audit purposes.
6. Operational metrics summarise request statuses and processing performance.

Important: This proof of concept uses synthetic data and simulated eligibility decisions. It is not intended for real patient data or production use.

Technology stack

- Python
- Flask
- SQLite
- REST-style JSON API
- Git and GitHub

Project structure

healthgrid-data/
├── app.py
├── eligibility.py
├── authorisations.py
├── metrics.py
├── seed.py
├── requirements.txt
└── tests/
    └── test_api.py

- "app.py" — application entry point, API registration, health endpoint, and development server configuration.
- "eligibility.py" — member lookup, reference data, and simulated eligibility checks.
- "authorisations.py" — authorisation request creation and workflow management.
- "metrics.py" — operational metrics, status counts, and pending-request reporting.
- "seed.py" — prepares the local synthetic database.
- "tests/" — automated API tests.

Requirements

- Python 3
- pip

Setup and installation

Open a terminal in the "healthgrid-data/" directory.

Install the dependencies:

python -m pip install -r requirements.txt

Prepare the synthetic database:

python seed.py

Start the API:

python app.py

The development API runs at:

"http://127.0.0.1:5001"

Health check:

"GET http://127.0.0.1:5001/api/health"

Keep the terminal running while making API requests.

API endpoints

The following endpoints are implemented in the eligibility and metrics modules.

Method| Endpoint| Purpose
GET| "/api/health"| Check whether the API is running
GET| "/api/members/<member_id>"| Retrieve a member summary
GET| "/api/members?q=<text>"| Search members by member ID or last name
GET| "/api/reference"| Retrieve provider and service-category reference data
POST| "/api/eligibility-checks"| Perform a simulated eligibility check
GET| "/api/metrics/operations"| Retrieve operational metrics

Authorisation endpoints are implemented in "authorisations.py". Check its Flask route decorators for the exact request paths and supported methods.

Example: member lookup

curl http://127.0.0.1:5001/api/members/SYN-100001

Replace the example member ID with an ID present in the synthetic seed data.

Example: search members

curl "http://127.0.0.1:5001/api/members?q=Smith"

Example: reference data

curl http://127.0.0.1:5001/api/reference

Example: eligibility check

curl -X POST http://127.0.0.1:5001/api/eligibility-checks \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "SYN-100001",
    "service_category": "consultation"
  }'

Use a member ID and service category that exist in your seed data. The exact request fields and accepted category values are defined in "eligibility.py".

Example: operational metrics

curl http://127.0.0.1:5001/api/metrics/operations

The metrics endpoint supports optional "from" and "to" date filters, using calendar dates in "YYYY-MM-DD" format.

Running tests

From "healthgrid-data/":

python -m unittest discover -s tests -v

Confirm that the tests pass before committing changes.

Security considerations

- Use synthetic data only.
- Validate request bodies and enforce permitted workflow transitions on the backend.
- Keep audit events consistent with successful workflow changes.
- CORS configuration is not authentication.
- Any demo role header is not a substitute for verified identity and server-side access control.
- Do not expose Flask debug mode or development credentials in a production environment.
- Real healthcare use would require appropriate access controls, privacy safeguards, secure deployment, and compliance review.

Current limitations

- Eligibility decisions are simulated.
- The local SQLite database is for demonstration and testing.
- The static HTML mock must be integrated with the API before browser actions call the backend.
- Authentication and production-grade authorisation are not provided merely by configuring CORS or demo role headers.

Team contribution

This backend PoC supports member eligibility, authorisation workflows, auditability, and operational reporting. Coordinate changes with teammates before merging shared files.

License

Internal proof of concept. Add the project's agreed licence before public distribution.