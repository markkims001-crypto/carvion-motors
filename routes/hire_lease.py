"""Public discovery and customer request flows for vehicle hire and lease."""

from datetime import date
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from hire_lease_models import CarHireOption, CarLeaseOption, HireRequest, LeaseRequest
from models import Car

hire_lease = Blueprint("hire_lease", __name__)


def _optional_positive_int(field_name, label, allow_zero=False):
    raw = request.form.get(field_name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "zero or greater" if allow_zero else "greater than zero"
        raise ValueError(f"{label} must be {qualifier}.")
    return value


def _public_car_or_404(car_id):
    car = Car.query.filter_by(id=car_id, status="Approved").first()
    if car is None:
        abort(404)
    return car


def _requester_can_request(car):
    if car.seller_id == current_user.id:
        flash("You cannot request your own vehicle.", "warning")
        return False
    return True


@hire_lease.route("/car/<int:car_id>/hire-lease", methods=["GET", "POST"])
@login_required
def manage_options(car_id):
    car = Car.query.get_or_404(car_id)

    if car.seller_id != current_user.id:
        flash("You are not allowed to manage hire or lease settings for this vehicle.", "danger")
        return redirect(url_for("cars.seller_dashboard"))

    hire_option = CarHireOption.query.filter_by(car_id=car.id).first()
    lease_option = CarLeaseOption.query.filter_by(car_id=car.id).first()

    if request.method == "POST":
        hire_enabled = request.form.get("hire_enabled") == "on"
        lease_enabled = request.form.get("lease_enabled") == "on"

        try:
            if hire_enabled:
                daily_price = _optional_positive_int("daily_price", "Daily hire price")
                weekly_price = _optional_positive_int("weekly_price", "Weekly hire price")
                minimum_days = _optional_positive_int("minimum_days", "Minimum hire days")
                minimum_days = 1 if minimum_days is None else minimum_days
                hire_deposit = _optional_positive_int("hire_security_deposit", "Hire security deposit", allow_zero=True)
                if daily_price is None:
                    raise ValueError("Enter a daily hire price to enable car hire.")
                if minimum_days < 1:
                    raise ValueError("Minimum hire days must be at least 1.")

            if lease_enabled:
                monthly_price = _optional_positive_int("monthly_price", "Monthly lease price")
                minimum_months = _optional_positive_int("minimum_months", "Minimum lease months")
                minimum_months = 12 if minimum_months is None else minimum_months
                lease_deposit = _optional_positive_int("lease_security_deposit", "Lease security deposit", allow_zero=True)
                if monthly_price is None:
                    raise ValueError("Enter a monthly lease price to enable car lease.")
                if minimum_months < 1:
                    raise ValueError("Minimum lease months must be at least 1.")
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("hire_lease.manage_options", car_id=car.id))

        try:
            if hire_enabled:
                if hire_option is None:
                    hire_option = CarHireOption(car_id=car.id, daily_price=daily_price)
                    db.session.add(hire_option)
                hire_option.daily_price = daily_price
                hire_option.weekly_price = weekly_price
                hire_option.minimum_days = minimum_days
                hire_option.security_deposit = hire_deposit
                hire_option.available = True
            elif hire_option is not None:
                hire_option.available = False

            if lease_enabled:
                if lease_option is None:
                    lease_option = CarLeaseOption(car_id=car.id, monthly_price=monthly_price)
                    db.session.add(lease_option)
                lease_option.monthly_price = monthly_price
                lease_option.minimum_months = minimum_months
                lease_option.security_deposit = lease_deposit
                lease_option.available = True
            elif lease_option is not None:
                lease_option.available = False

            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("We could not save these settings. Please try again.", "danger")
            return redirect(url_for("hire_lease.manage_options", car_id=car.id))

        flash("Hire and lease settings saved. A customer request will not automatically confirm a booking.", "success")
        return redirect(url_for("hire_lease.manage_options", car_id=car.id))

    return render_template(
        "manage_hire_lease.html",
        car=car,
        hire_option=hire_option,
        lease_option=lease_option,
    )


@hire_lease.route("/hire")
def hire_listings():
    listings = (
        db.session.query(Car, CarHireOption)
        .join(CarHireOption, CarHireOption.car_id == Car.id)
        .filter(Car.status == "Approved", CarHireOption.available.is_(True))
        .order_by(Car.created_at.desc())
        .all()
    )
    return render_template("hire_listings.html", listings=listings)


@hire_lease.route("/lease")
def lease_listings():
    listings = (
        db.session.query(Car, CarLeaseOption)
        .join(CarLeaseOption, CarLeaseOption.car_id == Car.id)
        .filter(Car.status == "Approved", CarLeaseOption.available.is_(True))
        .order_by(Car.created_at.desc())
        .all()
    )
    return render_template("lease_listings.html", listings=listings)


@hire_lease.route("/car/<int:car_id>/hire-request", methods=["GET", "POST"])
@login_required
def request_hire(car_id):
    car = _public_car_or_404(car_id)
    option = CarHireOption.query.filter_by(car_id=car.id, available=True).first_or_404()

    if not _requester_can_request(car):
        return redirect(url_for("hire_lease.hire_listings"))

    if request.method == "POST":
        try:
            start_date = date.fromisoformat(request.form.get("start_date", "").strip())
            end_date = date.fromisoformat(request.form.get("end_date", "").strip())
            pickup_location = request.form.get("pickup_location", "").strip()
            return_location = request.form.get("return_location", "").strip() or None
            message = request.form.get("message", "").strip() or None

            if start_date < date.today():
                raise ValueError("The start date cannot be in the past.")
            if end_date < start_date:
                raise ValueError("The return date must be on or after the start date.")
            days = (end_date - start_date).days + 1
            if days < option.minimum_days:
                raise ValueError(f"This vehicle requires a minimum hire period of {option.minimum_days} day(s).")
            if not pickup_location or len(pickup_location) > 120:
                raise ValueError("Enter a pickup location (maximum 120 characters).")
            if return_location and len(return_location) > 120:
                raise ValueError("Return location must be 120 characters or fewer.")
            if message and len(message) > 2000:
                raise ValueError("Message must be 2,000 characters or fewer.")
        except (ValueError, TypeError) as error:
            flash(str(error) or "Enter valid hire dates.", "danger")
            return redirect(url_for("hire_lease.request_hire", car_id=car.id))

        hire_request = HireRequest(
            car_id=car.id,
            renter_id=current_user.id,
            seller_id=car.seller_id,
            start_date=start_date,
            end_date=end_date,
            pickup_location=pickup_location,
            return_location=return_location,
            message=message,
            estimated_total=days * option.daily_price,
            status="Pending",
        )
        try:
            db.session.add(hire_request)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("We could not submit your request. Please try again.", "danger")
            return redirect(url_for("hire_lease.request_hire", car_id=car.id))

        flash("Your hire request was sent to the seller. It is pending and is not a confirmed booking.", "success")
        return redirect(url_for("hire_lease.hire_listings"))

    return render_template("hire_request.html", car=car, option=option, today=date.today().isoformat())


@hire_lease.route("/car/<int:car_id>/lease-request", methods=["GET", "POST"])
@login_required
def request_lease(car_id):
    car = _public_car_or_404(car_id)
    option = CarLeaseOption.query.filter_by(car_id=car.id, available=True).first_or_404()

    if not _requester_can_request(car):
        return redirect(url_for("hire_lease.lease_listings"))

    if request.method == "POST":
        try:
            requested_start_date = date.fromisoformat(request.form.get("requested_start_date", "").strip())
            duration_months = _optional_positive_int("duration_months", "Lease duration")
            budget = _optional_positive_int("requested_monthly_budget", "Monthly budget")
            location = request.form.get("location", "").strip()
            message = request.form.get("message", "").strip() or None

            if requested_start_date < date.today():
                raise ValueError("The requested start date cannot be in the past.")
            if duration_months is None or duration_months < option.minimum_months:
                raise ValueError(f"This vehicle requires a lease of at least {option.minimum_months} month(s).")
            if not location or len(location) > 120:
                raise ValueError("Enter a location (maximum 120 characters).")
            if message and len(message) > 2000:
                raise ValueError("Message must be 2,000 characters or fewer.")
        except (ValueError, TypeError) as error:
            flash(str(error) or "Enter valid lease details.", "danger")
            return redirect(url_for("hire_lease.request_lease", car_id=car.id))

        lease_request = LeaseRequest(
            car_id=car.id,
            renter_id=current_user.id,
            seller_id=car.seller_id,
            requested_start_date=requested_start_date,
            duration_months=duration_months,
            requested_monthly_budget=budget,
            location=location,
            message=message,
            status="Pending",
        )
        try:
            db.session.add(lease_request)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("We could not submit your request. Please try again.", "danger")
            return redirect(url_for("hire_lease.request_lease", car_id=car.id))

        flash("Your lease enquiry was sent to the seller. It is pending and is not a confirmed lease.", "success")
        return redirect(url_for("hire_lease.lease_listings"))

    return render_template("lease_request.html", car=car, option=option, today=date.today().isoformat())


def _seller_only():
    if (getattr(current_user, "role", "") or "").lower() != "seller":
        flash("Seller access required.", "danger")
        return False
    return True


@hire_lease.route("/seller/hire-lease-requests")
@login_required
def seller_requests():
    if not _seller_only():
        return redirect(url_for("home"))

    hire_requests = (
        HireRequest.query.filter_by(seller_id=current_user.id)
        .order_by(HireRequest.created_at.desc()).all()
    )
    lease_requests = (
        LeaseRequest.query.filter_by(seller_id=current_user.id)
        .order_by(LeaseRequest.created_at.desc()).all()
    )
    return render_template(
        "seller_hire_lease_requests.html",
        hire_requests=hire_requests,
        lease_requests=lease_requests,
    )


@hire_lease.route("/seller/hire-lease-requests/<string:request_type>/<int:request_id>", methods=["POST"])
@login_required
def respond_to_request(request_type, request_id):
    if not _seller_only():
        return redirect(url_for("home"))

    if request_type == "hire":
        item = HireRequest.query.filter_by(id=request_id, seller_id=current_user.id).first_or_404()
    elif request_type == "lease":
        item = LeaseRequest.query.filter_by(id=request_id, seller_id=current_user.id).first_or_404()
    else:
        abort(404)

    action = request.form.get("action", "").strip().lower()
    response_text = request.form.get("seller_response", "").strip()
    if action not in {"accept", "decline", "respond"}:
        abort(400)
    if len(response_text) > 2000:
        flash("Your response must be 2,000 characters or fewer.", "danger")
        return redirect(url_for("hire_lease.seller_requests"))

    if item.status != "Pending" and action in {"accept", "decline"}:
        flash("Only pending requests can be accepted or declined.", "warning")
        return redirect(url_for("hire_lease.seller_requests"))

    if action == "accept":
        item.status = "Accepted"
        item.seller_response = response_text or "The seller has accepted this request. This is not a confirmed booking or lease."
        message = "Request marked accepted. No booking, payment, or lease agreement has been created."
    elif action == "decline":
        item.status = "Declined"
        item.seller_response = response_text or "The seller has declined this request."
        message = "Request declined."
    else:
        if not response_text:
            flash("Enter a response before submitting.", "warning")
            return redirect(url_for("hire_lease.seller_requests"))
        item.seller_response = response_text
        message = "Your response was saved."

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("We could not update this request. Please try again.", "danger")
        return redirect(url_for("hire_lease.seller_requests"))

    flash(message, "success")
    return redirect(url_for("hire_lease.seller_requests"))
