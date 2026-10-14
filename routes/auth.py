
# routes/auth.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired
)

from extensions import db
from models import User

import importlib
import os


try:
    resend = importlib.import_module("resend")
except ImportError:
    resend = None


# ============================================================
# BLUEPRINT
# ============================================================

auth = Blueprint("auth", __name__)


# ============================================================
# PASSWORD RESET TOKEN
# ============================================================

def generate_reset_token(email):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    return serializer.dumps(
        email,
        salt="carvion-password-reset"
    )


def verify_reset_token(token, max_age=3600):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    try:
        email = serializer.loads(
            token,
            salt="carvion-password-reset",
            max_age=max_age
        )

        return email

    except (SignatureExpired, BadSignature):

        return None


# ============================================================
# SEND PASSWORD RESET EMAIL USING RESEND API
# ============================================================

def send_reset_email(user, reset_url):

    if resend is None:
        current_app.logger.error(
            "Password reset email error: "
            "resend package is not installed."
        )
        return False

    resend_api_key = os.environ.get(
        "RESEND_API_KEY", ""
    ).strip()

    resend_from_email = os.environ.get(
        "RESEND_FROM_EMAIL", ""
    ).strip()

    if not resend_api_key:
        current_app.logger.error(
            "Password reset email error: "
            "RESEND_API_KEY is missing."
        )
        return False

    if not resend_from_email:
        current_app.logger.error(
            "Password reset email error: "
            "RESEND_FROM_EMAIL is missing."
        )
        return False

    resend.api_key = resend_api_key

    subject = "Carvion Motors - Password Reset"

    text_body = f"""
Hello {user.name},

We received a request to reset your Carvion Motors password.

Click the link below to create a new password:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, you can safely ignore
this email.

Regards,

Carvion Motors
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">
    <title>Carvion Motors Password Reset</title>
</head>

<body style="
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
    font-family: Arial, Helvetica, sans-serif;
">

    <div style="
        max-width: 600px;
        margin: 40px auto;
        background: #ffffff;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 3px 15px rgba(0,0,0,0.08);
    ">

        <div style="
            background: #111111;
            color: #ffffff;
            padding: 25px;
            text-align: center;
        ">
            <h1 style="margin: 0; font-size: 28px;">
                Carvion Motors
            </h1>

            <p style="margin: 8px 0 0; color: #cccccc;">
                Password Reset
            </p>
        </div>

        <div style="padding: 35px 30px; color: #333333;">

            <h2>Hello {user.name},</h2>

            <p style="font-size: 16px; line-height: 1.6;">
                We received a request to reset your
                Carvion Motors account password.
            </p>

            <p style="font-size: 16px; line-height: 1.6;">
                Click the button below to create a new password:
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="
                    display: inline-block;
                    background: #111111;
                    color: #ffffff;
                    text-decoration: none;
                    padding: 14px 28px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 16px;
                ">
                    Reset My Password
                </a>
            </div>

            <p style="
                font-size: 14px;
                line-height: 1.6;
                color: #666666;
            ">
                This password reset link will expire in
                <strong>1 hour</strong>.
            </p>

            <p style="
                font-size: 14px;
                line-height: 1.6;
                color: #666666;
            ">
                If you did not request a password reset,
                you can safely ignore this email.
            </p>

        </div>

        <div style="
            background: #f7f7f7;
            padding: 20px;
            text-align: center;
            color: #777777;
            font-size: 13px;
        ">
            <p style="margin: 0;">Carvion Motors</p>

            <p style="margin: 6px 0 0;">
                Your trusted automotive marketplace
            </p>
        </div>

    </div>

</body>
</html>
"""

    try:
        params = {
            "from": resend_from_email,
            "to": [user.email],
            "subject": subject,
            "html": html_body,
            "text": text_body
        }

        response = resend.Emails.send(params)

        current_app.logger.info(
            "Password reset email submitted to Resend for %s",
            user.email
        )

        return bool(response)

    except Exception:
        current_app.logger.exception(
            "Password reset email could not be sent."
        )
        return False


# ============================================================
# REGISTER
# ============================================================

@auth.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        # Collect form data.
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        # Default to buyer if the role field is missing.
        role = request.form.get(
            "role", "buyer"
        ).strip().lower()

        # Validate required fields.
        if not name:
            flash("Please enter your name.", "danger")
            return redirect(url_for("auth.register"))

        if not email:
            flash("Please enter your email.", "danger")
            return redirect(url_for("auth.register"))

        if not phone:
            flash("Please enter your phone number.", "danger")
            return redirect(url_for("auth.register"))

        if not password:
            flash("Please enter a password.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash(
                "Password must be at least 6 characters.",
                "danger"
            )
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        # Only public buyer and seller roles are permitted.
        if role not in ("buyer", "seller"):
            flash(
                "Please select a valid account type.",
                "danger"
            )
            return redirect(url_for("auth.register"))

        # Check for an existing account.
        try:
            existing_user = User.query.filter_by(
                email=email
            ).first()

        except Exception:
            current_app.logger.exception(
                "Could not check for an existing user."
            )

            flash(
                "Unable to process your registration. "
                "Please try again.",
                "danger"
            )
            return redirect(url_for("auth.register"))

        if existing_user:
            flash(
                "An account with that email already exists.",
                "warning"
            )
            return redirect(url_for("auth.login"))

        # Create the account using the selected role.
        try:
            user = User(
                name=name,
                email=email,
                phone=phone,
                password=generate_password_hash(password),
                role=role
            )

            db.session.add(user)
            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Registration database error."
            )

            flash(
                "Something went wrong while creating your account. "
                "Please check your details and try again.",
                "danger"
            )
            return redirect(url_for("auth.register"))

        flash(
            f"{role.capitalize()} account created successfully. "
            "You can now log in.",
            "success"
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

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        if not email or not password:
            flash(
                "Please enter your email and password.",
                "danger"
            )
            return redirect(url_for("auth.login"))

        try:
            user = User.query.filter_by(
                email=email
            ).first()

        except Exception:
            current_app.logger.exception(
                "Login database lookup failed."
            )

            flash(
                "Unable to log in right now. Please try again.",
                "danger"
            )
            return redirect(url_for("auth.login"))

        if user and check_password_hash(
            user.password, password
        ):

            login_user(user)

            role = (
                getattr(user, "role", "buyer") or "buyer"
            ).strip().lower()

            if role == "admin":
                return redirect(
                    url_for("admin.dashboard")
                )

            if role == "seller":
                return redirect(
                    url_for("cars.seller_dashboard")
                )

            return redirect(url_for("home"))

        flash(
            "Invalid email or password.",
            "danger"
        )
        return redirect(url_for("auth.login"))

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@auth.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("auth.login"))


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        if email:

            try:
                user = User.query.filter_by(
                    email=email
                ).first()

            except Exception:
                current_app.logger.exception(
                    "Forgot-password database lookup failed."
                )
                user = None

            if user:

                try:
                    token = generate_reset_token(user.email)

                    reset_url = url_for(
                        "auth.reset_password",
                        token=token,
                        _external=True
                    )

                except Exception:
                    current_app.logger.exception(
                        "Password reset link creation failed."
                    )

                    flash(
                        "Unable to create the password reset link.",
                        "danger"
                    )
                    return redirect(
                        url_for("auth.forgot_password")
                    )

                sent = send_reset_email(user, reset_url)

                if not sent:
                    current_app.logger.error(
                        "Password reset email was not sent."
                    )

        # Do not disclose whether the account exists.
        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "info"
        )

        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


# ============================================================
# RESET PASSWORD
# ============================================================

@auth.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    email = verify_reset_token(token)

    if not email:
        flash(
            "The password reset link is invalid or has expired.",
            "danger"
        )
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not password:
            flash(
                "Please enter a new password.",
                "danger"
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        if len(password) < 6:
            flash(
                "Password must be at least 6 characters.",
                "danger"
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "danger"
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        try:
            user.password = generate_password_hash(password)
            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Password reset database update failed."
            )

            flash(
                "Something went wrong while resetting your password.",
                "danger"
            )
            return redirect(
                url_for("auth.reset_password", token=token)
            )

        flash(
            "Your password has been reset successfully. "
            "You can now log in.",
            "success"
        )

        return redirect(url_for("auth.login"))

    return render_template(
        "reset_password.html",
        token=token
    )


# ============================================================
# PROFILE
# ============================================================

@auth.route("/profile")
@login_required
def profile():

    return render_template(
        "profile.html",
        user=current_user
    )


# ============================================================
# FORCE LOGOUT
# ============================================================

@auth.route("/force-logout")
def force_logout():

    logout_user()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(url_for("auth.login"))
