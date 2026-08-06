from flask_migrate import Migrate
import importlib.util
import os

from flask import Flask, render_template, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db, login_manager
from models import User, Car, Inquiry


def import_module_by_path(module_name):
    module_path = os.path.join(
        os.path.dirname(__file__),
        *module_name.split('.')
    ) + '.py'
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    # Upload folder
    upload_folder = app.config.get("UPLOAD_FOLDER")

    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # Extensions
    db.init_app(app)

    migrate = Migrate(
        app,
        db
    )

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Models
    from models import User, Car, CarImage, Inquiry

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprints
    from routes.auth import auth
    from routes.cars import cars
    from routes.admin import admin
    messages = import_module_by_path("routes.messages").messages


    app.register_blueprint(auth)
    app.register_blueprint(cars)
    app.register_blueprint(admin)
    app.register_blueprint(messages)

    # ==========================
    # DATABASE
    # ==========================

    with app.app_context():

        db.create_all()

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

            print("=" * 40)
            print("DEFAULT ADMIN CREATED")
            print("Email: admin@carvion.com")
            print("Password: admin123")
            print("=" * 40)


    # ==========================
    # HOME
    # ==========================

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


    # ==========================
    # DASHBOARD
    # ==========================

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")


    # ==========================
    # ABOUT
    # ==========================

    @app.route("/about")
    def about():
        return render_template("about.html")


    # ==========================
    # CONTACT
    # ==========================

    @app.route("/contact")
    def contact():
        return render_template("contact.html")


    # ==========================
    # BUYER PAGE
    # ==========================

    @app.route("/buyer")
    @login_required
    def buyer_home():

        if current_user.role.lower() != "buyer":
            return redirect(url_for("home"))

        inquiries = (
            Inquiry.query
            .filter_by(buyer_id=current_user.id)
            .order_by(Inquiry.created_at.desc())
            .all()
        )

        return render_template(
            "buyer_home.html",
            inquiries=inquiries
        )


    return app