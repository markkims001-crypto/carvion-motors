
# routes/auth.py

from datetime import datetime, timedelta
import os
import re
import secrets
import time

import africastalking

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    session,
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired,
)

from extensions import db
from models import User, PasswordResetCode


auth = Blueprint("auth", __name__)


# ============================================================
# LEGACY EMAIL RESET TOKENS
# ============================================================

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )
    return serializer.dumps(email, salt="carvion-password-reset")


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


# ============================================================
# PHONE HELPERS
# ============================================================

def normalize_kenyan_phone(phone):
    digits = re.sub(r"\D", "", phone or "")

    if digits.startswith("254") and len(digits) == 12:
        normalized = "+" + digits
    elif digits.startswith("0") and len(digits) == 10:
        normalized = "+254" + digits[1:]
    elif len(digits) == 9 and digits[0] in ("7", "1"):
        normalized = "+254" + digits
    else:
        return None

    if not re.fullmatch(r"\+254[17]\d{8}", normalized):
        return None

    return normalized


def phone_lookup_variants(normalized_phone):
    national_number = normalized_phone[4:]

    return [
        normalized_phone,
        normalized_phone[1:],
        "0" + national_number,
        national_number,
    ]


# ============================================================
# AFRICA'S TALKING SMS
# ============================================================

def send_reset_sms(phone, code):
    username = os.environ.get("AT_USERNAME", "").strip()
    api_key = os.environ.get("AT_API_KEY", "").strip()
    sender_id = os.environ.get("AT_SENDER_ID", "").strip()

    if not username or not api_key:
        current_app.logger.error(
            "Missing AT_USERNAME or AT_API_KEY."
        )
        return False

    message = (
        f"Your Carvion Motors password reset code is {code}. "
        "It expires in 10 minutes. Do not share this code."
    )

    try:
        africastalking.initialize(username, api_key)

        if sender_id:
            response = africastalking.SMS.send(
                message, [phone], sender_id=sender_id
            )
        else:
            response = africastalking.SMS.send(message, [phone])

        # The SDK response should contain a response object.
        # Delivery to the handset must still be tested separately.
        return bool(response)

    except Exception:
        current_app.logger.exception("SMS sending failed.")
        return False


# ============================================================
# REGISTER
# ============================================================

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
        role = request.form.get("role", "buyer").strip().lower()

        if not name or not email or not phone or not password:
            flash("Please complete all required fields.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        if role not in ("buyer", "seller"):
            flash("Please select a valid account type.", "danger")
            return redirect(url_for("auth.register"))

        try:
            existing_user = User.query.filter_by(email=email).first()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Registration account lookup failed."
            )
            flash("Unable to process registration. Try again.", "danger")
            return redirect(url_for("auth.register"))

        if existing_user:
            flash(
                "An account with that email already exists.",
                "warning",
            )
            return redirect(url_for("auth.login"))

        try:
            user = User(
                name=name,
                email=email,
                phone=phone,
                password=generate_password_hash(password),
                role=role,
            )
            db.session.add(user)
            db.session.commit()

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Registration failed.")
            flash(
                "Unable to create your account. Please try again.",
                "danger",
            )
            return redirect(url_for("auth.register"))

        flash(
            f"{role.capitalize()} account created successfully. "
            "You can now log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "danger")
            return redirect(url_for("auth.login"))

        try:
            user = User.query.filter_by(email=email).first()
        except Exception:
            current_app.logger.exception("Login lookup failed.")
            flash("Unable to log in right now. Try again.", "danger")
            return redirect(url_for("auth.login"))

        if user and check_password_hash(user.password, password):
            login_user(user)

            role = (
                getattr(user, "role", "buyer") or "buyer"
            ).strip().lower()

            if role == "admin":
                return redirect(url_for("admin.dashboard"))
            if role == "seller":
                return redirect(url_for("cars.seller_dashboard"))
            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ============================================================
# FORGOT PASSWORD - REQUEST SMS CODE
# ============================================================

@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        phone = normalize_kenyan_phone(
            request.form.get("phone", "")
        )

        session.pop("password_reset_pending_user_id", None)
        session.pop("password_reset_verified_user_id", None)
        session.pop("password_reset_verified_at", None)

        if phone:
            try:
                user = User.query.filter(
                    User.phone.in_(phone_lookup_variants(phone))
                ).first()

                if user:
                    now = datetime.utcnow()

                    # Rate-limit requests per account.
                    latest = (
                        PasswordResetCode.query
                        .filter_by(user_id=user.id)
                        .order_by(
                            PasswordResetCode.created_at.desc()
                        )
                        .first()
                    )

                    if (
                        latest
                        and latest.created_at
                        > now - timedelta(seconds=60)
                    ):
                        # Do not create a fresh code or resend SMS.
                        flash(
                            "Please wait before requesting another code.",
                            "info",
                        )
                        return redirect(
                            url_for("auth.forgot_password")
                        )

                    # Delete older codes before issuing a new code.
                    PasswordResetCode.query.filter_by(
                        user_id=user.id
                    ).delete(synchronize_session=False)

                    code = f"{secrets.randbelow(1_000_000):06d}"

                    record = PasswordResetCode(
                        user_id=user.id,
                        code_hash=generate_password_hash(code),
                        expires_at=now + timedelta(minutes=10),
                        attempts=0,
                    )

                    db.session.add(record)
                    db.session.commit()

                    if send_reset_sms(phone, code):
                        session["password_reset_pending_user_id"] = user.id
                    else:
                        db.session.delete(record)
                        db.session.commit()

            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Forgot-password SMS request failed."
                )

        flash(
            "If an account matches that phone number, a verification "
            "code has been sent. Check your number and try again shortly "
            "if no code arrives.",
            "info",
        )
        return redirect(url_for("auth.verify_reset_code"))

    return render_template("forgot_password.html")


# ============================================================
# VERIFY SMS CODE
# ============================================================

@auth.route("/verify-reset-code", methods=["GET", "POST"])
def verify_reset_code():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        user_id = session.get("password_reset_pending_user_id")
        code = request.form.get("code", "").strip()

        if not user_id or not re.fullmatch(r"\d{6}", code):
            flash("Invalid or expired code. Request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))

        try:
            record = (
                PasswordResetCode.query
                .filter_by(user_id=user_id)
                .order_by(PasswordResetCode.created_at.desc())
                .first()
            )

            if not record:
                flash("Invalid or expired code. Request a new one.", "danger")
                return redirect(url_for("auth.forgot_password"))

            if record.expires_at <= datetime.utcnow():
                PasswordResetCode.query.filter_by(
                    user_id=user_id
                ).delete(synchronize_session=False)
                db.session.commit()
                session.pop("password_reset_pending_user_id", None)
                flash("Your code expired. Request a new one.", "danger")
                return redirect(url_for("auth.forgot_password"))

            if record.attempts >= 5:
                PasswordResetCode.query.filter_by(
                    user_id=user_id
                ).delete(synchronize_session=False)
                db.session.commit()
                session.pop("password_reset_pending_user_id", None)
                flash("Too many attempts. Request a new code.", "danger")
                return redirect(url_for("auth.forgot_password"))

            if not check_password_hash(record.code_hash, code):
                record.attempts += 1
                db.session.commit()

                remaining = 5 - record.attempts
                if remaining <= 0:
                    PasswordResetCode.query.filter_by(
                        user_id=user_id
                    ).delete(synchronize_session=False)
                    db.session.commit()
                    session.pop("password_reset_pending_user_id", None)
                    flash(
                        "Too many attempts. Request a new code.",
                        "danger",
                    )
                    return redirect(url_for("auth.forgot_password"))

                flash(
                    f"Incorrect code. {remaining} attempt(s) remaining.",
                    "danger",
                )
                return redirect(url_for("auth.verify_reset_code"))

            # Consume the code before permitting a password change.
            verified_user_id = record.user_id
            PasswordResetCode.query.filter_by(
                user_id=verified_user_id
            ).delete(synchronize_session=False)
            db.session.commit()

            session.pop("password_reset_pending_user_id", None)
            session["password_reset_verified_user_id"] = verified_user_id
            session["password_reset_verified_at"] = int(time.time())

            return redirect(url_for("auth.reset_password_sms"))

        except Exception:
            db.session.rollback()
            current_app.logger.exception("OTP verification failed.")
            flash("Unable to verify the code. Please try again.", "danger")
            return redirect(url_for("auth.forgot_password"))

    return render_template("verify_reset_code.html")


# ============================================================
# RESET PASSWORD AFTER VERIFIED SMS
# ============================================================

@auth.route("/reset-password-sms", methods=["GET", "POST"])
def reset_password_sms():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    user_id = session.get("password_reset_verified_user_id")
    verified_at = session.get("password_reset_verified_at")

    if (
        not user_id
        or not verified_at
        or time.time() - verified_at > 600
    ):
        session.pop("password_reset_verified_user_id", None)
        session.pop("password_reset_verified_at", None)
        flash("Your reset session expired. Please start again.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, user_id)

    if not user:
        session.pop("password_reset_verified_user_id", None)
        session.pop("password_reset_verified_at", None)
        flash("Unable to reset this account. Please try again.", "danger")
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
            current_app.logger.exception("Password update failed.")
            flash("Unable to update your password. Try again.", "danger")
            return redirect(url_for("auth.reset_password_sms"))

        session.pop("password_reset_verified_user_id", None)
        session.pop("password_reset_verified_at", None)

        flash(
            "Your password has been reset successfully. You can now log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("reset_password_sms.html")


# ============================================================
# LEGACY EMAIL RESET ROUTE
# ============================================================

@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)

    if not email:
        flash(
            "The password reset link is invalid or has expired.",
            "danger",
        )
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.forgot_password"))

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
            current_app.logger.exception(
                "Legacy password reset failed."
            )
            flash("Unable to reset your password. Please try again.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        flash(
            "Your password has been reset successfully. You can now log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


# ============================================================
# PROFILE
# ============================================================

@auth.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


# ============================================================
# FORCE LOGOUT
# ============================================================

@auth.route("/force-logout")
def force_logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
