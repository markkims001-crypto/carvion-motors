"""Seller controls for configuring car hire and lease pricing."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from hire_lease_models import CarHireOption, CarLeaseOption
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

        flash("Hire and lease settings saved. Customers can send requests; bookings are not confirmed automatically.", "success")
        return redirect(url_for("hire_lease.manage_options", car_id=car.id))

    return render_template(
        "manage_hire_lease.html",
        car=car,
        hire_option=hire_option,
        lease_option=lease_option,
    )
