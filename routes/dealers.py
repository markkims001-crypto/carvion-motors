"""Public showrooms and seller-owned dealership profile setup."""
import re
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from extensions import db
from dealership_models import Dealership
from models import Car

dealers = Blueprint("dealers", __name__, url_prefix="/dealers")

@dealers.route("/<slug>")
def showroom(slug):
    dealer = Dealership.query.filter_by(slug=slug).first_or_404()
    vehicles = Car.query.filter_by(seller_id=dealer.owner_id, status="Approved").order_by(Car.id.desc()).all()
    return render_template("dealers/showroom.html", dealer=dealer, vehicles=vehicles)

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
    return render_template("dealers/setup.html", dealer=dealer)
