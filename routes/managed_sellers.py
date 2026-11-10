"""Admin-managed seller profiles and verified account claiming."""
from flask import Blueprint, flash, redirect, render_template_string, request, url_for, abort
from flask_login import current_user, login_required
from sqlalchemy import select
from extensions import db, utcnow
from models import User, Car, Inquiry
from seller_profile_models import SellerProfile, SellerProfileClaim, SellerProfileAudit

managed = Blueprint("managed", __name__, url_prefix="/managed-sellers")

def _admin():
    if current_user.role != "admin":
        abort(403)

def _audit(profile, action):
    db.session.add(SellerProfileAudit(profile_id=profile.id, actor_user_id=current_user.id, action=action))

@managed.route("/admin", methods=["GET", "POST"])
@login_required
def admin_profiles():
    _admin()
    if request.method == "POST":
        kind = request.form.get("kind", "").strip()
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        consent = request.form.get("consent") == "on"
        if kind not in {"individual", "dealership"} or not name or len(name) > 120 or not location or len(location) > 160 or len(phone) > 20 or not consent:
            flash("Provide valid seller details and confirm advertising permission.", "danger")
            return redirect(url_for("managed.admin_profiles"))
        profile = SellerProfile(kind=kind, display_name=name, location=location,
                                public_phone=phone or None, created_by_admin_id=current_user.id,
                                advertising_consent_recorded=True)
        db.session.add(profile)
        db.session.flush()
        _audit(profile, "profile_created")
        db.session.commit()
        flash("Managed seller profile created.", "success")
        return redirect(url_for("managed.admin_profiles"))
    profiles = SellerProfile.query.order_by(SellerProfile.id.desc()).all()
    return render_template_string("""{% extends 'base.html' %}{% block content %}
    <main class="container py-4"><h1>Managed sellers</h1>
    <form method="post" class="card p-3 mb-4">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label>Type <select class="form-select" name="kind" required><option value="individual">Individual</option><option value="dealership">Dealership</option></select></label>
      <label>Name <input class="form-control" name="name" maxlength="120" required></label>
      <label>Location <input class="form-control" name="location" maxlength="160" required></label>
      <label>Public phone <input class="form-control" name="phone" maxlength="20"></label>
      <label><input type="checkbox" name="consent" required> I have the seller's permission to advertise</label>
      <button class="btn btn-primary mt-2">Create seller profile</button>
    </form>
    <h2>Profiles</h2><ul>
    {% for p in profiles %}<li>{{ p.display_name }} ({{ p.kind }}) — {{ 'Claimed' if p.is_claimed else 'Admin managed' }}</li>{% endfor %}
    </ul><a href="{{ url_for('managed.admin_claims') }}">Review claim requests</a></main>
    {% endblock %}""", profiles=profiles)

@managed.route("/<int:profile_id>/claim", methods=["POST"])
@login_required
def request_claim(profile_id):
    profile = db.get_or_404(SellerProfile, profile_id)
    if current_user.role not in {"seller", "buyer"} or profile.is_claimed:
        abort(403)
    if SellerProfileClaim.query.filter_by(profile_id=profile.id, requesting_user_id=current_user.id, status="pending").first():
        flash("Your claim is already awaiting review.", "info")
        return redirect(url_for("home"))
    db.session.add(SellerProfileClaim(profile_id=profile.id, requesting_user_id=current_user.id))
    _audit(profile, "claim_requested")
    db.session.commit()
    flash("Claim request submitted for admin verification.", "success")
    return redirect(url_for("home"))

@managed.route("/admin/claims")
@login_required
def admin_claims():
    _admin()
    claims = SellerProfileClaim.query.filter_by(status="pending").order_by(SellerProfileClaim.id.desc()).all()
    return render_template_string("""{% extends 'base.html' %}{% block content %}
    <main class="container py-4"><h1>Seller claim requests</h1>
    {% for c in claims %}<section class="card p-3 mb-3">
    <strong>{{ c.profile.display_name }}</strong> — {{ c.requester.name }} ({{ c.requester.email }})
    <p>Verify seller authority independently before approval.</p>
    <form method="post" action="{{ url_for('managed.review_claim', claim_id=c.id) }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button class="btn btn-success" name="decision" value="approve">Approve verified claim</button>
    <button class="btn btn-outline-danger" name="decision" value="reject">Reject</button></form>
    </section>{% else %}<p>No pending claims.</p>{% endfor %}</main>
    {% endblock %}""", claims=claims)

@managed.route("/admin/claims/<int:claim_id>/review", methods=["POST"])
@login_required
def review_claim(claim_id):
    _admin()
    decision = request.form.get("decision")
    if decision not in {"approve", "reject"}:
        abort(400)
    claim = db.session.execute(select(SellerProfileClaim).where(SellerProfileClaim.id == claim_id).with_for_update()).scalar_one_or_none()
    if claim is None:
        abort(404)
    profile = db.session.execute(select(SellerProfile).where(SellerProfile.id == claim.profile_id).with_for_update()).scalar_one()
    if claim.status != "pending" or profile.is_claimed:
        db.session.rollback()
        flash("Claim is no longer available.", "warning")
        return redirect(url_for("managed.admin_claims"))
    claim.status = "approved" if decision == "approve" else "rejected"
    claim.reviewed_by_admin_id = current_user.id
    claim.reviewed_at = utcnow()
    if decision == "approve":
        # Transfer only this profile's listings and their inquiry recipients.
        # Never reassign unrelated cars owned by the same admin.
        vehicle_ids = [car_id for (car_id,) in db.session.query(Car.id).filter(
            Car.seller_profile_id == profile.id
        ).all()]
        if vehicle_ids:
            Car.query.filter(Car.id.in_(vehicle_ids)).update(
                {"seller_id": claim.requesting_user_id}, synchronize_session=False
            )
            Inquiry.query.filter(Inquiry.car_id.in_(vehicle_ids)).update(
                {"seller_id": claim.requesting_user_id}, synchronize_session=False
            )
        profile.claimed_by_user_id = claim.requesting_user_id
        profile.assistance_enabled = False
        SellerProfileClaim.query.filter(SellerProfileClaim.profile_id == profile.id,
                                       SellerProfileClaim.id != claim.id,
                                       SellerProfileClaim.status == "pending").update(
            {"status": "rejected", "reviewed_by_admin_id": current_user.id, "reviewed_at": utcnow()},
            synchronize_session=False)
    _audit(profile, "claim_" + claim.status)
    db.session.commit()
    flash("Claim reviewed.", "success")
    return redirect(url_for("managed.admin_claims"))

@managed.route("/<int:profile_id>/assistance", methods=["POST"])
@login_required
def set_assistance(profile_id):
    profile = db.get_or_404(SellerProfile, profile_id)
    if profile.claimed_by_user_id != current_user.id:
        abort(403)
    if request.form.get("enabled") not in {"yes", "no"}:
        abort(400)
    profile.assistance_enabled = request.form["enabled"] == "yes"
    _audit(profile, "assistance_enabled" if profile.assistance_enabled else "assistance_disabled")
    db.session.commit()
    flash("Carvion assistance preference updated.", "success")
    return redirect(url_for("home"))
