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
        assert response.headers["Location"].endswith("/forgot-password-sms")
        assert client.get("/forgot-password-email").status_code == 200
        assert client.get("/forgot-password-sms").status_code == 200
        assert client.get("/verify-reset-code").status_code == 302
