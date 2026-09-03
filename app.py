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
    InquiryMessage,
    Message,
    Notification
)


# ============================================================
# CREATE APPLICATION
# ============================================================

def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    # ========================================================
    # UPLOAD FOLDER
    # ========================================================

    upload_folder = app.config.get("UPLOAD_FOLDER")

    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # ========================================================
    # DATABASE
    # ========================================================

    db.init_app(app)

    # ========================================================
    # FLASK MIGRATE
    # ========================================================

    Migrate(app, db)

    # ========================================================
    # LOGIN
    # ========================================================

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in first."

    # ========================================================
    # LOGIN MANAGER
    # ========================================================

    @login_manager.user_loader
    def load_user(user_id):

        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    # ========================================================
    # GLOBAL HEADER COUNTS
    # ========================================================

    @app.context_processor
    def inject_notification_data():

        data = {
            "unread_notifications": 0,
            "unread_favorites": 0,
            "unread_compares": 0,
            "unread_inquiries": 0,
            "unread_vehicle_updates": 0,
            "unread_messages": 0
        }

        if not current_user.is_authenticated:
            return data

        # ====================================================
        # GENERAL NOTIFICATIONS
        # ====================================================

        notifications = (
            Notification.query
            .filter(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False)
            )
            .all()
        )

        data["unread_notifications"] = len(notifications)

        # ====================================================
        # FAVORITES
        # ====================================================

        data["unread_favorites"] = sum(
            1
            for notification in notifications
            if notification.notification_type == "favorite"
        )

        # ====================================================
        # COMPARE
        # ====================================================

        data["unread_compares"] = sum(
            1
            for notification in notifications
            if notification.notification_type == "compare"
        )

        # ====================================================
        # VEHICLE UPDATES
        # ====================================================

        data["unread_vehicle_updates"] = sum(
            1
            for notification in notifications
            if notification.notification_type in (
                "vehicle",
                "approval",
                "rejection"
            )
        )

        # ====================================================
        # INQUIRIES
        # ====================================================

        if current_user.role.lower() == "admin":

            data["unread_inquiries"] = (
                Notification.query
                .filter(
                    Notification.user_id == current_user.id,
                    Notification.notification_type == "inquiry",
                    Notification.is_read.is_(False)
                )
                .count()
            )

        else:

            data["unread_inquiries"] = (
                InquiryMessage.query
                .filter(
                    InquiryMessage.receiver_id == current_user.id,
                    InquiryMessage.is_read.is_(False)
                )
                .count()
            )

        # ====================================================
        # DIRECT CHAT MESSAGES
        # ====================================================

        data["unread_messages"] = (
            Message.query
            .filter(
                Message.receiver_id == current_user.id,
                Message.is_read.is_(False)
            )
            .count()
        )

        return data

    # ========================================================
    # BLUEPRINTS
    # ========================================================

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

    # ========================================================
    # DATABASE INITIALIZATION
    # ========================================================

    with app.app_context():

        try:

            # ------------------------------------------------
            # CREATE ALL TABLES
            # ------------------------------------------------

            db.create_all()

            print("=" * 60)
            print("DATABASE INITIALIZATION COMPLETE")
            print("=" * 60)

            # ------------------------------------------------
            # SHOW DATABASE TYPE
            # ------------------------------------------------

            database_url = app.config.get(
                "SQLALCHEMY_DATABASE_URI",
                ""
            )

            if database_url.startswith("postgresql"):
                print("DATABASE: PostgreSQL")
            elif database_url.startswith("sqlite"):
                print("DATABASE: SQLite")
            else:
                print("DATABASE: Connected")

            print("=" * 60)

            # ------------------------------------------------
            # DEFAULT ADMIN
            # ------------------------------------------------

            admin_user = User.query.filter_by(
                email="admin@carvion.com"
            ).first()

            if admin_user is None:

                admin_user = User(
                    name="Carvion Admin",
                    email="admin@carvion.com",
                    phone="0700000000",
                    password=generate_password_hash("admin123"),
                    role="admin"
                )

                db.session.add(admin_user)
                db.session.commit()

                print("=" * 60)
                print("DEFAULT ADMIN CREATED")
                print("Email: admin@carvion.com")
                print("Password: admin123")
                print("=" * 60)

        except Exception as e:

            db.session.rollback()

            print("=" * 60)
            print("DATABASE INITIALIZATION ERROR")
            print(str(e))
            print("=" * 60)

    # ========================================================
    # HOME
    # ========================================================

    @app.route("/")
    def home():

        cars = (
            Car.query
            .filter_by(status="Approved")
            .order_by(Car.created_at.desc())
            .limit(6)
            .all()
        )

        return render_template(
            "index.html",
            cars=cars
        )

    # ========================================================
    # DASHBOARD
    # ========================================================

    @app.route("/dashboard")
    @login_required
    def dashboard():

        return render_template("dashboard.html")

    # ========================================================
    # ABOUT
    # ========================================================

    @app.route("/about")
    def about():

        return render_template("about.html")

    # ========================================================
    # CONTACT
    # ========================================================

    @app.route("/contact")
    def contact():

        return render_template("contact.html")

    # ========================================================
    # BUYER HOME
    # ========================================================

    @app.route("/buyer")
    @login_required
    def buyer_home():

        if current_user.role.lower() != "buyer":
            return redirect(url_for("home"))

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

    return app


# ============================================================
# CREATE APPLICATION
# ============================================================

app = create_app()

print("CARVION APP STARTED")


# ============================================================
# DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    print("RUNNING FLASK SERVER")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )