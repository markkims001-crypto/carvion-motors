
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

import os
import socket
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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

    except SignatureExpired:

        return None

    except BadSignature:

        return None


# ============================================================
# SEND PASSWORD RESET EMAIL
# ============================================================

def send_reset_email(user, reset_url):

    smtp_server = os.environ.get(
        "MAIL_SERVER",
        ""
    ).strip()

    smtp_port_raw = os.environ.get(
        "MAIL_PORT",
        "587"
    ).strip()

    smtp_username = os.environ.get(
        "MAIL_USERNAME",
        ""
    ).strip()

    smtp_password = os.environ.get(
        "MAIL_PASSWORD",
        ""
    ).strip()

    mail_sender = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        ""
    ).strip()


    # --------------------------------------------------------
    # VALIDATE PORT
    # --------------------------------------------------------

    try:

        smtp_port = int(smtp_port_raw)

    except ValueError:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("MAIL_PORT must be a number.")
        print("Current MAIL_PORT:", smtp_port_raw)
        print("=" * 60)

        return False


    # --------------------------------------------------------
    # VALIDATE SMTP SETTINGS
    # --------------------------------------------------------

    if not smtp_server:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("MAIL_SERVER is missing.")
        print("=" * 60)

        return False


    if not smtp_username:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("MAIL_USERNAME is missing.")
        print("=" * 60)

        return False


    if not smtp_password:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("MAIL_PASSWORD is missing.")
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
    # CREATE EMAIL MESSAGE
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


    server = None


    # --------------------------------------------------------
    # CONNECT AND SEND
    # --------------------------------------------------------

    try:

        print("=" * 60)
        print("PASSWORD RESET EMAIL")
        print("Connecting to SMTP server...")
        print("SMTP SERVER:", smtp_server)
        print("SMTP PORT:", smtp_port)
        print("=" * 60)


        # IMPORTANT:
        # Timeout prevents the Render worker from hanging
        # indefinitely while connecting to the SMTP server.

        server = smtplib.SMTP(
            host=smtp_server,
            port=smtp_port,
            timeout=10
        )


        # SMTP handshake

        server.ehlo()


        # Start encrypted connection

        server.starttls()

        server.ehlo()


        # Authenticate

        server.login(
            smtp_username,
            smtp_password
        )


        # Send email

        server.sendmail(
            mail_sender,
            user.email,
            message.as_string()
        )


        print("=" * 60)
        print("PASSWORD RESET EMAIL SENT SUCCESSFULLY")
        print("Recipient:", user.email)
        print("=" * 60)

        return True


    except smtplib.SMTPAuthenticationError as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("SMTP AUTHENTICATION FAILED")
        print("Check your MAIL_USERNAME and MAIL_PASSWORD.")
        print("Error:", str(e))
        print("=" * 60)

        return False


    except smtplib.SMTPConnectError as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("SMTP CONNECTION FAILED")
        print("Could not connect to the mail server.")
        print("Error:", str(e))
        print("=" * 60)

        return False


    except (TimeoutError, socket.timeout) as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("SMTP CONNECTION TIMED OUT")
        print("The SMTP server could not be reached within 10 seconds.")
        print("Error:", str(e))
        print("=" * 60)

        return False


    except OSError as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("NETWORK ERROR")
        print("Error:", str(e))
        print("=" * 60)

        return False


    except Exception as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
        print("=" * 60)

        return False


    finally:

        if server is not None:

            try:

                server.quit()

            except Exception:

                pass


# ============================================================
# REGISTER
# ============================================================

@auth.route("/register", methods=["GET", "POST"])
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

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not name:

            flash(
                "Please enter your name.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )


        if not email:

            flash(
                "Please enter your email.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )


        if not password:

            flash(
                "Please enter a password.",
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


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )


        # ----------------------------------------------------
        # CHECK EXISTING ACCOUNT
        # ----------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()


        if existing_user:

            flash(
                "An account with that email already exists.",
                "warning"
            )

            return redirect(
                url_for("auth.login")
            )


        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )


        # Buyers are the default role.

        if hasattr(user, "role"):

            user.role = "buyer"


        db.session.add(user)


        try:

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print("=" * 60)
            print("REGISTRATION ERROR")
            print("ERROR TYPE:", type(e).__name__)
            print("ERROR:", str(e))
            print("=" * 60)

            flash(
                "Something went wrong while creating your account.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )


        flash(
            "Account created successfully. You can now log in.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )


    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@auth.route("/login", methods=["GET", "POST"])
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


        if not email or not password:

            flash(
                "Please enter your email and password.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        user = User.query.filter_by(
            email=email
        ).first()


        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)


            # ------------------------------------------------
            # ROLE REDIRECTION
            # ------------------------------------------------

            if getattr(
                user,
                "role",
                "buyer"
            ) == "admin":

                return redirect(
                    url_for("admin.dashboard")
                )


            if getattr(
                user,
                "role",
                "buyer"
            ) == "seller":

                return redirect(
                    url_for("cars.seller_dashboard")
                )


            return redirect(
                url_for("home")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    return render_template(
        "login.html"
    )


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

    return redirect(
        url_for("auth.login")
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


        if email:

            user = User.query.filter_by(
                email=email
            ).first()


            if user:

                # --------------------------------------------
                # GENERATE RESET TOKEN
                # --------------------------------------------

                try:

                    token = generate_reset_token(
                        user.email
                    )

                except Exception as e:

                    print("=" * 60)
                    print("PASSWORD RESET TOKEN ERROR")
                    print("ERROR TYPE:", type(e).__name__)
                    print("ERROR:", str(e))
                    print("=" * 60)

                    flash(
                        "Unable to create the password reset link.",
                        "danger"
                    )

                    return redirect(
                        url_for("auth.forgot_password")
                    )


                # --------------------------------------------
                # CREATE RESET URL
                # --------------------------------------------

                try:

                    reset_url = url_for(
                        "auth.reset_password",
                        token=token,
                        _external=True
                    )

                except Exception as e:

                    print("=" * 60)
                    print("PASSWORD RESET URL ERROR")
                    print("ERROR TYPE:", type(e).__name__)
                    print("ERROR:", str(e))
                    print("=" * 60)

                    flash(
                        "Unable to create the password reset link.",
                        "danger"
                    )

                    return redirect(
                        url_for("auth.forgot_password")
                    )


                # --------------------------------------------
                # SEND RESET EMAIL
                # --------------------------------------------

                try:

                    sent = send_reset_email(
                        user,
                        reset_url
                    )

                except Exception as e:

                    print("=" * 60)
                    print("UNEXPECTED PASSWORD RESET ERROR")
                    print("ERROR TYPE:", type(e).__name__)
                    print("ERROR:", str(e))
                    print("=" * 60)

                    sent = False


                if not sent:

                    print("=" * 60)
                    print("PASSWORD RESET EMAIL WAS NOT SENT")
                    print("Recipient:", user.email)
                    print("=" * 60)


        # ----------------------------------------------------
        # SECURITY:
        # Do not reveal whether an email exists.
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # VERIFY TOKEN
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # FIND USER
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # PROCESS NEW PASSWORD
    # --------------------------------------------------------

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


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
        # SAVE PASSWORD
        # ----------------------------------------------------

        try:

            user.password = generate_password_hash(
                password
            )

            db.session.commit()


        except Exception as e:

            db.session.rollback()

            print("=" * 60)
            print("PASSWORD RESET DATABASE ERROR")
            print("ERROR TYPE:", type(e).__name__)
            print("ERROR:", str(e))
            print("=" * 60)

            flash(
                "Something went wrong while resetting your password.",
                "danger"
            )

            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token
                )
            )


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

    return redirect(
        url_for("auth.login")
    )
