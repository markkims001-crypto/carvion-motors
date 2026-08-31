
from flask import Flask, render_template, redirect, url_for
from flask_login import login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
import os

from config import Config
from extensions import db, login_manager
from models import (
    User,
    Car,
    Inquiry,
    Notification
)


# =====================================================
# CREATE APPLICATION
# =====================================================

def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)


    # =================================================
    # UPLOAD FOLDER
    # =================================================

    upload_folder = app.config.get("UPLOAD_FOLDER")

    if upload_folder:
        os.makedirs(
            upload_folder,
            exist_ok=True
        )


    # =================================================
    # EXTENSIONS
    # =================================================

    db.init_app(app)

    Migrate(
        app,
        db
    )

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"

    login_manager.login_message = (
        "Please log in first."
    )


    # =================================================
    # LOGIN MANAGER
    # =================================================

    @login_manager.user_loader
    def load_user(user_id):

        try:

            return db.session.get(
                User,
                int(user_id)
            )

        except (ValueError, TypeError):

            return None


    # =================================================
    # GLOBAL NOTIFICATION DATA
    # =================================================
    #
    # These variables are available in ALL templates.
    #
    # unread_notifications
    # unread_favorites
    # unread_compares
    # unread_inquiries
    # unread_vehicle_updates
    #
    # =================================================

    @app.context_processor
    def inject_notification_data():

        # -------------------------------------------------
        # LOGGED OUT USERS
        # -------------------------------------------------

        if not current_user.is_authenticated:

            return {
                "unread_notifications": 0,
                "unread_favorites": 0,
                "unread_compares": 0,
                "unread_inquiries": 0,
                "unread_vehicle_updates": 0
            }


        # -------------------------------------------------
        # GET UNREAD NOTIFICATIONS
        # -------------------------------------------------

        notifications = (
            Notification.query
            .filter_by(
                user_id=current_user.id,
                is_read=False
            )
            .all()
        )


        # -------------------------------------------------
        # TOTAL UNREAD
        # -------------------------------------------------

        unread_notifications = len(
            notifications
        )


        # -------------------------------------------------
        # FAVORITES
        # -------------------------------------------------

        unread_favorites = sum(
            1
            for notification in notifications
            if notification.notification_type == "favorite"
        )


        # -------------------------------------------------
        # COMPARE
        # -------------------------------------------------

        unread_compares = sum(
            1
            for notification in notifications
            if notification.notification_type == "compare"
        )


        # -------------------------------------------------
        # INQUIRIES
        # -------------------------------------------------

        unread_inquiries = sum(
            1
            for notification in notifications
            if notification.notification_type == "inquiry"
        )


        # -------------------------------------------------
        # VEHICLE UPDATES
        # -------------------------------------------------

        unread_vehicle_updates = sum(
            1
            for notification in notifications
            if notification.notification_type in [
                "vehicle",
                "approval",
                "rejection"
            ]
        )


        # -------------------------------------------------
        # SEND DATA TO ALL TEMPLATES
        # -------------------------------------------------

        return {
            "unread_notifications": unread_notifications,
            "unread_favorites": unread_favorites,
            "unread_compares": unread_compares,
            "unread_inquiries": unread_inquiries,
            "unread_vehicle_updates": unread_vehicle_updates
        }


    # =================================================
    # BLUEPRINTS
    # =================================================

    from routes.auth import auth
    from routes.cars import cars
    from routes.admin import admin
    from routes.messages import messages
    from routes.chat import chat


    app.register_blueprint(auth)

    app.register_blueprint(cars)

    app.register_blueprint(admin)

    app.register_blueprint(messages)

    app.register_blueprint(chat)


    # =================================================
    # DATABASE INITIALIZATION
    # =================================================

    with app.app_context():

        db.create_all()


        # -------------------------------------------------
        # DEFAULT ADMIN
        # -------------------------------------------------

        admin_user = User.query.filter_by(
            email="admin@carvion.com"
        ).first()


        if admin_user is None:

            admin_user = User(
                name="Carvion Admin",
                email="admin@carvion.com",
                phone="0700000000",
                password=generate_password_hash(
                    "admin123"
                ),
                role="admin"
            )


            db.session.add(
                admin_user
            )

            db.session.commit()


            print("=" * 50)

            print(
                "DEFAULT ADMIN CREATED"
            )

            print(
                "Email: admin@carvion.com"
            )

            print(
                "Password: admin123"
            )

            print("=" * 50)


    # =================================================
    # HOME
    # =================================================

    @app.route("/")
    def home():

        cars = (
            Car.query
            .filter_by(
                status="Approved"
            )
            .order_by(
                Car.created_at.desc()
            )
            .limit(6)
            .all()
        )


        return render_template(
            "index.html",
            cars=cars
        )


    # =================================================
    # DASHBOARD
    # =================================================

    @app.route("/dashboard")
    @login_required
    def dashboard():

        return render_template(
            "dashboard.html"
        )


    # =================================================
    # ABOUT
    # =================================================

    @app.route("/about")
    def about():

        return render_template(
            "about.html"
        )


    # =================================================
    # CONTACT
    # =================================================

    @app.route("/contact")
    def contact():

        return render_template(
            "contact.html"
        )


    # =================================================
    # BUYER HOME
    # =================================================

    @app.route("/buyer")
    @login_required
    def buyer_home():

        # -------------------------------------------------
        # ONLY BUYERS
        # -------------------------------------------------

        if current_user.role.lower() != "buyer":

            return redirect(
                url_for("home")
            )


        # -------------------------------------------------
        # BUYER INQUIRIES
        # -------------------------------------------------

        inquiries = (
            Inquiry.query
            .filter_by(
                buyer_id=current_user.id
            )
            .order_by(
                Inquiry.created_at.desc()
            )
            .all()
        )


        return render_template(
            "buyer_home.html",
            inquiries=inquiries
        )


    # =================================================
    # RETURN APPLICATION
    # =================================================

    return app


# =====================================================
# CREATE FLASK APPLICATION
# =====================================================

app = create_app()


print(
    "CARVION APP STARTED"
)


# =====================================================
# RUN FLASK DEVELOPMENT SERVER
# =====================================================

if __name__ == "__main__":

    print(
        "RUNNING FLASK SERVER"
    )

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )

