"""Smoke and security regression tests for Carvion Motors."""

import os

import pytest

# Set test-only configuration before importing app.py, whose module creates
# the WSGI application at import time.
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("CARVION_ADMIN_EMAIL", None)
os.environ.pop("CARVION_ADMIN_PASSWORD", None)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import Car, Inquiry, InquiryMessage, User  # noqa: E402
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


def test_marketplace_uses_page_specific_title():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/cars")
        assert response.status_code == 200
        assert b"<title>Carvion Cars Marketplace | Buy & Sell Vehicles</title>" in response.data


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



def test_combined_hire_lease_landing_page_is_public():
    app = make_test_app()

    with app.test_client() as client:
        response = client.get("/hire-lease")

        assert response.status_code == 200
        assert b"Carvion Hire &amp; Lease" in response.data
        assert b"Explore Hire Vehicles" in response.data
        assert b"Explore Lease Vehicles" in response.data
        assert b"Carvion Cars" in response.data


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



def _login_test_user(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _create_inquiry_test_users_and_car(status):
    seller = User(
        name="Test Seller",
        email="seller@example.test",
        phone="0700000001",
        password="test-password",
        role="seller",
    )
    buyer = User(
        name="Test Buyer",
        email="buyer@example.test",
        phone="0700000002",
        password="test-password",
        role="buyer",
    )
    db.session.add_all([seller, buyer])
    db.session.flush()

    car = Car(
        registration_number=f"TEST-{status.upper()}",
        seller_id=seller.id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        price=1500000,
        mileage=25000,
        fuel="Petrol",
        transmission="Automatic",
        location="Nairobi",
        status=status,
    )
    db.session.add(car)
    db.session.commit()
    return buyer, car


def test_inquiry_rejects_unpublished_listing():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)

    with app.app_context():
        buyer, car = _create_inquiry_test_users_and_car("Pending")
        buyer_id, car_id = buyer.id, car.id

    with app.test_client() as client:
        _login_test_user(client, buyer_id)
        response = client.post(
            f"/inquiry/{car_id}",
            data={"message": "Is this vehicle available?"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cars")

    with app.app_context():
        assert Inquiry.query.filter_by(car_id=car_id).count() == 0
        assert InquiryMessage.query.count() == 0


def test_inquiry_still_works_for_approved_listing():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)

    with app.app_context():
        buyer, car = _create_inquiry_test_users_and_car("Approved")
        buyer_id, car_id = buyer.id, car.id

    with app.test_client() as client:
        _login_test_user(client, buyer_id)
        response = client.post(
            f"/inquiry/{car_id}",
            data={"message": "Is this vehicle available?"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/chat/inquiry/" in response.headers["Location"]

    with app.app_context():
        inquiry = Inquiry.query.filter_by(
            car_id=car_id,
            buyer_id=buyer_id,
        ).one()
        assert InquiryMessage.query.filter_by(
            inquiry_id=inquiry.id,
            message="Is this vehicle available?",
        ).count() == 1


def test_admin_can_delete_buyer_with_inquiries_without_foreign_key_error():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)

    with app.app_context():
        admin_user = User(
            name="Test Admin",
            email="admin-delete@example.test",
            phone="0700000010",
            password="test-password",
            role="admin",
        )
        seller = User(
            name="Seller For Deletion Test",
            email="seller-delete@example.test",
            phone="0700000011",
            password="test-password",
            role="seller",
        )
        buyer = User(
            name="Buyer For Deletion Test",
            email="buyer-delete@example.test",
            phone="0700000012",
            password="test-password",
            role="buyer",
        )
        db.session.add_all([admin_user, seller, buyer])
        db.session.flush()

        car = Car(
            registration_number="DELETE-TEST-1",
            seller_id=seller.id,
            brand="Toyota",
            model="Corolla",
            year=2022,
            price=1500000,
            mileage=25000,
            fuel="Petrol",
            transmission="Automatic",
            location="Nairobi",
            status="Approved",
        )
        db.session.add(car)
        db.session.flush()

        inquiry = Inquiry(
            car_id=car.id,
            buyer_id=buyer.id,
            seller_id=seller.id,
            status="Open",
        )
        db.session.add(inquiry)
        db.session.flush()
        db.session.add(InquiryMessage(
            inquiry_id=inquiry.id,
            sender_id=buyer.id,
            receiver_id=seller.id,
            sender_role="buyer",
            message="Is this vehicle available?",
        ))
        db.session.commit()
        admin_id, buyer_id, inquiry_id = admin_user.id, buyer.id, inquiry.id

    with app.test_client() as client:
        _login_test_user(client, admin_id)
        response = client.post(
            f"/admin/delete_user/{buyer_id}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/users")

    with app.app_context():
        assert db.session.get(User, buyer_id) is None
        assert db.session.get(Inquiry, inquiry_id) is None
        assert InquiryMessage.query.count() == 0


def test_admin_cannot_delete_user_who_owns_vehicle_listings():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)

    with app.app_context():
        admin_user = User(
            name="Test Admin",
            email="admin-owner-check@example.test",
            phone="0700000020",
            password="test-password",
            role="admin",
        )
        seller = User(
            name="Seller With Listing",
            email="seller-owner-check@example.test",
            phone="0700000021",
            password="test-password",
            role="seller",
        )
        db.session.add_all([admin_user, seller])
        db.session.flush()
        car = Car(
            registration_number="KEEP-LISTING-1",
            seller_id=seller.id,
            brand="Toyota",
            model="Corolla",
            year=2022,
            price=1500000,
            mileage=25000,
            fuel="Petrol",
            transmission="Automatic",
            location="Nairobi",
            status="Approved",
        )
        db.session.add(car)
        db.session.commit()
        admin_id, seller_id, car_id = admin_user.id, seller.id, car.id

    with app.test_client() as client:
        _login_test_user(client, admin_id)
        response = client.post(
            f"/admin/delete_user/{seller_id}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, seller_id) is not None
        assert db.session.get(Car, car_id) is not None


def _create_car_form_data(**overrides):
    data = {
        "registration_number": "CREATE-TEST-1",
        "brand": "Toyota",
        "model": "Corolla",
        "year": "2022",
        "price": "1500000",
        "mileage": "25000",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "location": "Nairobi",
        "engine": "1.8L",
        "color": "White",
        "condition": "Local Used",
        "description": "Well maintained vehicle",
    }
    data.update(overrides)
    return data



def test_new_car_listings_require_admin_approval(monkeypatch):
    import importlib
    import io

    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    cars_module = importlib.import_module("routes.cars")

    with app.app_context():
        buyer, _ = _create_inquiry_test_users_and_car("Approved")
        buyer_id = buyer.id

    monkeypatch.setattr(
        cars_module,
        "configure_cloudinary",
        lambda: {
            "cloud_name": "test",
            "api_key": "test",
            "api_secret": "test",
            "upload_preset": "test-preset",
        },
    )
    monkeypatch.setattr(
        cars_module.cloudinary.api,
        "ping",
        lambda: {"status": "ok"},
    )
    monkeypatch.setattr(
        cars_module.cloudinary.uploader,
        "upload",
        lambda *args, **kwargs: {
            "secure_url": f"https://example.test/{kwargs['public_id']}.jpg",
            "public_id": kwargs["public_id"],
        },
    )

    data = _create_car_form_data(registration_number="PENDING-TEST-1")
    data["images"] = [
        (io.BytesIO(b"fake image content"), f"vehicle-{index}.jpg")
        for index in range(5)
    ]

    with app.test_client() as client:
        _login_test_user(client, buyer_id)
        response = client.post(
            "/add_car",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    with app.app_context():
        created_car = Car.query.filter_by(
            registration_number="PENDING-TEST-1"
        ).one()
        upgraded_buyer = db.session.get(User, buyer_id)
        assert created_car.status == "Pending"
        assert upgraded_buyer.role == "seller"


def test_report_listing_route_is_registered_once():
    app = make_test_app()

    report_rules = [
        rule for rule in app.url_map.iter_rules()
        if rule.rule == "/car/<int:car_id>/report"
        and "POST" in rule.methods
    ]
    assert len(report_rules) == 1


def test_database_initialization_failure_prevents_app_startup(monkeypatch):
    def fail_create_all():
        raise RuntimeError("test database unavailable")

    monkeypatch.setattr(db, "create_all", fail_create_all)

    with pytest.raises(
        RuntimeError,
        match="Database initialization failed; refusing to start",
    ):
        create_app()


def test_add_car_rejects_negative_mileage_before_uploading_images():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller, _ = _create_inquiry_test_users_and_car("Approved")
        seller_id = User.query.filter_by(email="seller@example.test").one().id
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post("/add_car", data=_create_car_form_data(
            registration_number="NEG-MILEAGE-1", mileage="-1"
        ))
    assert response.status_code == 302
    with app.app_context():
        assert Car.query.filter_by(registration_number="NEG-MILEAGE-1").first() is None


def test_add_car_rejects_unreasonable_year_before_uploading_images():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller, _ = _create_inquiry_test_users_and_car("Approved")
        seller_id = User.query.filter_by(email="seller@example.test").one().id
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post("/add_car", data=_create_car_form_data(
            registration_number="BAD-YEAR-1", year="1800"
        ))
    assert response.status_code == 302
    with app.app_context():
        assert Car.query.filter_by(registration_number="BAD-YEAR-1").first() is None


def test_add_car_requires_fuel_transmission_and_location():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        _create_inquiry_test_users_and_car("Approved")
        seller_id = User.query.filter_by(email="seller@example.test").one().id
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        for field in ("fuel", "transmission", "location"):
            data = _create_car_form_data(registration_number=f"MISSING-{field.upper()}")
            data[field] = ""
            response = client.post("/add_car", data=data)
            assert response.status_code == 302
    with app.app_context():
        assert Car.query.filter(Car.registration_number.like("MISSING-%")).count() == 0


def test_add_car_rejects_fields_longer_than_database_columns():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        _create_inquiry_test_users_and_car("Approved")
        seller_id = User.query.filter_by(email="seller@example.test").one().id
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post("/add_car", data=_create_car_form_data(
            registration_number="LONG-BRAND-1", brand="B" * 51
        ))
    assert response.status_code == 302
    with app.app_context():
        assert Car.query.filter_by(registration_number="LONG-BRAND-1").first() is None




def test_add_car_cleans_up_cloudinary_asset_when_upload_response_is_incomplete(monkeypatch):
    import importlib
    import io

    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    cars_module = importlib.import_module("routes.cars")
    destroyed_ids = []

    with app.app_context():
        _create_inquiry_test_users_and_car("Approved")
        seller_id = User.query.filter_by(email="seller@example.test").one().id

    monkeypatch.setattr(
        cars_module,
        "configure_cloudinary",
        lambda: {
            "cloud_name": "test",
            "api_key": "test",
            "api_secret": "test",
            "upload_preset": "test-preset",
        },
    )
    monkeypatch.setattr(
        cars_module.cloudinary.api,
        "ping",
        lambda: {"status": "ok"},
    )
    monkeypatch.setattr(
        cars_module.cloudinary.uploader,
        "upload",
        lambda *args, **kwargs: {"public_id": "test/orphaned-asset"},
    )
    monkeypatch.setattr(
        cars_module.cloudinary.uploader,
        "destroy",
        lambda public_id, **kwargs: (
            destroyed_ids.append(public_id) or {"result": "ok"}
        ),
    )

    data = _create_car_form_data(registration_number="UPLOAD-FAIL-1")
    data["images"] = [
        (io.BytesIO(b"fake image content"), f"vehicle-{index}.jpg")
        for index in range(5)
    ]

    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(
            "/add_car",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert destroyed_ids == ["test/orphaned-asset"]
    with app.app_context():
        assert Car.query.filter_by(registration_number="UPLOAD-FAIL-1").first() is None



def _create_edit_car_test_data():
    seller = User(
        name="Edit Test Seller",
        email="edit-seller@example.test",
        phone="0700000030",
        password="test-password",
        role="seller",
    )
    db.session.add(seller)
    db.session.flush()
    car = Car(
        registration_number="EDIT-TEST-1",
        seller_id=seller.id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        price=1500000,
        mileage=25000,
        fuel="Petrol",
        transmission="Automatic",
        location="Nairobi",
        description="Original description",
        status="Approved",
    )
    db.session.add(car)
    db.session.commit()
    return seller.id, car.id


def test_edit_car_rejects_negative_price_without_changing_listing():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller_id, car_id = _create_edit_car_test_data()
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(f"/edit_car/{car_id}", data={"price": "-1"})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(Car, car_id).price == 1500000


def test_edit_car_rejects_negative_mileage_without_changing_listing():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller_id, car_id = _create_edit_car_test_data()
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(f"/edit_car/{car_id}", data={"mileage": "-5"})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(Car, car_id).mileage == 25000


def test_edit_car_rejects_unreasonable_year_without_changing_listing():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller_id, car_id = _create_edit_car_test_data()
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(f"/edit_car/{car_id}", data={"year": "1800"})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(Car, car_id).year == 2022


def test_edit_car_accepts_valid_changes():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        seller_id, car_id = _create_edit_car_test_data()
    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(
            f"/edit_car/{car_id}",
            data={
                "brand": "Honda",
                "model": "Civic",
                "year": "2024",
                "price": "2200000",
                "mileage": "12000",
                "fuel": "Petrol",
                "transmission": "Automatic",
                "location": "Mombasa",
                "description": "Updated listing",
            },
            follow_redirects=False,
        )
    assert response.status_code == 302
    with app.app_context():
        car = db.session.get(Car, car_id)
        assert car.brand == "Honda"
        assert car.model == "Civic"
        assert car.year == 2024
        assert car.price == 2200000
        assert car.mileage == 12000
        assert car.location == "Mombasa"
        assert car.description == "Updated listing"

def _create_car_with_images_for_delete_test(image_count=5, registration="IMG-DELETE-TEST"):
    from models import CarImage
    seller = User(
        name="Image Delete Seller",
        email=f"{registration.lower()}@example.test",
        phone="0700000040",
        password="test-password",
        role="seller",
    )
    db.session.add(seller)
    db.session.flush()
    car = Car(
        registration_number=registration,
        seller_id=seller.id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        price=1500000,
        mileage=25000,
        fuel="Petrol",
        transmission="Automatic",
        location="Nairobi",
        status="Approved",
    )
    db.session.add(car)
    db.session.flush()
    for index in range(image_count):
        db.session.add(CarImage(
            car_id=car.id,
            filename=f"https://example.test/{registration}-{index}.jpg",
            public_id=None,
        ))
    db.session.commit()
    return seller.id, car.id


def test_delete_car_cleans_up_reports_without_foreign_key_error():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    from models import Report
    with app.app_context():
        seller_id, car_id = _create_car_with_images_for_delete_test(
            image_count=5, registration="REPORT-CAR-DELETE"
        )
        reporter = User(
            name="Reporter",
            email="reporter-car-delete@example.test",
            phone="0700000041",
            password="test-password",
            role="buyer",
        )
        db.session.add(reporter)
        db.session.flush()
        db.session.add(Report(
            car_id=car_id,
            reporter_id=reporter.id,
            reason="Incorrect information",
            details="Testing deletion",
        ))
        db.session.commit()

    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(f"/delete_car/{car_id}")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Car, car_id) is None
        assert Report.query.filter_by(car_id=car_id).count() == 0


def test_delete_image_keeps_five_image_minimum():
    app = make_test_app()
    app.config.update(WTF_CSRF_ENABLED=False)
    from models import CarImage
    with app.app_context():
        seller_id, car_id = _create_car_with_images_for_delete_test(
            image_count=5, registration="MINIMUM-IMAGE-TEST"
        )
        image_id = CarImage.query.filter_by(car_id=car_id).first().id

    with app.test_client() as client:
        _login_test_user(client, seller_id)
        response = client.post(f"/delete_image/{image_id}")

    assert response.status_code == 302
    with app.app_context():
        assert CarImage.query.filter_by(car_id=car_id).count() == 5

