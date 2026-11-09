"""Public showrooms and seller-owned dealership profile setup."""
import re
from flask import Blueprint, abort, flash, redirect, render_template_string, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from extensions import db
from dealership_models import Dealership
from models import Car

dealers = Blueprint("dealers", __name__, url_prefix="/dealers")

@dealers.route("/<slug>")
def showroom(slug):
    dealer = Dealership.query.filter_by(slug=slug).first_or_404()
    vehicles = Car.query.filter_by(seller_id=dealer.owner_id).order_by(Car.id.desc()).all()
    return render_template_string("""{% extends 'base.html' %}{% block title %}{{ dealer.name }} | Carvion Motors{% endblock %}{% block content %}
    <main class="container py-5"><h1>{{ dealer.name }}</h1><p>{{ dealer.location }}</p>
    <p>{{ dealer.description or 'Carvion Motors dealership showroom' }}</p>
    {% if dealer.is_verified %}<span class="badge bg-success">Verified dealership</span>{% endif %}
    <h2 class="mt-4">Available vehicles</h2><div class="row g-3">
    {% for car in vehicles %}<div class="col-md-4"><div class="card p-3"><h3 class="h5">{{ car.brand }} {{ car.model }}</h3><p>{{ car.year }} · KSh {{ '{:,}'.format(car.price) }}</p></div></div>
    {% else %}<p>No vehicles listed yet.</p>{% endfor %}</div></main>
    {% endblock %}""", dealer=dealer, vehicles=vehicles)

@dealers.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    if current_user.role not in ("seller", "admin"):
        flash("Switch to a seller account before creating a dealership.", "warning")
        return redirect(url_for("home"))
    dealer = Dealership.query.filter_by(owner_id=current_user.id).first()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        description = request.form.get("description", "").strip()
        if not name or len(name) > 120 or not location or len(location) > 160 or not phone or len(phone) > 20 or len(description) > 2000:
            flash("Enter valid dealership details.", "danger")
        else:
            if dealer is None:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:100] or "dealer"
                slug = f"{slug}-{current_user.id}"
                dealer = Dealership(owner_id=current_user.id, slug=slug)
                db.session.add(dealer)
            dealer.name, dealer.location, dealer.phone, dealer.description = name, location, phone, description
            try:
                db.session.commit()
                flash("Dealership profile saved.", "success")
                return redirect(url_for("dealers.showroom", slug=dealer.slug))
            except IntegrityError:
                db.session.rollback()
                flash("Unable to save dealership profile.", "danger")
    return render_template_string("""{% extends 'base.html' %}{% block title %}Dealership profile | Carvion Motors{% endblock %}{% block content %}
    <main class="container py-5"><h1>My dealership</h1><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label class="form-label">Company name</label><input class="form-control mb-3" name="name" maxlength="120" required value="{{ dealer.name if dealer else '' }}">
    <label class="form-label">Location</label><input class="form-control mb-3" name="location" maxlength="160" required value="{{ dealer.location if dealer else '' }}">
    <label class="form-label">Business phone</label><input class="form-control mb-3" name="phone" maxlength="20" required value="{{ dealer.phone if dealer else '' }}">
    <label class="form-label">Description</label><textarea class="form-control mb-3" name="description" maxlength="2000">{{ dealer.description or '' if dealer else '' }}</textarea>
    <button class="btn btn-warning" type="submit">Save dealership</button></form></main>{% endblock %}""", dealer=dealer)
