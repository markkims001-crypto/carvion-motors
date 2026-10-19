"""Independent public listings and management workflows for hire and lease.

This blueprint never reads or writes the sale-marketplace Car table. Hire and
lease each use their own inventory and request tables.
"""
import calendar
import os
import uuid
from datetime import date
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from service_vehicle_models import (
    HireVehicle, LeaseVehicle, HireServiceRequest, LeaseServiceRequest,
)

hire_lease = Blueprint("hire_lease", __name__)


@hire_lease.route("/hire-lease")
def hire_lease_home():
    """Combined public entry point for the Carvion Hire & Lease service."""
    return render_template("hire_lease_home.html")


def _seller_required(allow_buyer=False):
    if not current_user.is_authenticated:
        abort(401)
    role = (getattr(current_user, "role", "") or "").lower()
    allowed_roles = {"seller", "admin"}
    if allow_buyer:
        allowed_roles.add("buyer")
    if role not in allowed_roles:
        abort(403)


def _positive_int(field, label, default=None, allow_zero=False):
    raw = request.form.get(field, "").strip()
    if not raw and default is not None:
        return default
    if not raw:
        raise ValueError(f"{label} is required.")
    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a whole number.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} must be {'zero or greater' if allow_zero else 'greater than zero'}.")
    return value


def _form_values(service):
    values = {
        "registration_number": request.form.get("registration_number", "").strip().upper(),
        "brand": request.form.get("brand", "").strip(),
        "model": request.form.get("model", "").strip(),
        "year": _positive_int("year", "Year"),
        "mileage": _positive_int("mileage", "Mileage", default=0, allow_zero=True),
        "fuel": request.form.get("fuel", "").strip(),
        "transmission": request.form.get("transmission", "").strip(),
        "location": request.form.get("location", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "image_url": request.form.get("image_url", "").strip() or None,
    }
    for field, maximum in (("registration_number", 30), ("brand", 80), ("model", 100), ("fuel", 30), ("transmission", 30), ("location", 100)):
        if not values[field] or len(values[field]) > maximum:
            raise ValueError(f"Enter a valid {field.replace('_', ' ')} (maximum {maximum} characters).")
    if not 1900 <= values["year"] <= date.today().year + 1:
        raise ValueError("Enter a valid vehicle year.")
    if values["image_url"]:
        parsed = urlparse(values["image_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Vehicle image must be a valid http or https URL.")
    if values["description"] and len(values["description"]) > 4000:
        raise ValueError("Description must be 4,000 characters or fewer.")
    if service == "hire":
        values["daily_price"] = _positive_int("daily_price", "Daily hire price")
        values["weekly_price"] = _positive_int("weekly_price", "Weekly price", allow_zero=False) if request.form.get("weekly_price", "").strip() else None
        values["minimum_days"] = _positive_int("minimum_days", "Minimum hire days", default=1)
        values["security_deposit"] = _positive_int("security_deposit", "Security deposit", allow_zero=True) if request.form.get("security_deposit", "").strip() else None
    else:
        values["monthly_price"] = _positive_int("monthly_price", "Monthly lease price")
        values["minimum_months"] = _positive_int("minimum_months", "Minimum lease months", default=12)
        values["security_deposit"] = _positive_int("security_deposit", "Security deposit", allow_zero=True) if request.form.get("security_deposit", "").strip() else None
    return values


def _inventory(service):
    return HireVehicle if service == "hire" else LeaseVehicle


def _request_model(service):
    return HireServiceRequest if service == "hire" else LeaseServiceRequest


def _manage_endpoint(service):
    return "hire_lease.manage_hire" if service == "hire" else "hire_lease.manage_lease"


def _listing_endpoint(service):
    return "hire_lease.hire_listings" if service == "hire" else "hire_lease.lease_listings"


def _upload_service_image(image, service):
    """Upload one cover image to the existing private-configured Cloudinary account."""
    if not image or not image.filename or not image.filename.strip():
        return None
    filename = image.filename.strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Choose a JPG, JPEG, PNG or WEBP image.")
    if image.mimetype and not image.mimetype.lower().startswith("image/"):
        raise ValueError("The uploaded file must be an image.")

    # Reuse the same server-side Cloudinary configuration as sale listings.
    from routes.cars import configure_cloudinary
    settings = configure_cloudinary()
    image.stream.seek(0, os.SEEK_END)
    size = image.stream.tell()
    image.stream.seek(0)
    if size > 8 * 1024 * 1024:
        raise ValueError("The cover image must be 8 MB or smaller.")

    public_id = f"{service}_{uuid.uuid4().hex}"
    result = cloudinary.uploader.upload(
        image.stream,
        upload_preset=settings["upload_preset"],
        folder=f"carvion_motors/{service}",
        public_id=public_id,
        resource_type="image",
        overwrite=False,
        use_filename=False,
        unique_filename=False,
        secure=True,
    )
    image_url = result.get("secure_url")
    uploaded_public_id = result.get("public_id")
    if not image_url or not uploaded_public_id:
        if uploaded_public_id:
            try:
                cloudinary.uploader.destroy(uploaded_public_id, resource_type="image")
            except Exception:
                current_app.logger.exception("Could not clean up incomplete service image upload")
        raise RuntimeError("Cloudinary did not return the uploaded image details.")
    return image_url, uploaded_public_id


def _save_vehicle(service, vehicle=None):
    _seller_required(allow_buyer=True)
    model = _inventory(service)
    image = request.files.get("cover_image")
    try:
        values = _form_values(service)
        uploaded = _upload_service_image(image, service) if image and image.filename else None
        if uploaded:
            values["image_url"] = uploaded[0]
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for(_manage_endpoint(service), edit_id=vehicle.id if vehicle else None))
    except Exception:
        current_app.logger.exception("Failed to upload %s vehicle cover image", service)
        flash("The image could not be uploaded. Check your Cloudinary configuration and try again.", "danger")
        return redirect(url_for(_manage_endpoint(service), edit_id=vehicle.id if vehicle else None))

    creating_first_service_listing = vehicle is None
    if vehicle is None:
        vehicle = model(seller_id=current_user.id)
        db.session.add(vehicle)
    for key, value in values.items():
        setattr(vehicle, key, value)
    vehicle.status = vehicle.status if vehicle.status in {"Published", "Paused"} else "Published"
    # Match the existing marketplace onboarding: the first listing promotes a
    # buyer to seller, but only within the same transaction as the new listing.
    if creating_first_service_listing and (getattr(current_user, "role", "") or "").lower() == "buyer":
        current_user.role = "seller"
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if uploaded:
            try:
                cloudinary.uploader.destroy(uploaded[1], resource_type="image")
            except Exception:
                current_app.logger.exception("Could not clean up failed service image upload")
        flash("We could not save this vehicle. Please check the details and try again.", "danger")
        return redirect(url_for(_manage_endpoint(service)))
    flash(f"Your vehicle was saved in the separate {service} inventory.", "success")
    return redirect(url_for(_manage_endpoint(service)))


@hire_lease.route("/hire")
def hire_listings():
    listings = HireVehicle.query.filter_by(status="Published").order_by(HireVehicle.created_at.desc()).all()
    return render_template("service_listings.html", service="hire", listings=listings)


@hire_lease.route("/lease")
def lease_listings():
    listings = LeaseVehicle.query.filter_by(status="Published").order_by(LeaseVehicle.created_at.desc()).all()
    return render_template("service_listings.html", service="lease", listings=listings)


@hire_lease.route("/hire/manage")
@login_required
def manage_hire():
    _seller_required(allow_buyer=True)
    listings = HireVehicle.query.filter_by(seller_id=current_user.id).order_by(HireVehicle.created_at.desc()).all()
    edit_id = request.args.get("edit_id", type=int)
    vehicle = HireVehicle.query.filter_by(id=edit_id, seller_id=current_user.id).first() if edit_id else None
    return render_template("service_inventory.html", service="hire", listings=listings, vehicle=vehicle)


@hire_lease.route("/lease/manage")
@login_required
def manage_lease():
    _seller_required(allow_buyer=True)
    listings = LeaseVehicle.query.filter_by(seller_id=current_user.id).order_by(LeaseVehicle.created_at.desc()).all()
    edit_id = request.args.get("edit_id", type=int)
    vehicle = LeaseVehicle.query.filter_by(id=edit_id, seller_id=current_user.id).first() if edit_id else None
    return render_template("service_inventory.html", service="lease", listings=listings, vehicle=vehicle)


@hire_lease.route("/hire/manage/save", methods=["POST"])
@login_required
def save_hire():
    _seller_required(allow_buyer=True)
    edit_id = request.form.get("vehicle_id", type=int)
    vehicle = HireVehicle.query.filter_by(id=edit_id, seller_id=current_user.id).first() if edit_id else None
    if edit_id and vehicle is None:
        abort(404)
    return _save_vehicle("hire", vehicle)


@hire_lease.route("/lease/manage/save", methods=["POST"])
@login_required
def save_lease():
    _seller_required(allow_buyer=True)
    edit_id = request.form.get("vehicle_id", type=int)
    vehicle = LeaseVehicle.query.filter_by(id=edit_id, seller_id=current_user.id).first() if edit_id else None
    if edit_id and vehicle is None:
        abort(404)
    return _save_vehicle("lease", vehicle)


@hire_lease.route("/hire/manage/<int:vehicle_id>/status", methods=["POST"])
@login_required
def toggle_hire_status(vehicle_id):
    _seller_required()
    vehicle = HireVehicle.query.filter_by(id=vehicle_id, seller_id=current_user.id).first_or_404()
    vehicle.status = "Paused" if vehicle.status == "Published" else "Published"
    db.session.commit()
    flash(f"Hire listing is now {vehicle.status.lower()}.", "success")
    return redirect(url_for("hire_lease.manage_hire"))


@hire_lease.route("/lease/manage/<int:vehicle_id>/status", methods=["POST"])
@login_required
def toggle_lease_status(vehicle_id):
    _seller_required()
    vehicle = LeaseVehicle.query.filter_by(id=vehicle_id, seller_id=current_user.id).first_or_404()
    vehicle.status = "Paused" if vehicle.status == "Published" else "Published"
    db.session.commit()
    flash(f"Lease listing is now {vehicle.status.lower()}.", "success")
    return redirect(url_for("hire_lease.manage_lease"))


@hire_lease.route("/hire/vehicle/<int:vehicle_id>/request", methods=["GET", "POST"])
@login_required
def request_hire(vehicle_id):
    vehicle = HireVehicle.query.filter_by(id=vehicle_id, status="Published").first_or_404()
    if vehicle.seller_id == current_user.id:
        abort(403)
    if request.method == "POST":
        try:
            start = date.fromisoformat(request.form.get("start_date", ""))
            end = date.fromisoformat(request.form.get("end_date", ""))
            pickup = request.form.get("pickup_location", "").strip()
            message = request.form.get("message", "").strip() or None
            if start < date.today() or end < start:
                raise ValueError("Choose valid hire dates; the end date must not precede the start date.")
            days = (end - start).days + 1
            if days < vehicle.minimum_days:
                raise ValueError(f"Minimum hire period is {vehicle.minimum_days} day(s).")
            if not pickup or len(pickup) > 120:
                raise ValueError("Enter a pickup location (maximum 120 characters).")
            if message and len(message) > 2000:
                raise ValueError("Message must be 2,000 characters or fewer.")
        except (ValueError, TypeError) as error:
            flash(str(error) or "Enter valid hire dates.", "danger")
            return redirect(url_for("hire_lease.request_hire", vehicle_id=vehicle.id))
        db.session.add(HireServiceRequest(vehicle_id=vehicle.id, renter_id=current_user.id, seller_id=vehicle.seller_id, start_date=start, end_date=end, pickup_location=pickup, message=message))
        db.session.commit()
        flash("Hire request sent. It is pending and is not a confirmed booking.", "success")
        return redirect(url_for("hire_lease.hire_listings"))
    return render_template("service_request_form.html", service="hire", vehicle=vehicle, today=date.today().isoformat())


@hire_lease.route("/lease/vehicle/<int:vehicle_id>/request", methods=["GET", "POST"])
@login_required
def request_lease(vehicle_id):
    vehicle = LeaseVehicle.query.filter_by(id=vehicle_id, status="Published").first_or_404()
    if vehicle.seller_id == current_user.id:
        abort(403)
    if request.method == "POST":
        try:
            start = date.fromisoformat(request.form.get("requested_start_date", ""))
            duration = _positive_int("duration_months", "Lease duration")
            location = request.form.get("location", "").strip()
            message = request.form.get("message", "").strip() or None
            if start < date.today():
                raise ValueError("The requested lease start date cannot be in the past.")
            if duration < vehicle.minimum_months:
                raise ValueError(f"Minimum lease term is {vehicle.minimum_months} month(s).")
            if not location or len(location) > 120:
                raise ValueError("Enter a location (maximum 120 characters).")
            if message and len(message) > 2000:
                raise ValueError("Message must be 2,000 characters or fewer.")
        except (ValueError, TypeError) as error:
            flash(str(error) or "Enter valid lease details.", "danger")
            return redirect(url_for("hire_lease.request_lease", vehicle_id=vehicle.id))
        db.session.add(LeaseServiceRequest(vehicle_id=vehicle.id, renter_id=current_user.id, seller_id=vehicle.seller_id, requested_start_date=start, duration_months=duration, location=location, message=message))
        db.session.commit()
        flash("Lease enquiry sent. No lease agreement has been created.", "success")
        return redirect(url_for("hire_lease.lease_listings"))
    return render_template("service_request_form.html", service="lease", vehicle=vehicle, today=date.today().isoformat())


@hire_lease.route("/seller/hire-lease-requests")
@login_required
def seller_requests():
    _seller_required()
    hire_requests = HireServiceRequest.query.filter_by(seller_id=current_user.id).order_by(HireServiceRequest.created_at.desc()).all()
    lease_requests = LeaseServiceRequest.query.filter_by(seller_id=current_user.id).order_by(LeaseServiceRequest.created_at.desc()).all()
    return render_template("service_requests_inbox.html", hire_requests=hire_requests, lease_requests=lease_requests)


@hire_lease.route("/hire/requests/<int:request_id>/respond", methods=["POST"])
@login_required
def respond_hire_request(request_id):
    _seller_required()
    item = HireServiceRequest.query.filter_by(id=request_id, seller_id=current_user.id).first_or_404()
    return _respond(item, "hire")


@hire_lease.route("/lease/requests/<int:request_id>/respond", methods=["POST"])
@login_required
def respond_lease_request(request_id):
    _seller_required()
    item = LeaseServiceRequest.query.filter_by(id=request_id, seller_id=current_user.id).first_or_404()
    return _respond(item, "lease")


def _add_months(start_date, months):
    """Return the date the lease period ends, clamping month-end dates safely."""
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _hire_request_conflicts(item):
    """Check whether another accepted hire request overlaps this vehicle's dates."""
    return HireServiceRequest.query.filter(
        HireServiceRequest.vehicle_id == item.vehicle_id,
        HireServiceRequest.status == "Accepted",
        HireServiceRequest.id != item.id,
        HireServiceRequest.start_date <= item.end_date,
        HireServiceRequest.end_date >= item.start_date,
    ).first() is not None


def _lease_request_conflicts(item):
    """Check accepted lease periods as half-open [start, end) date ranges."""
    requested_end = _add_months(item.requested_start_date, item.duration_months)
    accepted_items = LeaseServiceRequest.query.filter(
        LeaseServiceRequest.vehicle_id == item.vehicle_id,
        LeaseServiceRequest.status == "Accepted",
        LeaseServiceRequest.id != item.id,
    ).all()
    for accepted in accepted_items:
        accepted_end = _add_months(
            accepted.requested_start_date,
            accepted.duration_months,
        )
        if accepted.requested_start_date < requested_end and accepted_end > item.requested_start_date:
            return True
    return False


def _respond(item, service):
    action = request.form.get("action", "").strip().lower()
    response = request.form.get("seller_response", "").strip()
    if action not in {"accept", "decline", "respond"}:
        abort(400)
    if len(response) > 2000:
        flash("Response must be 2,000 characters or fewer.", "danger")
        return redirect(url_for("hire_lease.seller_requests"))
    if action == "accept":
        has_conflict = (
            _hire_request_conflicts(item)
            if service == "hire"
            else _lease_request_conflicts(item)
        )
        if has_conflict:
            flash(
                "This vehicle already has an accepted request for an overlapping period. "
                "Decline or resolve the conflicting request before accepting this one.",
                "danger",
            )
            return redirect(url_for("hire_lease.seller_requests"))
        item.status = "Accepted"
        item.seller_response = response or "The seller has accepted your enquiry. Contact the seller to agree on next steps."
    elif action == "decline":
        item.status = "Declined"
        item.seller_response = response or "The seller is unable to proceed with this request."
    else:
        item.seller_response = response
    db.session.commit()
    flash("Response saved. This does not confirm a hire booking or create a lease agreement.", "success")
    return redirect(url_for("hire_lease.seller_requests"))
