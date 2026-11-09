"""Fast structural regression checks for the dealership MVP."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dealership_model_has_unique_owner():
    from dealership_models import Dealership
    assert Dealership.__table__.columns["owner_id"].unique
    assert Dealership.__table__.columns["slug"].unique
    assert Dealership.__table__.columns["is_verified"].default.arg is False


def test_seller_navigation_has_dealership_link():
    template = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "url_for('dealers.setup')" in template


def test_showroom_uses_public_listing_filter():
    source = (ROOT / "routes" / "dealers.py").read_text(encoding="utf-8")
    assert 'status="Approved"' in source
    assert 'owner_id=current_user.id' in source
    assert 'csrf_token()' in source
