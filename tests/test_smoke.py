"""Smoke and security regression tests for Carvion Motors."""

import os

# Set test-only configuration before importing app.py, whose module creates
# the WSGI application at import time.
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402


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
