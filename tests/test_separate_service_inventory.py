"""Regression tests for independent hire and lease inventory."""
import os

os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
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
