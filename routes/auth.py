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

import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


auth = Blueprint(
    "auth",
    __name__
)


# ============================================================
# PASSWORD RESET HELPERS
# ============================================================

def generate_reset_token(email):
    """
    Generate a secure password reset token.
    """

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    return serializer.dumps(
        email,
        salt="carvion-password-reset"
    )


def verify_reset_token(token, max_age=3600):
    """
    Verify password reset token.

    max_age=3600 means the token expires after 1 hour.
    """

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

    except SignatureExpired:
        return None

    except BadSignature:
        return None


# ============================================================
# SEND PASSWORD RESET EMAIL
# ============================================================

def send_reset_email(user, reset_url):

    smtp_server = os.environ.get(
        "MAIL_SERVER"
    )

    smtp_port = int(
        os.environ.get(
            "MAIL_PORT",
            587
        )
    )

    smtp_username = os.environ.get(
        "MAIL_USERNAME"
    )

    smtp_password = os.environ.get(
        "MAIL_PASSWORD"
    )

    mail_sender = os.environ.get(
        "MAIL_DEFAULT_SENDER"
    )

    # --------------------------------------------------------
    # CHECK EMAIL CONFIGURATION
    # --------------------------------------------------------

    if not smtp_server or not smtp_username or not smtp_password:

        print("=" * 60)
        print("PASSWORD RESET EMAIL CONFIGURATION MISSING")
        print("MAIL_SERVER:", smtp_server)
        print("MAIL_USERNAME:", smtp_username)
        print("=" * 60)

        return False

    if not mail_sender:
        mail_sender = smtp_username

    # --------------------------------------------------------
    # EMAIL CONTENT
    # --------------------------------------------------------

    subject = "Carvion Motors - Password Reset"

    body = f"""
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

    # --------------------------------------------------------
    # CREATE EMAIL
    # --------------------------------------------------------

    message = MIMEMultipart()

    message["From"] = mail_sender
    message["To"] = user.email
    message["Subject"] = subject

    message.attach(
        MIMEText(
            body,
            "plain"
        )
    )

    # --------------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------------

    try:

        with smtplib.SMTP(
            smtp_server,
            smtp_port
        ) as server:

            server.starttls()

            server.login(
                smtp_username,
                smtp_password
            )

            server.sendmail(
                mail_sender,
                user.email,
                message.as_string()
            )

        return True

    except Exception as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print(str(e))
        print("=" * 60)

        return False


# ============================================================
# REGISTER
# ============================================================

@auth.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if current_user.is_authenticated:
        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role"
        )

        # ----------------------------------------------------
        # ONLY BUYER AND SELLER CAN REGISTER
        # ----------------------------------------------------

        if role not in [
            "buyer",
            "seller"
        ]:
            role = "buyer"

        # ----------------------------------------------------
        # BASIC VALIDATION
        # ----------------------------------------------------

        if not name or not email or not phone or not password:

            flash(
                "Please fill in all required fields.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        # ----------------------------------------------------
        # CHECK EXISTING USER
        # ----------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already exists.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        user = User(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(
                password
            ),
            role=role
        )

        db.session.add(user)
        db.session.commit()

        login_user(user)

        flash(
            "Account created successfully.",
            "success"
        )

        # ----------------------------------------------------
        # SELLER
        # ----------------------------------------------------

        if user.role == "seller":

            return redirect(
                url_for(
                    "cars.seller_dashboard"
                )
            )

        # ----------------------------------------------------
        # BUYER
        # ----------------------------------------------------

        return redirect(
            url_for("home")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@auth.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            flash(
                "Login successful.",
                "success"
            )

            role = user.role.lower()

            # ------------------------------------------------
            # ADMIN
            # ------------------------------------------------

            if role == "admin":

                return redirect(
                    url_for(
                        "admin.dashboard"
                    )
                )

            # ------------------------------------------------
            # SELLER
            # ------------------------------------------------

            elif role == "seller":

                return redirect(
                    url_for(
                        "cars.seller_dashboard"
                    )
                )

            # ------------------------------------------------
            # BUYER
            # ------------------------------------------------

            else:

                return redirect(
                    url_for("home")
                )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if current_user.is_authenticated:

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        user = User.query.filter_by(
            email=email
        ).first()

        # ----------------------------------------------------
        # ALWAYS SHOW SAME MESSAGE
        # ----------------------------------------------------
        # This prevents people from discovering which
        # email addresses have accounts.

        if user:

            token = generate_reset_token(
                user.email
            )

            reset_url = url_for(
                "auth.reset_password",
                token=token,
                _external=True
            )

            sent = send_reset_email(
                user,
                reset_url
            )

            if not sent:

                print("=" * 60)
                print("PASSWORD RESET LINK")
                print(reset_url)
                print("=" * 60)

        flash(
            "If an account exists for that email, "
            "a password reset link has been sent.",
            "info"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "forgot_password.html"
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    email = verify_reset_token(
        token
    )

    if not email:

        flash(
            "The password reset link is invalid or has expired.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:

        flash(
            "Account not found.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # ----------------------------------------------------
        # VALIDATE PASSWORD
        # ----------------------------------------------------

        if not password:

            flash(
                "Please enter a new password.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token
                )
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token
                )
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token
                )
            )

        # ----------------------------------------------------
        # UPDATE PASSWORD
        # ----------------------------------------------------

        user.password = generate_password_hash(
            password
        )

        db.session.commit()

        flash(
            "Your password has been reset successfully. "
            "You can now log in.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "reset_password.html",
        token=token
    )


# ============================================================
# LOGOUT
# ============================================================

@auth.route(
    "/logout"
)
@login_required
def logout():

    logout_user()

    flash(
        "Logged out successfully.",
        "info"
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# PROFILE
# ============================================================

@auth.route(
    "/profile"
)
@login_required
def profile():

    return render_template(
        "profile.html",
        user=current_user
    )


# ============================================================
# FORCE LOGOUT
# ============================================================

@auth.route(
    "/force_logout"
)
def force_logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )