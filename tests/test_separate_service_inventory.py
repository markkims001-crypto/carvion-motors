"""Regression tests for independent hire and lease inventory."""
import os

os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import User  # noqa: E402
from service_vehicle_models import (  # noqa: E402
    HireVehicle, LeaseVehicle, HireServiceRequest, LeaseServiceRequest,
)


def test_independent_inventory_tables_do_not_depend_on_sale_cars():
    app = create_app()
    with app.app_context():
        assert "cars" in db.metadata.tables
        assert "hire_vehicles" in db.metadata.tables
        assert "lease_vehicles" in db.metadata.tables
        assert "car_id" not in db.metadata.tables["hire_vehicles"].columns
        assert "car_id" not in db.metadata.tables["lease_vehicles"].columns
        assert "vehicle_id" in db.metadata.tables["hire_service_requests"].columns
        assert "vehicle_id" in db.metadata.tables["lease_service_requests"].columns
        assert HireVehicle.__tablename__ != LeaseVehicle.__tablename__
        assert HireServiceRequest.__tablename__ != LeaseServiceRequest.__tablename__


def test_public_hire_and_lease_pages_render_independently():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        hire = client.get("/hire")
        lease = client.get("/lease")
        assert hire.status_code == 200
        assert b"Cars available for hire" in hire.data
        assert lease.status_code == 200
        assert b"Cars available for lease" in lease.data


def test_separate_management_workflows_require_login():
    app = create_app()
    with app.test_client() as client:
        assert client.get("/hire/manage").status_code == 302
        assert client.get("/lease/manage").status_code == 302

def test_buyer_can_start_a_service_inventory_and_is_promoted_to_seller():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        user = User(
            name="Test Buyer",
            email="service-seller@example.com",
            phone="0700000000",
            password="test-password",
            role="buyer",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

        assert client.get("/hire/manage").status_code == 200
        response = client.post("/hire/manage/save", data={
            "registration_number": "KDA123A",
            "brand": "Toyota",
            "model": "Corolla",
            "year": "2022",
            "mileage": "0",
            "fuel": "Petrol",
            "transmission": "Automatic",
            "location": "Nairobi",
            "daily_price": "3500",
            "minimum_days": "1",
        })
        assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.role == "seller"
        assert HireVehicle.query.filter_by(seller_id=user_id).count() == 1

