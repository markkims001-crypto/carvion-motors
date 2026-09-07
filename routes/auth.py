
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

    except SignatureExpired:

        return None

    except BadSignature:

        return None


# ============================================================
# SEND PASSWORD RESET EMAIL USING RESEND API
# ============================================================

def send_reset_email(user, reset_url):

    if resend is None:

        print("PASSWORD RESET EMAIL ERROR: resend package is not installed.")

        return False

    # --------------------------------------------------------
    # GET RESEND API KEY
    # --------------------------------------------------------

    resend_api_key = os.environ.get(
        "RESEND_API_KEY",
        ""
    ).strip()


    # --------------------------------------------------------
    # GET SENDER EMAIL
    # --------------------------------------------------------

    resend_from_email = os.environ.get(
        "RESEND_FROM_EMAIL",
        ""
    ).strip()


    # --------------------------------------------------------
    # CHECK API KEY
    # --------------------------------------------------------

    if not resend_api_key:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("RESEND_API_KEY is missing.")
        print("=" * 60)

        return False


    # --------------------------------------------------------
    # CHECK SENDER
    # --------------------------------------------------------

    if not resend_from_email:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("RESEND_FROM_EMAIL is missing.")
        print("=" * 60)

        return False


    # --------------------------------------------------------
    # SET RESEND API KEY
    # --------------------------------------------------------

    resend.api_key = resend_api_key


    # --------------------------------------------------------
    # EMAIL SUBJECT
    # --------------------------------------------------------

    subject = "Carvion Motors - Password Reset"


    # --------------------------------------------------------
    # PLAIN TEXT EMAIL
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # HTML EMAIL
    # --------------------------------------------------------

    html_body = f"""
<!DOCTYPE html>

<html>

<head>

    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>
        Carvion Motors Password Reset
    </title>

</head>


<body
    style="
        margin: 0;
        padding: 0;
        background-color: #f4f4f4;
        font-family: Arial, Helvetica, sans-serif;
    "
>


    <div
        style="
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 3px 15px rgba(0,0,0,0.08);
        "
    >


        <!-- HEADER -->

        <div
            style="
                background: #111111;
                color: #ffffff;
                padding: 25px;
                text-align: center;
            "
        >

            <h1
                style="
                    margin: 0;
                    font-size: 28px;
                "
            >
                Carvion Motors
            </h1>

            <p
                style="
                    margin: 8px 0 0;
                    color: #cccccc;
                "
            >
                Password Reset
            </p>

        </div>


        <!-- CONTENT -->

        <div
            style="
                padding: 35px 30px;
                color: #333333;
            "
        >

            <h2>
                Hello {user.name},
            </h2>


            <p
                style="
                    font-size: 16px;
                    line-height: 1.6;
                "
            >
                We received a request to reset your
                Carvion Motors account password.
            </p>


            <p
                style="
                    font-size: 16px;
                    line-height: 1.6;
                "
            >
                Click the button below to create a new password:
            </p>


            <div
                style="
                    text-align: center;
                    margin: 30px 0;
                "
            >

                <a
                    href="{reset_url}"
                    style="
                        display: inline-block;
                        background: #111111;
                        color: #ffffff;
                        text-decoration: none;
                        padding: 14px 28px;
                        border-radius: 6px;
                        font-weight: bold;
                        font-size: 16px;
                    "
                >
                    Reset My Password
                </a>

            </div>


            <p
                style="
                    font-size: 14px;
                    line-height: 1.6;
                    color: #666666;
                "
            >
                This password reset link will expire in
                <strong>1 hour</strong>.
            </p>


            <p
                style="
                    font-size: 14px;
                    line-height: 1.6;
                    color: #666666;
                "
            >
                If you did not request a password reset,
                you can safely ignore this email.
            </p>


        </div>


        <!-- FOOTER -->

        <div
            style="
                background: #f7f7f7;
                padding: 20px;
                text-align: center;
                color: #777777;
                font-size: 13px;
            "
        >

            <p style="margin: 0;">
                Carvion Motors
            </p>

            <p style="margin: 6px 0 0;">
                Your trusted automotive marketplace
            </p>

        </div>


    </div>

</body>

</html>
"""


    # --------------------------------------------------------
    # SEND THROUGH RESEND
    # --------------------------------------------------------

    try:

        print("=" * 60)
        print("PASSWORD RESET EMAIL")
        print("Using Resend Email API")
        print("Recipient:", user.email)
        print("Sender:", resend_from_email)
        print("=" * 60)


        params = {
            "from": resend_from_email,

            "to": [
                user.email
            ],

            "subject": subject,

            "html": html_body,

            "text": text_body
        }


        response = resend.Emails.send(
            params
        )


        print("=" * 60)
        print("PASSWORD RESET EMAIL SENT")
        print("Resend response:", response)
        print("=" * 60)


        return True


    except Exception as e:

        print("=" * 60)
        print("PASSWORD RESET EMAIL ERROR")
        print("RESEND API ERROR")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
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
        # CHECK EXISTING USER
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


        # Default role

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
            # ADMIN
            # ------------------------------------------------

            if getattr(
                user,
                "role",
                "buyer"
            ) == "admin":

                return redirect(
                    url_for("admin.dashboard")
                )


            # ------------------------------------------------
            # SELLER
            # ------------------------------------------------

            if getattr(
                user,
                "role",
                "buyer"
            ) == "seller":

                return redirect(
                    url_for("cars.seller_dashboard")
                )


            # ------------------------------------------------
            # BUYER
            # ------------------------------------------------

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
                # CREATE TOKEN
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
                # SEND EMAIL
                # --------------------------------------------

                sent = send_reset_email(
                    user,
                    reset_url
                )


                if not sent:

                    print("=" * 60)
                    print("PASSWORD RESET EMAIL WAS NOT SENT")
                    print("Recipient:", user.email)
                    print("=" * 60)


        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------
        # Do not reveal whether the email exists.

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
    # NEW PASSWORD
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

