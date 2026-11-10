"""Buyer-managed saved searches; notifications are in-app and opt-in."""
from flask import Blueprint, abort, flash, redirect, render_template_string, request, url_for
from flask_login import current_user, login_required
from extensions import db
from buyer_alert_models import SavedVehicleSearch, VehicleAlertEvent
from models import Notification

buyer_alerts = Blueprint("buyer_alerts", __name__, url_prefix="/buyer-alerts")

@buyer_alerts.route("/", methods=["GET", "POST"])
@login_required
def searches():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:100]
        brand = request.form.get("brand", "").strip()[:50]
        location = request.form.get("location", "").strip()[:100]
        try:
            max_price = int(request.form["max_price"]) if request.form.get("max_price") else None
            min_year = int(request.form["min_year"]) if request.form.get("min_year") else None
        except ValueError:
            flash("Enter valid price and year values.", "danger")
            return redirect(url_for("buyer_alerts.searches"))
        if not name or (max_price is not None and max_price <= 0) or (min_year is not None and not 1900 <= min_year <= 2200):
            flash("Enter a search name and valid filters.", "danger")
            return redirect(url_for("buyer_alerts.searches"))
        if SavedVehicleSearch.query.filter_by(user_id=current_user.id).count() >= 20:
            flash("You can save up to 20 searches.", "warning")
            return redirect(url_for("buyer_alerts.searches"))
        db.session.add(SavedVehicleSearch(user_id=current_user.id, name=name, brand=brand or None,
                                         location=location or None, max_price=max_price, min_year=min_year))
        db.session.commit()
        flash("Saved search created. New matching vehicles will trigger in-app alerts.", "success")
        return redirect(url_for("buyer_alerts.searches"))
    records = SavedVehicleSearch.query.filter_by(user_id=current_user.id).order_by(SavedVehicleSearch.id.desc()).all()
    return render_template_string("""{% extends 'base.html' %}{% block content %}
    <main class="container py-4"><h1>Vehicle alerts</h1><p>Save your preferences and receive in-app notifications when matching vehicles are listed.</p>
    <form method="post" class="card p-3 row g-2 mb-4">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Search name<input class="form-control" name="name" maxlength="100" required></label>
    <label>Brand<input class="form-control" name="brand" maxlength="50" placeholder="e.g. Toyota"></label>
    <label>Location<input class="form-control" name="location" maxlength="100" placeholder="e.g. Nairobi"></label>
    <label>Maximum price (KSh)<input class="form-control" type="number" min="1" name="max_price"></label>
    <label>Minimum year<input class="form-control" type="number" min="1900" max="2200" name="min_year"></label>
    <button class="btn btn-primary mt-3">Save search</button></form>
    <h2 class="h4">My saved searches</h2>
    {% for item in records %}<div class="card p-3 mb-2 d-flex flex-row justify-content-between align-items-center">
    <div><strong>{{ item.name }}</strong><br><small>{{ item.brand or 'Any brand' }} · {{ item.location or 'Any location' }} · {{ 'Enabled' if item.enabled else 'Paused' }}</small></div>
    <form method="post" action="{{ url_for('buyer_alerts.toggle', search_id=item.id) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="btn btn-outline-secondary">{{ 'Pause' if item.enabled else 'Resume' }}</button></form>
    <form method="post" action="{{ url_for('buyer_alerts.delete', search_id=item.id) }}" onsubmit="return confirm('Delete this saved search?')"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button class="btn btn-outline-danger">Delete</button></form></div>
    {% else %}<p>No saved searches yet.</p>{% endfor %}
    </main>{% endblock %}""", records=records)

@buyer_alerts.route("/<int:search_id>/toggle", methods=["POST"])
@login_required
def toggle(search_id):
    item = db.get_or_404(SavedVehicleSearch, search_id)
    if item.user_id != current_user.id:
        abort(403)
    item.enabled = not item.enabled
    db.session.commit()
    return redirect(url_for("buyer_alerts.searches"))

@buyer_alerts.route("/<int:search_id>/delete", methods=["POST"])
@login_required
def delete(search_id):
    item = db.get_or_404(SavedVehicleSearch, search_id)
    if item.user_id != current_user.id:
        abort(403)
    VehicleAlertEvent.query.filter_by(search_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("buyer_alerts.searches"))

def notify_matching_searches(car):
    """Call before a listing transaction commits; duplicate events are suppressed."""
    if car.status != "Approved":
        return
    for saved in SavedVehicleSearch.query.filter_by(enabled=True).all():
        if saved.user_id == car.seller_id or not saved.matches(car):
            continue
        exists = VehicleAlertEvent.query.filter_by(search_id=saved.id, car_id=car.id, event_type="new").first()
        if exists:
            continue
        db.session.add(VehicleAlertEvent(search_id=saved.id, car_id=car.id, event_type="new"))
        db.session.add(Notification(user_id=saved.user_id, car_id=car.id,
            title="New vehicle matching your saved search",
            message=f"{car.brand} {car.model} matches '{saved.name}'.",
            notification_type="saved_search", is_read=False))
