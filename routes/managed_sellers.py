"""Admin-managed seller profiles and verified account claiming."""
from flask import Blueprint, flash, redirect, render_template_string, request, url_for, abort
from flask_login import current_user, login_required
from sqlalchemy import select, func, or_
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
    query = SellerProfile.query
    search = request.args.get("q", "").strip()[:120]
    kind_filter = request.args.get("kind", "")
    status_filter = request.args.get("status", "")
    if search:
        query = query.filter(or_(SellerProfile.display_name.ilike(f"%{search}%"),
                                 SellerProfile.location.ilike(f"%{search}%")))
    if kind_filter in {"individual", "dealership"}:
        query = query.filter_by(kind=kind_filter)
    if status_filter == "claimed":
        query = query.filter(SellerProfile.claimed_by_user_id.isnot(None))
    elif status_filter == "managed":
        query = query.filter(SellerProfile.claimed_by_user_id.is_(None))
    profiles = query.order_by(SellerProfile.id.desc()).all()
    counts = dict(db.session.query(Car.seller_profile_id, func.count(Car.id))
                  .filter(Car.seller_profile_id.isnot(None))
                  .group_by(Car.seller_profile_id).all())
    totals = {"sellers": SellerProfile.query.filter_by(kind="individual").count(),
              "dealerships": SellerProfile.query.filter_by(kind="dealership").count(),
              "vehicles": Car.query.filter(Car.seller_profile_id.isnot(None)).count(),
              "claims": SellerProfileClaim.query.filter_by(status="pending").count()}
    return render_template_string("""{% extends 'base.html' %}{% block content %}
    <main class="container py-4">
      <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
        <div><h1>Managed Sellers &amp; Dealerships</h1><p class="text-muted">Manage customer profiles and their vehicles.</p></div>
        <a class="btn btn-outline-secondary" href="{{ url_for('admin.dashboard') }}">Admin dashboard</a>
      </div>
      <div class="row g-2 mb-4">
      {% for label, number in [('Individual sellers', totals.sellers), ('Dealerships', totals.dealerships), ('Linked vehicles', totals.vehicles), ('Pending claims', totals.claims)] %}
        <div class="col-6 col-lg-3"><div class="card p-3"><small class="text-muted">{{ label }}</small><h3>{{ number }}</h3></div></div>
      {% endfor %}</div>
      <section class="card p-3 mb-4"><h2 class="h5">Create a managed profile</h2>
      <form method="post" class="row g-2">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="col-md-3"><label class="form-label">Type</label><select class="form-select" name="kind" required><option value="individual">Individual</option><option value="dealership">Dealership</option></select></div>
        <div class="col-md-3"><label class="form-label">Name</label><input class="form-control" name="name" maxlength="120" required></div>
        <div class="col-md-3"><label class="form-label">Location</label><input class="form-control" name="location" maxlength="160" required></div>
        <div class="col-md-3"><label class="form-label">Public phone</label><input class="form-control" name="phone" maxlength="20"></div>
        <div class="col-12"><label><input type="checkbox" name="consent" required> I have permission from this seller to advertise their vehicles</label></div>
        <div class="col-12"><button class="btn btn-primary">Create profile</button></div>
      </form></section>
      <form method="get" class="row g-2 mb-3">
        <div class="col-md-6"><input class="form-control" name="q" value="{{ search }}" placeholder="Search by name or location"></div>
        <div class="col-md-2"><select class="form-select" name="kind"><option value="">All types</option><option value="individual" {% if kind_filter == 'individual' %}selected{% endif %}>Individuals</option><option value="dealership" {% if kind_filter == 'dealership' %}selected{% endif %}>Dealerships</option></select></div>
        <div class="col-md-2"><select class="form-select" name="status"><option value="">All statuses</option><option value="managed" {% if status_filter == 'managed' %}selected{% endif %}>Admin managed</option><option value="claimed" {% if status_filter == 'claimed' %}selected{% endif %}>Claimed</option></select></div>
        <div class="col-md-2"><button class="btn btn-outline-primary w-100">Filter</button></div>
      </form>
      <div class="table-responsive"><table class="table table-hover align-middle"><thead><tr><th>Name</th><th>Type</th><th>Location</th><th>Vehicles</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {% for p in profiles %}<tr><td>{{ p.display_name }}</td><td>{{ p.kind|title }}</td><td>{{ p.location }}</td><td>{{ counts.get(p.id, 0) }}</td><td>{{ 'Claimed' if p.is_claimed else 'Admin managed' }}</td>
      <td><a class="btn btn-sm btn-outline-primary" href="{{ url_for('managed.admin_profile_detail', profile_id=p.id) }}">View / Edit</a></td></tr>
      {% else %}<tr><td colspan="6">No profiles match your filters.</td></tr>{% endfor %}
      </tbody></table></div>
      <a href="{{ url_for('managed.admin_claims') }}">Review seller claim requests</a>
    </main>{% endblock %}""", profiles=profiles, counts=counts, totals=totals,
                                  search=search, kind_filter=kind_filter, status_filter=status_filter)


@managed.route("/admin/<int:profile_id>", methods=["GET", "POST"])
@login_required
def admin_profile_detail(profile_id):
    _admin()
    profile = db.get_or_404(SellerProfile, profile_id)
    if request.method == "POST":
        if not profile.can_manage(current_user):
            abort(403)
        kind = request.form.get("kind", "").strip()
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        private_phone = request.form.get("private_phone", "").strip()
        description = request.form.get("description", "").strip()
        if (kind not in {"individual", "dealership"} or not name or len(name) > 120
                or not location or len(location) > 160 or len(phone) > 20
                or len(private_phone) > 20 or len(description) > 3000):
            flash("Check the profile details and try again.", "danger")
            return redirect(url_for("managed.admin_profile_detail", profile_id=profile.id))
        profile.kind = kind
        profile.display_name = name
        profile.location = location
        profile.public_phone = phone or None
        profile.private_phone = private_phone or None
        profile.description = description or None
        _audit(profile, "profile_updated")
        db.session.commit()
        flash("Seller profile updated.", "success")
        return redirect(url_for("managed.admin_profile_detail", profile_id=profile.id))
    vehicles = Car.query.filter_by(seller_profile_id=profile.id).order_by(Car.created_at.desc()).all()
    history = SellerProfileAudit.query.filter_by(profile_id=profile.id).order_by(SellerProfileAudit.id.desc()).limit(20).all()
    return render_template_string("""{% extends 'base.html' %}{% block content %}
    <main class="container py-4">
      <a href="{{ url_for('managed.admin_profiles') }}">← All managed sellers</a>
      <h1 class="mt-3">{{ profile.display_name }}</h1>
      <p class="text-muted">{{ profile.kind|title }} · {{ 'Claimed' if profile.is_claimed else 'Admin managed' }}
      {% if profile.is_claimed %} · {{ 'Assistance enabled' if profile.assistance_enabled else 'Owner managed' }}{% endif %}</p>
      <div class="row g-3">
        <div class="col-lg-6"><section class="card p-3"><h2 class="h5">Profile details</h2>
        {% if profile.can_manage(current_user) %}
        <form method="post">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <label class="form-label">Type</label><select class="form-select mb-2" name="kind"><option value="individual" {% if profile.kind == 'individual' %}selected{% endif %}>Individual</option><option value="dealership" {% if profile.kind == 'dealership' %}selected{% endif %}>Dealership</option></select>
          <label class="form-label">Name</label><input class="form-control mb-2" name="name" maxlength="120" value="{{ profile.display_name }}" required>
          <label class="form-label">Location</label><input class="form-control mb-2" name="location" maxlength="160" value="{{ profile.location }}" required>
          <label class="form-label">Public phone</label><input class="form-control mb-2" name="phone" maxlength="20" value="{{ profile.public_phone or '' }}">
          <label class="form-label">Private phone (admin only)</label><input class="form-control mb-2" name="private_phone" maxlength="20" value="{{ profile.private_phone or '' }}">
          <label class="form-label">Description</label><textarea class="form-control mb-3" name="description" maxlength="3000" rows="4">{{ profile.description or '' }}</textarea>
          <button class="btn btn-primary">Save changes</button>
        </form>
        {% else %}<p>This owner has claimed their profile and has not enabled admin assistance. Editing is disabled.</p>
        <p>{{ profile.location }} · {{ profile.public_phone or 'No public phone' }}</p>{% endif %}
        </section></div>
        <div class="col-lg-6"><section class="card p-3 mb-3"><h2 class="h5">Vehicles ({{ vehicles|length }})</h2>
          {% if profile.can_manage(current_user) %}<a class="btn btn-outline-primary mb-3" href="{{ url_for('cars.add_car', seller_profile_id=profile.id) }}">Add vehicle for this seller</a>{% endif %}
          <ul class="list-group">{% for car in vehicles %}
          <li class="list-group-item d-flex justify-content-between align-items-center"><span>{{ car.brand }} {{ car.model }} · {{ car.registration_number }}<br><small class="text-muted">{{ car.status }}</small></span>
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('cars.car_details', car_id=car.id) }}">View car</a></li>
          {% else %}<li class="list-group-item">No linked vehicles yet.</li>{% endfor %}</ul>
        </section><section class="card p-3"><h2 class="h5">Activity history</h2>
        <ul class="list-group list-group-flush">{% for entry in history %}<li class="list-group-item">{{ entry.action|replace('_', ' ')|title }} <small class="text-muted">{{ entry.created_at.strftime('%d %b %Y %H:%M') }}</small></li>
        {% else %}<li class="list-group-item">No activity recorded.</li>{% endfor %}</ul></section></div>
      </div>
    </main>{% endblock %}""", profile=profile, vehicles=vehicles, history=history)

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
