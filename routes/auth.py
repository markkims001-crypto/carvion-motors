from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
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

from extensions import db
from models import User


auth = Blueprint(
    "auth",
    __name__
)


# =====================================
# REGISTER
# =====================================

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

        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")

        role = request.form.get("role")


        # Only buyer and seller can register
        if role not in [
            "buyer",
            "seller"
        ]:
            role = "buyer"



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



        if user.role == "seller":

            return redirect(
                url_for(
                    "cars.seller_dashboard"
                )
            )



        return redirect(
            url_for("home")
        )



    return render_template(
        "register.html"
    )




# =====================================
# LOGIN
# =====================================

@auth.route(
    "/login",
    methods=["GET","POST"]
)
def login():


    if current_user.is_authenticated:

        return redirect(
            url_for("home")
        )



    if request.method == "POST":


        email = request.form.get(
            "email"
        )

        password = request.form.get(
            "password"
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



            # ADMIN

            if role == "admin":

                return redirect(
                    url_for(
                        "admin.dashboard"
                    )
                )



            # SELLER

            elif role == "seller":

                return redirect(
                    url_for(
                        "cars.seller_dashboard"
                    )
                )



            # BUYER

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





# =====================================
# LOGOUT
# =====================================

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





# =====================================
# PROFILE
# =====================================

@auth.route(
    "/profile"
)
@login_required
def profile():

    return render_template(
        "profile.html",
        user=current_user
    )





# =====================================
# FORCE LOGOUT
# =====================================

@auth.route(
    "/force_logout"
)
def force_logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )