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


@bp.route("/gemini-models", methods=["GET"])
def gemini_models():
    """List Gemini models this key can actually use. Delete after debugging."""
    if not _token_ok():
        return jsonify({"ok": False, "error": "token required"}), 401
    key = current_app.config.get("GEMINI_API_KEY")
    if not key:
        return jsonify({"ok": False, "error": "no GEMINI_API_KEY"}), 400
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        models = []
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                models.append({"name": m.name, "display": getattr(m, "display_name", "")})
        return jsonify({"ok": True, "count": len(models), "models": models})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}",
                        "trace": traceback.format_exc().splitlines()[-15:]}), 500


@bp.route("/gemini-probe", methods=["GET", "POST"])
def gemini_probe():
    """Temporary: send a canned prompt to Gemini and return the raw response
    + parsed length. Delete after debugging."""
    if not _token_ok():
        return jsonify({"ok": False, "error": "token required"}), 401
    key = current_app.config.get("GEMINI_API_KEY")
    if not key:
        return jsonify({"ok": False, "error": "no GEMINI_API_KEY"}), 400

    sample = (
        "1. If 3x + 5 = 20, what is the value of x?\n"
        "A) 3\nB) 5\nC) 15\nD) 25\n\n"
        "2. A circle has radius 4. What is its area in terms of pi?\n"
        "A. 4pi\nB. 8pi\nC. 16pi\nD. 32pi\n"
    )
    try:
        import google.generativeai as genai
        from app.services.ingest.llm_extract import _render_prompt
        genai.configure(api_key=key)
        model_name = current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash")
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",
            },
        )
        resp = model.generate_content(_render_prompt(sample))
        raw = (resp.text or "")
        import json as _json
        parsed_len = None
        parse_err = None
        try:
            parsed = _json.loads(raw)
            parsed_len = len(parsed) if isinstance(parsed, list) else -1
        except Exception as e:  # noqa: BLE001
            parse_err = str(e)
        return jsonify({
            "ok": True,
            "model": model_name,
            "raw_response": raw,
            "raw_len": len(raw),
            "parsed_len": parsed_len,
            "parse_error": parse_err,
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc().splitlines()[-15:],
        }), 500


@bp.route("/ingest-probe", methods=["GET"])
def ingest_probe():
    """Tell me which LLM extraction path is active.

    Priority: Gemini > Anthropic > heuristic.
    """
    if not _token_ok():
        return jsonify({"ok": False, "error": "token required"}), 401
    gemini_set = bool(current_app.config.get("GEMINI_API_KEY"))
    anthropic_set = bool(current_app.config.get("ANTHROPIC_API_KEY"))
    if gemini_set:
        provider = "gemini"
    elif anthropic_set:
        provider = "anthropic"
    else:
        provider = "heuristic"

    hint = {
        "gemini":    f"Gemini path active — using {current_app.config.get('GEMINI_MODEL', 'gemini-3.6-flash')}.",
        "anthropic": "Anthropic Claude path active.",
        "heuristic": ("No LLM key set — uploads fall back to a regex parser that "
                      "only handles well-structured text. Set GEMINI_API_KEY or "
                      "ANTHROPIC_API_KEY on Railway to enable real extraction."),
    }[provider]

    return jsonify({
        "ok": True,
        "llm": provider,
        "gemini_key_set": gemini_set,
        "anthropic_key_set": anthropic_set,
        "gemini_model": current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash"),
        "prompt_version": current_app.config.get("INGEST_PROMPT_VERSION", "v1"),
        "hint": hint,
    })
