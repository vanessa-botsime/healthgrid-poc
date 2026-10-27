"""
Standalone runner so the data layer can be tested on its own.

    pip install flask
    python seed.py
    python app.py          # http://localhost:5001

To plug into the main backend instead:

    from eligibility import bp as eligibility_bp
    from metrics import bp as metrics_bp
    app.config["HEALTHGRID_DB"] = "healthgrid.db"
    app.config["HEALTHGRID_TODAY"] = "2026-10-28"   # optional: pin demo date
    app.register_blueprint(eligibility_bp)
    app.register_blueprint(metrics_bp)
"""
from authorisations import bp as authorisations_bp

from pathlib import Path

from flask import Flask, jsonify

from eligibility import bp as eligibility_bp
from metrics import bp as metrics_bp

app = Flask(__name__)
app.config["HEALTHGRID_DB"] = str(Path(__file__).resolve().parent / "healthgrid.db")
app.config["HEALTHGRID_TODAY"] = "2026-10-28"
app.register_blueprint(eligibility_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(authorisations_bp)

@app.after_request
def cors(resp):
    # Lets the frontend call the API from another local port during the demo.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PATCH"
    return resp


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "simulated": True})


if __name__ == "__main__":
    app.run(port=5001, debug=True)
