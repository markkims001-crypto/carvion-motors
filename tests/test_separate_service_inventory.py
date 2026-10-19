"""Regression tests for independent hire and lease inventory."""
import os
from datetime import date

os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import User  # noqa: E402
from service_vehicle_models import (  # noqa: E402
    HireVehicle, LeaseVehicle, HireServiceRequest, LeaseServiceRequest,
    ServiceRequestMessage,
)
from routes.hire_lease import (  # noqa: E402
    _add_months, _hire_request_conflicts, _lease_request_conflicts,
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

def _make_service_test_users():
    seller = User(
        name="Test Seller",
        email="overlap-seller@example.com",
        phone="0700000001",
        password="test-password",
        role="seller",
    )
    renter = User(
        name="Test Renter",
        email="overlap-renter@example.com",
        phone="0700000002",
        password="test-password",
        role="buyer",
    )
    db.session.add_all([seller, renter])
    db.session.flush()
    return seller, renter


def test_hire_acceptance_conflict_detects_overlapping_dates():
    app = create_app()
    with app.app_context():
        seller, renter = _make_service_test_users()
        vehicle = HireVehicle(
            seller_id=seller.id,
            registration_number="KDA900A",
            brand="Toyota",
            model="Axio",
            year=2022,
            mileage=0,
            fuel="Petrol",
            transmission="Automatic",
            location="Nairobi",
            daily_price=3000,
            minimum_days=1,
            status="Published",
        )
        db.session.add(vehicle)
        db.session.flush()
        accepted = HireServiceRequest(
            vehicle_id=vehicle.id,
            renter_id=renter.id,
            seller_id=seller.id,
            start_date=date(2027, 5, 1),
            end_date=date(2027, 5, 5),
            pickup_location="Nairobi",
            status="Accepted",
        )
        candidate = HireServiceRequest(
            vehicle_id=vehicle.id,
            renter_id=renter.id,
            seller_id=seller.id,
            start_date=date(2027, 5, 5),
            end_date=date(2027, 5, 8),
            pickup_location="Nairobi",
            status="Pending",
        )
        db.session.add_all([accepted, candidate])
        db.session.flush()
        assert _hire_request_conflicts(candidate) is True
        candidate.start_date = date(2027, 5, 6)
        assert _hire_request_conflicts(candidate) is False


def test_lease_acceptance_conflict_uses_monthly_periods():
    app = create_app()
    with app.app_context():
        seller, renter = _make_service_test_users()
        vehicle = LeaseVehicle(
            seller_id=seller.id,
            registration_number="KDB900B",
            brand="Toyota",
            model="Premio",
            year=2021,
            mileage=1000,
            fuel="Petrol",
            transmission="Automatic",
            location="Nairobi",
            monthly_price=45000,
            minimum_months=1,
            status="Published",
        )
        db.session.add(vehicle)
        db.session.flush()
        accepted = LeaseServiceRequest(
            vehicle_id=vehicle.id,
            renter_id=renter.id,
            seller_id=seller.id,
            requested_start_date=date(2027, 1, 31),
            duration_months=1,
            location="Nairobi",
            status="Accepted",
        )
        candidate = LeaseServiceRequest(
            vehicle_id=vehicle.id,
            renter_id=renter.id,
            seller_id=seller.id,
            requested_start_date=date(2027, 2, 15),
            duration_months=1,
            location="Nairobi",
            status="Pending",
        )
        db.session.add_all([accepted, candidate])
        db.session.flush()
        assert _add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)
        assert _lease_request_conflicts(candidate) is True
        candidate.requested_start_date = date(2027, 2, 28)
        assert _lease_request_conflicts(candidate) is False



def test_service_request_message_table_is_registered():
    app = create_app()
    with app.app_context():
        assert "service_request_messages" in db.metadata.tables
        assert "sender_id" in db.metadata.tables["service_request_messages"].columns
        assert "receiver_id" in db.metadata.tables["service_request_messages"].columns
        assert "body" in db.metadata.tables["service_request_messages"].columns


def test_customer_service_request_inbox_requires_login():
    app = create_app()
    with app.test_client() as client:
        assert client.get("/my-hire-lease-requests").status_code == 302
