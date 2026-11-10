"""Tests for the first, additive managed-seller data-model phase."""
from app import create_app
from extensions import db
from models import User
from seller_profile_models import SellerProfile, SellerProfileClaim, SellerProfileAudit


def test_managed_profile_can_exist_without_seller_login():
    app = create_app()
    with app.app_context():
        admin = User(name="Admin", email="managed-admin@example.test", phone="254700000101", password="test", role="admin")
        db.session.add(admin)
        db.session.flush()
        profile = SellerProfile(kind="dealership", display_name="Test Motors", location="Nairobi",
                                created_by_admin_id=admin.id, advertising_consent_recorded=True)
        db.session.add(profile)
        db.session.commit()
        assert profile.claimed_by_user_id is None
        assert profile.can_manage(admin)
        assert not profile.assistance_enabled


def test_claimed_seller_controls_admin_assistance():
    app = create_app()
    with app.app_context():
        admin = User(name="Admin", email="managed-admin-2@example.test", phone="254700000102", password="test", role="admin")
        seller = User(name="Seller", email="managed-seller@example.test", phone="254700000103", password="test", role="seller")
        db.session.add_all([admin, seller])
        db.session.flush()
        profile = SellerProfile(kind="individual", display_name="Seller", location="Nairobi",
                                created_by_admin_id=admin.id, claimed_by_user_id=seller.id)
        db.session.add(profile)
        db.session.commit()
        assert profile.can_manage(seller)
        assert not profile.can_manage(admin)
        profile.assistance_enabled = True
        db.session.commit()
        assert profile.can_manage(admin)
        profile.assistance_enabled = False
        db.session.commit()
        assert not profile.can_manage(admin)
