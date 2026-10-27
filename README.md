IMISI HealthGrid PoC

A Healthcare Eligibility and Care Authorisation Workflow System

Overview

IMISI HealthGrid is a proof of concept (PoC) designed to demonstrate a digital workflow between healthcare providers and medical scheme administrators.

The system allows healthcare providers to look up members, perform simulated eligibility checks, submit care authorisation requests, and track request statuses. It also provides operational metrics and an audit trail of workflow events.

Key Features

- Member Lookup: Retrieve and search synthetic healthcare member records.
- Eligibility Verification: Perform simulated eligibility checks based on member and plan information.
- Care Authorisation: Create and manage care authorisation requests.
- Workflow Management: Track requests through review and decision stages.
- Audit Trail: Record workflow events and status changes.
- Operational Metrics: View request counts, pending queues, approval rates, and processing turnaround times.
- REST API: Expose backend functionality through HTTP endpoints returning JSON responses.

«Note: This project uses synthetic demonstration data and simulated eligibility decisions. It is not intended for processing real patient information or making actual healthcare decisions.»

Technology Stack

Technology| Purpose
Python| Backend development
Flask| REST API and application routing
SQLite| Local database
JSON| API request and response format
Git and GitHub| Version control and collaboration

Project Structure

healthgrid-data/
├── app.py
├── eligibility.py
├── authorisations.py
├── metrics.py
├── seed.py
├── requirements.txt
├── README.md
└── tests/
    └── test_api.py

Main Components

- "app.py" — Initialises the Flask application, registers API blueprints, configures CORS, and exposes the health-check endpoint.
- "eligibility.py" — Handles member lookup, reference data, and simulated eligibility checks.
- "authorisations.py" — Manages care authorisation requests, workflow transitions, and associated audit events.
- "metrics.py" — Provides operational metrics and pending-request information.
- "seed.py" — Creates and populates the local database with synthetic demonstration data.
- "tests/" — Contains automated tests for API functionality.

Getting Started

Prerequisites

Ensure that you have the following installed:

- Python 3
- pip
- Git (if cloning the repository)

Installation

1. Navigate to the backend directory.

cd healthgrid-data

2. Install the required dependencies.

python -m pip install -r requirements.txt

3. Initialise the synthetic database.

python seed.py

«Run the seed script only when you intend to initialise or reset the demonstration database. Check its behaviour before running it against any existing data.»

4. Start the Flask application.

python app.py

The local API should be available at:

"http://127.0.0.1:5001"

API Documentation

The backend exposes HTTP endpoints for member management, eligibility checks, care authorisation, and operational reporting.

Available Endpoints

Method| Endpoint| Description
"GET"| "/api/health"| Checks API availability
"GET"| "/api/members/<member_id>"| Retrieves a member summary
"GET"| "/api/members?q=<text>"| Searches for members
"GET"| "/api/reference"| Retrieves provider and service-category reference data
"POST"| "/api/eligibility-checks"| Performs a simulated eligibility check
"GET"| "/api/metrics/operations"| Retrieves operational metrics

Care authorisation endpoints are defined in "authorisations.py". Refer to the route definitions in that file for their exact paths, supported methods, request fields, and response formats.

Example: Health Check

curl http://127.0.0.1:5001/api/health

Example: Member Lookup

curl http://127.0.0.1:5001/api/members/SYN-100001

Replace "SYN-100001" with a member ID available in your synthetic database.

Example: Eligibility Check

curl -X POST http://127.0.0.1:5001/api/eligibility-checks \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "SYN-100001",
    "service_category": "consultation"
  }'

Use a service category supported by the project's reference data.

Example: Operational Metrics

curl http://127.0.0.1:5001/api/metrics/operations

The metrics endpoint supports optional "from" and "to" date filters in "YYYY-MM-DD" format.

Running Tests

Run the automated tests from the backend directory:

python -m unittest discover -s tests -v

Review the test results before committing changes or merging a pull request.

Security Considerations

- Use synthetic data exclusively in the proof of concept.
- Validate incoming request data on the backend.
- Enforce valid workflow transitions and appropriate access permissions.
- Keep workflow status changes and corresponding audit events consistent.
- Do not treat CORS configuration as an authentication mechanism.
- Do not rely on client-supplied role headers as proof of identity.
- Disable debug mode and use appropriate access controls before any production deployment.

Current Limitations

- Eligibility checks are simulated and do not connect to a real insurer.
- The SQLite database is intended for local demonstration and testing.
- The frontend must be connected to the backend API for live data exchange.
- Production-grade authentication, authorisation, and deployment controls require further implementation and verification.

Testing and Collaboration

Contributors should test their changes locally, review their staged Git changes, and use feature branches and pull requests where possible.

Before merging, coordinate changes to shared files such as "app.py", database schema files, and API modules with the rest of the team.

Project Status

Proof of Concept — Under Development

This project demonstrates healthcare eligibility verification, care authorisation workflows, auditability, and operational reporting.

License

No public licence has been specified. Add the team's agreed licence before distributing the project publicly.