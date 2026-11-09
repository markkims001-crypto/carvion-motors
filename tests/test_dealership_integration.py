"""Dealership behavior tests with an isolated SQLite database."""
import pytest
from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, Car
from dealership_models import Dealership
from routes.dealers import dealers


@pytest.fixture
def client_app(tmp_path):
    app = Flask(__name__, template_folder="../templates")
    app.config.update(SECRET_KEY="test-secret", TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///" + str(tmp_path / "dealers.sqlite"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    login_manager = LoginManager(app)
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    app.register_blueprint(dealers)
    @app.route("/")
    def home():
        return "Home"
    with app.app_context():
        db.create_all()
        db.session.add_all([
            User(id=1, name="Private seller", email="private@example.com", phone="254712345678", password=generate_password_hash("test"), role="buyer"),
            User(id=2, name="Dealer owner", email="dealer@example.com", phone="254712345679", password=generate_password_hash("test"), role="seller"),
            User(id=3, name="Other seller", email="other@example.com", phone="254712345670", password=generate_password_hash("test"), role="seller"),
        ])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_buyer_cannot_create_dealership(client_app):
    with client_app.test_client() as client:
        login(client, 1)
        response = client.post("/dealers/setup", data={"name":"Unauthorized","location":"Nairobi","phone":"254712345678"})
        assert response.status_code == 302
    with client_app.app_context():
        assert Dealership.query.count() == 0


def test_seller_can_create_and_edit_dealership(client_app):
    with client_app.test_client() as client:
        login(client, 2)
        response = client.post("/dealers/setup", data={"name":"Prestige Autos","location":"Nairobi","phone":"254712345679"})
        assert response.status_code == 302
        assert "/dealers/prestige-autos-2" in response.location
        response = client.post("/dealers/setup", data={"name":"Prestige Motors","location":"Mombasa","phone":"254712345679"})
        assert response.status_code == 302
    with client_app.app_context():
        assert Dealership.query.count() == 1
        dealer = Dealership.query.one()
        assert dealer.name == "Prestige Motors"
        assert dealer.location == "Mombasa"
        assert dealer.is_verified is False


def test_showroom_is_public_and_missing_dealer_404(client_app, monkeypatch):
    monkeypatch.setattr('routes.dealers.render_template', lambda *args, **kwargs: 'Showroom')
    with client_app.app_context():
        db.session.add(Dealership(owner_id=2, name="Prestige Autos", slug="prestige-autos-2", location="Nairobi", phone="254712345679"))
        db.session.commit()
    with client_app.test_client() as client:
        assert client.get("/dealers/prestige-autos-2").status_code == 200
        assert client.get("/dealers/not-found").status_code == 404
