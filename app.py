from flask import Flask, render_template, redirect, url_for
from flask_login import login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
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
    Notification,
    PasswordResetCode,
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    db.init_app(app)
    Migrate(app, db)
    CSRFProtect(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in first."

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    @app.context_processor
    def inject_notification_data():
        data = {
            "unread_notifications": 0,
            "unread_favorites": 0,
            "unread_compares": 0,
            "unread_inquiries": 0,
            "unread_vehicle_updates": 0,
            "unread_messages": 0,
        }

        if not current_user.is_authenticated:
            return data

        notifications = (
            Notification.query
            .filter(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
            )
            .all()
        )

        data["unread_notifications"] = len(notifications)
        data["unread_favorites"] = sum(
            1 for notification in notifications
            if notification.notification_type == "favorite"
        )
        data["unread_compares"] = sum(
            1 for notification in notifications
            if notification.notification_type == "compare"
        )
        data["unread_vehicle_updates"] = sum(
            1 for notification in notifications
            if notification.notification_type in (
                "vehicle", "approval", "rejection"
            )
        )

        if (getattr(current_user, "role", "") or "").lower() == "admin":
            data["unread_inquiries"] = (
                Notification.query
                .filter(
                    Notification.user_id == current_user.id,
                    Notification.notification_type == "inquiry",
                    Notification.is_read.is_(False),
                )
                .count()
            )
        else:
            data["unread_inquiries"] = (
                InquiryMessage.query
                .filter(
                    InquiryMessage.receiver_id == current_user.id,
                    InquiryMessage.is_read.is_(False),
                )
                .count()
            )

        data["unread_messages"] = (
            Message.query
            .filter(
                Message.receiver_id == current_user.id,
                Message.is_read.is_(False),
            )
            .count()
        )

        return data

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

    with app.app_context():
        try:
            db.create_all()

            if db.engine.dialect.name == "postgresql":
                from sqlalchemy import text

                with db.engine.begin() as connection:
                    connection.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN IF NOT EXISTS allow_phone_contact
                        BOOLEAN NOT NULL DEFAULT TRUE
                    """))
                    connection.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN IF NOT EXISTS allow_whatsapp_contact
                        BOOLEAN NOT NULL DEFAULT TRUE
                    """))

                print("Seller contact preferences verified.")

            database_url = app.config.get(
                "SQLALCHEMY_DATABASE_URI", ""
            )

            if database_url.startswith("postgresql"):
                print("DATABASE: PostgreSQL")
            elif database_url.startswith("sqlite"):
                print("DATABASE: SQLite")
            else:
                print("DATABASE: Connected")

            print("=" * 60)

            admin_email = os.environ.get(
                "CARVION_ADMIN_EMAIL", ""
            ).strip().lower()
            admin_password = os.environ.get(
                "CARVION_ADMIN_PASSWORD", ""
            )

            if admin_email and admin_password:
                admin_user = User.query.filter_by(
                    email=admin_email
                ).first()

                if admin_user is None:
                    admin_user = User(
                        name="Carvion Admin",
                        email=admin_email,
                        phone="0700000000",
                        password=generate_password_hash(admin_password),
                        role="admin",
                    )
                    db.session.add(admin_user)
                    db.session.commit()
                    print("Initial admin account created.")
                else:
                    print("Configured admin account already exists.")
            else:
                print(
                    "Initial admin creation skipped. Configure "
                    "CARVION_ADMIN_EMAIL and CARVION_ADMIN_PASSWORD if needed."
                )

        except Exception:
            db.session.rollback()
            app.logger.exception("DATABASE INITIALIZATION ERROR")

    @app.route("/")
    def home():
        cars = (
            Car.query
            .filter_by(status="Approved")
            .order_by(Car.created_at.desc())
            .limit(6)
            .all()
        )
        return render_template("index.html", cars=cars)

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/buyer")
    @login_required
    def buyer_home():
        if (getattr(current_user, "role", "") or "").lower() != "buyer":
            return redirect(url_for("home"))

        inquiries = (
            Inquiry.query
            .filter_by(buyer_id=current_user.id)
            .order_by(Inquiry.created_at.desc())
            .all()
        )

        return render_template(
            "buyer_home.html",
            inquiries=inquiries,
        )

    return app


app = create_app()

print("CARVION APP STARTED")


if __name__ == "__main__":
    print("RUNNING FLASK SERVER")
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
