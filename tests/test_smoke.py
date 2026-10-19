"""Smoke and security regression tests for Carvion Motors."""

import os

# Set test-only configuration before importing app.py, whose module creates
# the WSGI application at import time.
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from hire_lease_models import (  # noqa: E402
    CarHireOption,
    CarLeaseOption,
    HireRequest,
    LeaseRequest,
)


def make_test_app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_homepage_returns_success():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200


def test_logout_rejects_get_requests():
    app = make_test_app()

    with app.test_client() as client:
        assert client.get("/logout").status_code == 405
        assert client.get("/force_logout").status_code == 405


def test_logout_requires_valid_csrf_token():
    app = make_test_app()

    with app.test_client() as client:
        response = client.post("/logout", data={})
        assert response.status_code == 400


def test_password_reset_pages_are_reachable():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/forgot-password", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/forgot-password-email")
        assert client.get("/forgot-password-email").status_code == 200
        assert client.get("/forgot-password-sms").status_code == 200
        assert client.get("/verify-reset-code").status_code == 302


def test_about_and_privacy_pages_are_reachable():
    app = make_test_app()

    with app.test_client() as client:
        about_response = client.get("/about")
        privacy_response = client.get("/privacy")

        assert about_response.status_code == 200
        assert b"About Carvion Motors" in about_response.data
        assert privacy_response.status_code == 200
        assert b"Privacy Policy" in privacy_response.data


def test_contact_page_shows_official_contact_details():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/contact")
        assert response.status_code == 200
        assert b"+0182709886" in response.data
        assert b"carvionmotor@gmail.com" in response.data


def test_hire_and_lease_models_are_registered_without_changing_car_table():
    app = make_test_app()

    with app.app_context():
        assert CarHireOption.__tablename__ == "car_hire_options"
        assert CarLeaseOption.__tablename__ == "car_lease_options"
        assert HireRequest.__tablename__ == "hire_requests"
        assert LeaseRequest.__tablename__ == "lease_requests"

        # The feature uses new tables; the existing cars table remains intact.
        assert "price" in db.metadata.tables["cars"].columns
        assert "registration_number" in db.metadata.tables["cars"].columns
        assert "car_id" in db.metadata.tables["car_hire_options"].columns
        assert "daily_price" in db.metadata.tables["car_hire_options"].columns
        assert "monthly_price" in db.metadata.tables["car_lease_options"].columns
        assert "start_date" in db.metadata.tables["hire_requests"].columns
        assert "requested_start_date" in db.metadata.tables["lease_requests"].columns



def test_hire_lease_settings_page_requires_login():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/hire/manage")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]



def test_public_hire_and_lease_listing_pages_are_reachable():
    app = make_test_app()

    with app.test_client() as client:
        hire_response = client.get("/hire")
        lease_response = client.get("/lease")

        assert hire_response.status_code == 200
        assert b"Cars available for hire" in hire_response.data
        assert lease_response.status_code == 200
        assert b"Cars available for lease" in lease_response.data


def test_hire_and_lease_request_forms_require_login():
    app = make_test_app()

    with app.test_client() as client:
        hire_response = client.get("/hire/vehicle/1/request")
        lease_response = client.get("/lease/vehicle/1/request")

        assert hire_response.status_code == 302
        assert "/login" in hire_response.headers["Location"]
        assert lease_response.status_code == 302
        assert "/login" in lease_response.headers["Location"]


def test_seller_hire_lease_inbox_requires_login():
    app = make_test_app()
    with app.test_client() as client:
        response = client.get("/seller/hire-lease-requests")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_seller_hire_lease_actions_reject_get_requests():
    app = make_test_app()
    with app.test_client() as client:
        assert client.get("/hire/requests/1/respond").status_code == 405
        assert client.get("/lease/requests/1/respond").status_code == 405
