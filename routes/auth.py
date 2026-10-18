
# routes/auth.py
"""Carvion Motors authentication and password-reset routes."""

import hashlib
import hmac
import importlib
import os
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from extensions import db
from models import PasswordResetCode, User

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

def is_safe_next_url(target):
    """Accept only local absolute paths, never external or backslash URLs."""
    if not target or chr(92) in target:
        return False

    parsed = urlsplit(target)
    return (
        target.startswith("/")
        and not target.startswith("//")
        and not parsed.scheme
        and not parsed.netloc
    )


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

    return bool(
        stored
        and submitted
        and hmac.compare_digest(stored, submitted)
    )


def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )
    return serializer.dumps(
        email,
        salt="carvion-password-reset",
    )


def verify_reset_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    try:
        return serializer.loads(
            token,
            salt="carvion-password-reset",
            max_age=max_age,
        )
    except (SignatureExpired, BadSignature):
        return None


def otp_digest(code):
    secret = str(
        current_app.config["SECRET_KEY"]
    ).encode("utf-8")

    return hmac.new(
        secret,
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def clear_sms_reset_session():
    # Only a database record ID is kept in the signed client session.
    # OTP hashes, expiry, and attempt counts remain server-side.
    for key in (
        "sms_reset_user_id",
        "sms_reset_code_id",
        "sms_reset_code_hash",  # clear legacy session values
        "sms_reset_expires_at",
        "sms_reset_attempts",
        "sms_reset_sent_at",
        "sms_reset_verified",
    ):
        session.pop(key, None)


# ----------------------------------------------------------------------
# Resend email reset helper
# ----------------------------------------------------------------------

def send_reset_email(user, reset_url):
    if resend is None:
        current_app.logger.error(
            "Email reset failed: resend package is not installed."
        )
        return False

    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip()

    if not api_key or not from_email:
        current_app.logger.error(
            "Email reset requires RESEND_API_KEY and "
            "RESEND_FROM_EMAIL."
        )
        return False

    try:
        resend.api_key = api_key

        response = resend.Emails.send({
            "from": from_email,
            "to": [user.email],
            "subject": "Carvion Motors password reset",
            "text": (
                f"Hello {user.name},\n\n"
                "Reset your password using this link:\n"
                f"{reset_url}\n\n"
                "This link expires in one hour. "
                "If you did not request this, ignore this email."
            ),
            "html": (
                f"<p>Hello {user.name},</p>"
                "<p>Use the link below to reset your Carvion Motors "
                "password. It expires in one hour.</p>"
                f'<p><a href="{reset_url}">Reset my password</a></p>'
                "<p>If you did not request this, ignore this email.</p>"
            ),
        })

        if isinstance(response, dict):
            message_id = response.get("id")
        else:
            message_id = getattr(response, "id", None)

        if not message_id:
            current_app.logger.error(
                "Resend returned no message ID for the password-reset email."
            )
            return False

        current_app.logger.info(
            "Resend accepted password-reset email; message_id=%s",
            message_id,
        )
        return True

    except Exception:
        current_app.logger.exception(
            "Password reset email sending failed."
        )
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
                message,
                [recipient],
                sender_id=sender_id,
            )
        else:
            response = africastalking.SMS.send(
                message,
                [recipient],
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
    code_id = session.get("sms_reset_code_id")
    user_id = session.get("sms_reset_user_id")

    if not session.get("sms_reset_verified") or not code_id or not user_id:
        flash("Verify your SMS code before changing your password.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

    reset_record = db.session.get(PasswordResetCode, code_id)
    user = db.session.get(User, user_id)
    now = datetime.utcnow()

    if (
        reset_record is None
        or user is None
        or reset_record.user_id != user_id
        or reset_record.expires_at <= now
    ):
        clear_sms_reset_session()
        flash("That reset session has expired. Request a new code.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

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
            # Delete this code and any other outstanding reset codes so a
            # previously verified session cannot be replayed after success.
            PasswordResetCode.query.filter_by(user_id=user.id).delete(
                synchronize_session=False
            )
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
# SMS PASSWORD RESET REQUEST AND OTP VERIFICATION
# ----------------------------------------------------------------------

@auth.route("/forgot-password-sms", methods=["GET", "POST"])
def forgot_password_sms():
    if request.method == "GET":
        return render_template("forgot_password.html", sms_mode=True)

    phone = request.form.get("phone", "").strip()
    if not phone:
        flash("Enter the phone number linked to your account.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

    user = next(
        (
            candidate for candidate in User.query.all()
            if phone_matches(candidate.phone, phone)
        ),
        None,
    )

    # Keep the response generic to avoid exposing registered phone numbers.
    if user is None:
        flash(
            "If the number belongs to an account and SMS delivery is available, "
            "a reset code will be sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    now = datetime.utcnow()
    most_recent = (
        PasswordResetCode.query
        .filter_by(user_id=user.id)
        .order_by(PasswordResetCode.created_at.desc())
        .first()
    )
    last_sent = int(session.get("sms_reset_sent_at", 0) or 0)
    if (
        (most_recent and most_recent.created_at and
         (now - most_recent.created_at).total_seconds() < 60)
        or (int(time.time()) - last_sent < 60)
    ):
        flash("Please wait before requesting another reset code.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

    code = f"{secrets.randbelow(1_000_000):06d}"
    reset_record = PasswordResetCode(
        user_id=user.id,
        code_hash=otp_digest(code),
        expires_at=now + timedelta(minutes=10),
        attempts=0,
        created_at=now,
    )

    try:
        # Replace older codes before sending; only the latest code remains valid.
        PasswordResetCode.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )
        db.session.add(reset_record)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not create SMS password reset record.")
        flash("We could not start password recovery. Please try again later.", "danger")
        return redirect(url_for("auth.forgot_password_sms"))

    if not send_reset_sms(user.phone, code):
        # Keep the short-lived record for server-side rate limiting, but never
        # expose its ID to a client that did not receive a successful response.
        flash("We could not send the reset SMS. Please try again later.", "danger")
        return redirect(url_for("auth.forgot_password_sms"))

    session["sms_reset_user_id"] = user.id
    session["sms_reset_code_id"] = reset_record.id
    session["sms_reset_verified"] = False
    session["sms_reset_sent_at"] = int(time.time())
    session.permanent = False

    flash("If SMS delivery succeeded, your code should arrive shortly.", "info")
    return redirect(url_for("auth.verify_reset_code"))


@auth.route("/verify-reset-code", methods=["GET", "POST"])
def verify_reset_code():
    code_id = session.get("sms_reset_code_id")
    user_id = session.get("sms_reset_user_id")

    if not code_id or not user_id:
        flash("Request a password reset code first.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

    reset_record = db.session.get(PasswordResetCode, code_id)
    if (
        reset_record is None
        or reset_record.user_id != user_id
        or reset_record.expires_at <= datetime.utcnow()
    ):
        clear_sms_reset_session()
        flash("Your reset code expired. Request a new one.", "warning")
        return redirect(url_for("auth.forgot_password_sms"))

    if request.method == "POST":
        if reset_record.attempts >= 5:
            clear_sms_reset_session()
            flash("Too many incorrect attempts. Request a new code.", "danger")
            return redirect(url_for("auth.forgot_password_sms"))

        submitted_code = request.form.get("code", "").strip()
        if (
            not submitted_code.isdigit()
            or len(submitted_code) != 6
            or not hmac.compare_digest(
                otp_digest(submitted_code),
                reset_record.code_hash,
            )
        ):
            reset_record.attempts += 1
            db.session.commit()
            if reset_record.attempts >= 5:
                clear_sms_reset_session()
                flash("Too many incorrect attempts. Request a new code.", "danger")
                return redirect(url_for("auth.forgot_password_sms"))
            flash("That code is incorrect. Please try again.", "danger")
            return redirect(url_for("auth.verify_reset_code"))

        session["sms_reset_verified"] = True
        return redirect(url_for("auth.reset_password_sms"))

    return render_template("forgot_password.html", verify_sms=True)


# ----------------------------------------------------------------------
# Optional email reset-link flow
# ----------------------------------------------------------------------

@auth.route("/forgot-password-email", methods=["GET", "POST"])
def forgot_password_email():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = (
            User.query.filter_by(email=email).first()
            if email
            else None
        )

        if user:
            token = generate_reset_token(user.email)
            reset_url = url_for(
                "auth.reset_password",
                token=token,
                _external=True,
            )
            send_reset_email(user, reset_url)

        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template(
        "forgot_password.html",
        email_reset=True,
    )


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)

    if not email:
        flash(
            "The password reset link is invalid or has expired.",
            "danger",
        )
        return redirect(
            url_for("auth.forgot_password_email")
        )

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Account not found.", "danger")
        return redirect(
            url_for("auth.forgot_password_email")
        )

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if len(password) < 6:
            flash(
                "Password must be at least 6 characters.",
                "danger",
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        try:
            user.password = generate_password_hash(password)
            db.session.commit()

        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Email password reset database update failed."
            )
            flash(
                "Unable to update your password right now. "
                "Please try again.",
                "danger",
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        flash(
            "Password reset successfully. You can now log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template(
        "reset_password.html",
        token=token,
        sms_reset=False,
    )


# ----------------------------------------------------------------------
# Logout and profile
# ----------------------------------------------------------------------

@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@auth.route("/profile")
@login_required
def profile():
    return render_template(
        "profile.html",
        user=current_user,
    )


@auth.route("/force_logout", methods=["POST"])
@login_required
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

            if is_safe_next_url(next_url):
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
        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not name or not email or not phone:
            flash(
                "Please complete all required fields.",
                "danger",
            )

        elif len(password) < 6:
            flash(
                "Password must be at least 6 characters.",
                "danger",
            )

        elif password != confirm_password:
            flash("Passwords do not match.", "danger")

        elif User.query.filter_by(email=email).first():
            flash(
                "An account with that email already exists.",
                "danger",
            )

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

                flash(
                    "Account created. You can now log in.",
                    "success",
                )
                return redirect(url_for("auth.login"))

            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Registration failed."
                )
                flash(
                    "Registration failed. Please try again.",
                    "danger",
                )

    return render_template("register.html")


# ----------------------------------------------------------------------
# EMAIL PASSWORD RESET REQUEST
# ----------------------------------------------------------------------

@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if email:
            user = User.query.filter_by(email=email).first()

            # Log diagnostic status without exposing the email.
            current_app.logger.warning(
                "Password reset lookup: email_submitted=%s, "
                "account_found=%s",
                bool(email),
                user is not None,
            )

            if user:
                try:
                    token = generate_reset_token(user.email)

                    reset_url = url_for(
                        "auth.reset_password",
                        token=token,
                        _external=True,
                    )

                    sent = send_reset_email(user, reset_url)

                    current_app.logger.warning(
                        "Password reset email helper returned: %s",
                        sent,
                    )

                    if not sent:
                        current_app.logger.error(
                            "Password reset email could not be sent."
                        )

                except Exception:
                    current_app.logger.exception(
                        "Password reset request failed."
                    )

        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    # Email is the default recovery method for now. SMS remains available
    # at /forgot-password-sms while provider delivery is being resolved.
    return redirect(url_for("auth.forgot_password_email"))


# ----------------------------------------------------------------------
# EMAIL DELIVERY TEST
# ----------------------------------------------------------------------

@auth.route("/test-reset-email", methods=["GET"])
def test_reset_email():
    if (
        not current_app.config.get("TESTING")
        and not current_app.debug
    ):
        if os.environ.get("ENABLE_EMAIL_TEST_ROUTE") != "true":
            return "Not found", 404

    if resend is None:
        return "Resend package is not installed.", 500

    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip()

    if not api_key or not from_email:
        return (
            "Missing RESEND_API_KEY or RESEND_FROM_EMAIL.",
            500,
        )

    try:
        resend.api_key = api_key

        response = resend.Emails.send({
            "from": from_email,
            "to": ["markkims001@gmail.com"],
            "subject": "Carvion Motors email test",
            "text": (
                "This is a test of Carvion Motors "
                "password-reset email delivery."
            ),
        })

        current_app.logger.info(
            "Resend test response: %s",
            response,
        )

        return (
            "Resend accepted the test email. "
            "Check your inbox and spam folder."
        )

    except Exception:
        current_app.logger.exception(
            "Resend test email failed."
        )
        return (
            "Resend rejected the test email. Check Render logs.",
            500,
        )


# ----------------------------------------------------------------------
# SELLER CONTACT SETTINGS
# ----------------------------------------------------------------------

@auth.route("/seller/contact-settings", methods=["GET", "POST"])
@login_required
def seller_contact_settings():
    if (
        (getattr(current_user, "role", "") or "").lower()
        != "seller"
    ):
        flash(
            "Only sellers can change contact preferences.",
            "warning",
        )
        return redirect(url_for("home"))

    if request.method == "POST":
        current_user.allow_phone_contact = (
            "allow_phone_contact" in request.form
        )

        current_user.allow_whatsapp_contact = (
            "allow_whatsapp_contact" in request.form
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Failed to save seller contact preferences."
            )
            flash(
                "Could not save your settings. Please try again.",
                "danger",
            )
            return redirect(
                url_for("auth.seller_contact_settings")
            )

        flash(
            "Contact preferences updated successfully.",
            "success",
        )

        return redirect(
            url_for("auth.seller_contact_settings")
        )

    return render_template(
        "seller_contact_settings.html",
        user=current_user,
    )
