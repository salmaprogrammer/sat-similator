"""Entry point for the SAT Simulator Flask app.

Per project CLAUDE.md: this is the single canonical entry point. All scripts
(seed, WSGI, CLI) go through create_app() here so the DB path stays consistent.

Dev run:
    lsof -ti:5000 | xargs kill -9 2>/dev/null
    flask db upgrade
    flask seed
    flask run
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
