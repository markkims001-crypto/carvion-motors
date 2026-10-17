# routes/auth.py
"""Carvion Motors authentication and password-reset routes."""

import hashlib
import hmac
import importlib
import os
import secrets
import time

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User

auth = Blueprint("auth", __name__)

try:
    africastalking = importlib.import_module("africastalking")
except ImportError:
    africastalking = None

try:
    resend = importlib.import_module("resend")
except ImportError:
    resend = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def normalise_phone(phone):
    """Normalise common Kenyan phone formats to 254XXXXXXXXX."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        return "254" + digits[1:]
    if len(digits) == 9 and digits.startswith(("1", "7")):
        return "254" + digits
    if len(digits) == 12 and digits.startswith("254"):
        return digits
    return digits


def phone_matches(stored_phone, submitted_phone):
    stored = normalise_phone(stored_phone)
    submitted = normalise_phone(submitted_phone)
    return bool(stored and submitted and hmac.compare_digest(stored, submitted))


def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt="carvion-password-reset")


def verify_reset_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return serializer.loads(token, salt="carvion-password-reset", max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


def otp_digest(code):
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    return hmac.new(secret, code.encode("utf-8"), hashlib.sha256).hexdigest()


def clear_sms_reset_session():
    for key in (
        "sms_reset_user_id", "sms_reset_code_hash", "sms_reset_expires_at",
        "sms_reset_attempts", "sms_reset_sent_at", "sms_reset_verified",
    ):
        session.pop(key, None)


# ----------------------------------------------------------------------
# Resend email reset helper (optional alternative)
# ----------------------------------------------------------------------

def send_reset_email(user, reset_url):
    if resend is None:
        current_app.logger.error("Email reset failed: resend package is not installed.")
        return False

    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip()
    if not api_key or not from_email:
        current_app.logger.error(
            "Email reset requires RESEND_API_KEY and RESEND_FROM_EMAIL."
        )
        return False

    try:
        resend.api_key = api_key
        response = resend.Emails.send({
            "from": from_email,
            "to": [user.email],
            "subject": "Carvion Motors password reset",
            "text": (
                f"Hello {user.name},\n\nReset your password using this link:\n"
                f"{reset_url}\n\nThis link expires in one hour. "
                "If you did not request this, ignore this email."
            ),
            "html": (
                f"<p>Hello {user.name},</p>"
                "<p>Use the link below to reset your Carvion Motors password. "
                "It expires in one hour.</p>"
                f'<p><a href="{reset_url}">Reset my password</a></p>'
                "<p>If you did not request this, ignore this email.</p>"
            ),
        })
        return bool(response)
    except Exception:
        current_app.logger.exception("Password reset email sending failed.")
        return False


# ----------------------------------------------------------------------
# Africa's Talking SMS
# ----------------------------------------------------------------------


def send_reset_sms(phone, code):
    username = os.environ.get("AT_USERNAME", "").strip()
    api_key = os.environ.get("AT_API_KEY", "").strip()
    sender_id = os.environ.get("AT_SENDER_ID", "").strip()

    if africastalking is None:
        current_app.logger.error(
            "Africa's Talking SDK is not installed."
        )
        return False

    if not username or not api_key:
        current_app.logger.error(
            "AT_USERNAME or AT_API_KEY is missing."
        )
        return False

    normalised = normalise_phone(phone)

    if not normalised or not normalised.startswith("254"):
        current_app.logger.error("Invalid Kenyan phone number.")
        return False

    recipient = "+" + normalised
    message = (
        f"Your Carvion Motors password reset code is {code}. "
        "It expires in 10 minutes. Do not share this code."
    )

    try:
        africastalking.initialize(username, api_key)

        if sender_id:
            response = africastalking.SMS.send(
                message, [recipient], sender_id=sender_id
            )
        else:
            response = africastalking.SMS.send(
                message, [recipient]
            )

        data = (
            response.get("SMSMessageData", {})
            if isinstance(response, dict)
            else {}
        )
        recipients = data.get("Recipients", [])

        if not recipients:
            current_app.logger.error(
                "Africa's Talking returned no recipient results."
            )
            return False

        for item in recipients:
            current_app.logger.info(
                "SMS result: status=%s, number=%s",
                item.get("status"),
                item.get("number"),
            )

        return any(
            str(item.get("statusCode")) == "101"
            for item in recipients
        )

    except Exception:
        current_app.logger.exception(
            "Africa's Talking SMS sending failed."
        )
        return False


# ----------------------------------------------------------------------
# Save new password after SMS verification
# ----------------------------------------------------------------------

@auth.route("/reset-password-sms", methods=["GET", "POST"])
def reset_password_sms():
    if not session.get("sms_reset_verified"):
        flash("Verify your SMS code before changing your password.", "warning")
        return redirect(url_for("auth.forgot_password"))

    if int(time.time()) > int(session.get("sms_reset_expires_at", 0)):
        clear_sms_reset_session()
        flash("That reset session has expired. Request a new code.", "warning")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, session.get("sms_reset_user_id"))
    if user is None:
        clear_sms_reset_session()
        flash("Account not found. Request a new reset code.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.reset_password_sms"))
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password_sms"))

        try:
            user.password = generate_password_hash(password)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("SMS password reset database update failed.")
            flash("Unable to update your password right now. Please try again.", "danger")
            return redirect(url_for("auth.reset_password_sms"))

        clear_sms_reset_session()
        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=None, sms_reset=True)


# ----------------------------------------------------------------------
# Optional email reset-link flow
# ----------------------------------------------------------------------

@auth.route("/forgot-password-email", methods=["GET", "POST"])
def forgot_password_email():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_reset_email(user, reset_url)

        flash(
            "If an account exists for that email, a password reset link has been sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html", email_reset=True)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password_email"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.forgot_password_email"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.reset_password", token=token))
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        try:
            user.password = generate_password_hash(password)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Email password reset database update failed.")
            flash("Unable to update your password right now. Please try again.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token, sms_reset=False)


# ----------------------------------------------------------------------
# Logout and profile
# ----------------------------------------------------------------------

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@auth.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


@auth.route("/force_logout")
def force_logout():
    logout_user()
    return redirect(url_for("auth.login"))

# ----------------------------------------------------------------------
# LOGIN
# ----------------------------------------------------------------------

@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Welcome back!", "success")

            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)

            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ----------------------------------------------------------------------
# REGISTRATION
# ----------------------------------------------------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not phone:
            flash("Please complete all required fields.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            try:
                user = User(
                    name=name,
                    email=email,
                    phone=phone,
                    password=generate_password_hash(password),
                    role="buyer",
                )
                db.session.add(user)
                db.session.commit()

                flash("Account created. You can now log in.", "success")
                return redirect(url_for("auth.login"))

            except Exception:
                db.session.rollback()
                current_app.logger.exception("Registration failed.")
                flash("Registration failed. Please try again.", "danger")

    return render_template("register.html")


# ----------------------------------------------------------------------
# SMS PASSWORD RESET REQUEST
# ----------------------------------------------------------------------

@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        normalised = normalise_phone(phone)

        user = None
        for candidate in User.query.all():
            if phone_matches(candidate.phone, normalised):
                user = candidate
                break

        if user:
            now = int(time.time())
            previous_sent = int(session.get("sms_reset_sent_at", 0))

            if now - previous_sent < 60:
                flash("Please wait before requesting another code.", "warning")
                return render_template("forgot_password.html")

            code = f"{secrets.randbelow(1_000_000):06d}"

            clear_sms_reset_session()

            if send_reset_sms(user.phone, code):
                session["sms_reset_user_id"] = user.id
                session["sms_reset_code_hash"] = otp_digest(code)
                session["sms_reset_expires_at"] = now + 600
                session["sms_reset_attempts"] = 0
                session["sms_reset_sent_at"] = now

                flash("If your number matches an account, a reset code has been sent.", "info")
                return redirect(url_for("auth.verify_reset_code"))

            clear_sms_reset_session()
            flash("We could not send the reset code. Please try again later.", "danger")
        else:
            flash("If your number matches an account, a reset code will be sent.", "info")

    return render_template("forgot_password.html")


# ----------------------------------------------------------------------
# VERIFY SMS RESET CODE
# ----------------------------------------------------------------------

@auth.route("/verify-reset-code", methods=["GET", "POST"])
def verify_reset_code():
    user_id = session.get("sms_reset_user_id")
    expires_at = int(session.get("sms_reset_expires_at", 0))

    if not user_id or int(time.time()) > expires_at:
        clear_sms_reset_session()
        flash("Your reset code has expired. Please request another.", "warning")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        attempts = int(session.get("sms_reset_attempts", 0))

        if attempts >= 5:
            clear_sms_reset_session()
            flash("Too many incorrect attempts. Request a new code.", "danger")
            return redirect(url_for("auth.forgot_password"))

        submitted_code = request.form.get("code", "").strip()
        expected_hash = session.get("sms_reset_code_hash", "")
        submitted_hash = otp_digest(submitted_code)

        if not submitted_code or not hmac.compare_digest(
            expected_hash, submitted_hash
        ):
            session["sms_reset_attempts"] = attempts + 1
            flash("Incorrect verification code.", "danger")
        else:
            session["sms_reset_verified"] = True
            return redirect(url_for("auth.reset_password_sms"))

    return render_template("verify_reset_code.html")
