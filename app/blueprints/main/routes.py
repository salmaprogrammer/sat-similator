from pathlib import Path

from flask import Blueprint, render_template, send_from_directory, abort, current_app, redirect
from flask_login import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/healthz")
def healthz():
    return {"status": "ok"}


@bp.route("/uploads/<path:filename>")
@login_required
def serve_upload(filename: str):
    """Serve locally-stored uploaded files (question images, ingested docs).

    Only used in dev / when S3 isn't configured. In S3 mode the storage handles
    are `s3://` URLs and this route isn't hit.
    """
    if current_app.config.get("S3_BUCKET"):
        abort(404)
    if "/" in filename or ".." in filename or filename.startswith("."):
        abort(404)  # basic path-traversal guard; storage names uuids
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    return send_from_directory(folder, filename)
