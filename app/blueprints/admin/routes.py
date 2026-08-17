"""On-demand DB init: runs Alembic upgrade + seed via HTTP.

Meant for one-shot use after a Railway/Fly.io deploy where you'd rather not
put migrations in the container startCommand (they can hang and block the
healthcheck). Hit /admin/init-db once — it's idempotent, so re-hits are
safe (migrations only apply what's missing; seed skips if teacher exists).

Optional protection: set ADMIN_INIT_TOKEN in env; then requests must include
?token=<value> or an X-Admin-Token header. Without the env var, the
endpoint refuses to seed once any users exist (so an attacker can't reset
your data by hitting it, only inspect the state).
"""
from __future__ import annotations
import os
import traceback

from flask import Blueprint, jsonify, request, current_app
from flask_migrate import upgrade as alembic_upgrade

from app.extensions import db, csrf
from app.models.user import User
from app.services.seed import seed_demo_data

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _token_ok() -> bool:
    expected = os.getenv("ADMIN_INIT_TOKEN")
    if not expected:
        return True  # token not required; endpoint self-guards via idempotency
    supplied = request.args.get("token") or request.headers.get("X-Admin-Token", "")
    return supplied == expected


@bp.route("/init-db", methods=["GET", "POST"])
@csrf.exempt
def init_db():
    if not _token_ok():
        return jsonify({"ok": False, "error": "token required"}), 401

    steps = []
    # 1. Migrations — always safe to re-run
    try:
        alembic_upgrade()
        steps.append({"step": "migrations", "status": "ok"})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("init-db migrations failed")
        return jsonify({
            "ok": False,
            "steps": steps,
            "failed_at": "migrations",
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc().splitlines()[-15:],
        }), 500

    # 2. Seed — idempotent, refuses to touch a populated DB
    try:
        result = seed_demo_data()
        steps.append({"step": "seed", "status": "ok", "detail": result})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("init-db seed failed")
        return jsonify({
            "ok": False,
            "steps": steps,
            "failed_at": "seed",
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc().splitlines()[-15:],
        }), 500

    return jsonify({
        "ok": True,
        "steps": steps,
        "login": {
            "url": request.host_url + "auth/login",
            "teacher": "teacher@example.com",
            "student": "student@example.com",
            "password": "password",
        },
    })


@bp.route("/db-status", methods=["GET"])
def db_status():
    """Quick read-only check: does the DB have the tables, and how many users?"""
    if not _token_ok():
        return jsonify({"ok": False, "error": "token required"}), 401
    try:
        n_users = User.query.count()
        return jsonify({"ok": True, "users": n_users, "db_url_scheme": db.engine.url.drivername})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500
