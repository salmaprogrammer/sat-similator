"""Google integrations (Sheets + Calendar).

Requires GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in .env. If unset, the connect
route shows setup instructions so the UI still renders in dev.

Full OAuth flow uses Authlib; token storage would go on the Student row in a
future migration. For v1 we scaffold the UI and gate on config.
"""
from __future__ import annotations
from flask import Blueprint, render_template, current_app, url_for, redirect, request, flash
from flask_login import login_required, current_user

bp = Blueprint("integrations", __name__, url_prefix="/integrations")


@bp.route("/google")
@login_required
def google_connect():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    return render_template(
        "integrations/google.html",
        configured=bool(client_id),
        client_id=client_id,
    )


@bp.route("/google/oauth-start", methods=["POST"])
@login_required
def google_oauth_start():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google OAuth isn't configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env.", "error")
        return redirect(url_for("integrations.google_connect"))
    # Real flow would go through Authlib here; placeholder for v1.
    flash("Google OAuth is scaffolded but requires production credentials to complete.", "info")
    return redirect(url_for("integrations.google_connect"))
