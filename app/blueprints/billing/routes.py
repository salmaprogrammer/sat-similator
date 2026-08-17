"""Paywall / Stripe integration.

Pricing model per the original spec: exam-date-scoped one-time payment (Pro
expires at the student's test date, or a default 60-day window if none is set).

In prod: Stripe Checkout + webhook. In dev without STRIPE_SECRET_KEY set,
a "Dev grant" button flips pro_expires_at directly so the ProGate UI is
testable without a real payment.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, current_app, abort, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db, csrf

bp = Blueprint("billing", __name__, url_prefix="/billing")

DEFAULT_PRO_WINDOW_DAYS = 60


def _pro_expiry_for(student) -> datetime:
    """Set Pro expiry to the student's test date (+ a buffer day) if set;
    otherwise a fixed 60-day window from today."""
    today = datetime.utcnow()
    if student.test_date:
        return datetime.combine(student.test_date, datetime.min.time()) + timedelta(days=1)
    return today + timedelta(days=DEFAULT_PRO_WINDOW_DAYS)


# ---------------------------------------------------------------------------
# Upgrade page
# ---------------------------------------------------------------------------

@bp.route("/upgrade", methods=["GET"])
@login_required
def upgrade():
    if not current_user.is_student:
        abort(403)
    stripe_ready = bool(current_app.config.get("STRIPE_SECRET_KEY"))
    return render_template(
        "billing/upgrade.html",
        student=current_user.student,
        stripe_ready=stripe_ready,
        pro_expires_at=current_user.student.pro_expires_at,
    )


# ---------------------------------------------------------------------------
# Real Stripe checkout (requires STRIPE_SECRET_KEY + a Stripe price ID)
# ---------------------------------------------------------------------------

@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    if not current_user.is_student:
        abort(403)
    if not current_app.config.get("STRIPE_SECRET_KEY"):
        flash("Stripe is not configured yet.", "error")
        return redirect(url_for("billing.upgrade"))

    import stripe
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "SatSimilator Pro — until test day"},
                "unit_amount": 2900,
            },
            "quantity": 1,
        }],
        client_reference_id=str(current_user.student.id),
        success_url=url_for("billing.success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("billing.upgrade", _external=True),
    )
    return redirect(session.url, code=303)


@bp.route("/success")
@login_required
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("billing.upgrade"))

    import stripe
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == "paid":
        student = current_user.student
        student.pro_expires_at = _pro_expiry_for(student)
        db.session.commit()
        flash("You're on Pro. Enjoy the full report.", "success")
    return redirect(url_for("student.dashboard"))


# ---------------------------------------------------------------------------
# Stripe webhook (Pro grant on payment_intent.succeeded)
# ---------------------------------------------------------------------------

@bp.route("/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    import stripe
    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception:  # noqa: BLE001
        return "", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        student_id = int(session.get("client_reference_id") or 0)
        from app.models.user import Student
        student = db.session.get(Student, student_id)
        if student:
            student.pro_expires_at = _pro_expiry_for(student)
            db.session.commit()
    return jsonify(received=True)


# ---------------------------------------------------------------------------
# Dev-only grant (no Stripe required) — makes ProGate testable
# ---------------------------------------------------------------------------

@bp.route("/dev-grant", methods=["POST"])
@login_required
def dev_grant():
    if not current_app.debug and not current_app.config.get("TESTING"):
        abort(404)
    if not current_user.is_student:
        abort(403)
    student = current_user.student
    student.pro_expires_at = _pro_expiry_for(student)
    db.session.commit()
    flash("Dev: Pro granted until " + student.pro_expires_at.strftime("%Y-%m-%d") + ".", "success")
    return redirect(url_for("billing.upgrade"))
