import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-carvion")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import create_app


def test_app_starts_and_home_responds():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200


def test_logout_requires_post():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.get("/logout")
        assert response.status_code in (404, 405)
