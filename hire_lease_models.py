"""Separate data models for Carvion Motors hire and lease services.

These tables are deliberately separate from the existing cars table so that
adding hire/lease capability does not require altering existing vehicle rows.
"""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db, utcnow


class CarHireOption(db.Model):
    """Hire pricing and availability configured for an existing vehicle."""

    __tablename__ = "car_hire_options"
    __table_args__ = (
        UniqueConstraint("car_id", name="uq_car_hire_option_car"),
        CheckConstraint("daily_price > 0", name="ck_hire_daily_price_positive"),
        CheckConstraint(
            "weekly_price IS NULL OR weekly_price > 0",
            name="ck_hire_weekly_price_positive",
        ),
        CheckConstraint(
            "minimum_days >= 1",
            name="ck_hire_minimum_days_positive",
        ),
        CheckConstraint(
            "security_deposit IS NULL OR security_deposit >= 0",
            name="ck_hire_deposit_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    daily_price = db.Column(db.Integer, nullable=False)
    weekly_price = db.Column(db.Integer, nullable=True)
    minimum_days = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    security_deposit = db.Column(db.Integer, nullable=True)
    available = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    car = db.relationship("Car")


class CarLeaseOption(db.Model):
    """Monthly lease pricing and minimum term for an existing vehicle."""

    __tablename__ = "car_lease_options"
    __table_args__ = (
        UniqueConstraint("car_id", name="uq_car_lease_option_car"),
        CheckConstraint("monthly_price > 0", name="ck_lease_monthly_price_positive"),
        CheckConstraint(
            "minimum_months >= 1",
            name="ck_lease_minimum_months_positive",
        ),
        CheckConstraint(
            "security_deposit IS NULL OR security_deposit >= 0",
            name="ck_lease_deposit_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monthly_price = db.Column(db.Integer, nullable=False)
    minimum_months = db.Column(
        db.Integer,
        nullable=False,
        default=12,
        server_default="12",
    )
    security_deposit = db.Column(db.Integer, nullable=True)
    available = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    car = db.relationship("Car")


class HireRequest(db.Model):
    """A customer's requested hire period; does not itself confirm a booking."""

    __tablename__ = "hire_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_hire_request_date_order"),
        CheckConstraint(
            "estimated_total IS NULL OR estimated_total >= 0",
            name="ck_hire_request_total_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    renter_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    pickup_location = db.Column(db.String(120), nullable=False)
    return_location = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=True)
    estimated_total = db.Column(db.Integer, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
        server_default="Pending",
        index=True,
    )
    seller_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    car = db.relationship("Car")
    renter = db.relationship("User", foreign_keys=[renter_id])
    seller = db.relationship("User", foreign_keys=[seller_id])


class LeaseRequest(db.Model):
    """A customer's lease enquiry; does not itself create a lease agreement."""

    __tablename__ = "lease_requests"
    __table_args__ = (
        CheckConstraint(
            "duration_months >= 1",
            name="ck_lease_request_duration_positive",
        ),
        CheckConstraint(
            "requested_monthly_budget IS NULL OR requested_monthly_budget > 0",
            name="ck_lease_request_budget_positive",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    renter_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_start_date = db.Column(db.Date, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    requested_monthly_budget = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
        server_default="Pending",
        index=True,
    )
    seller_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    car = db.relationship("Car")
    renter = db.relationship("User", foreign_keys=[renter_id])
    seller = db.relationship("User", foreign_keys=[seller_id])
