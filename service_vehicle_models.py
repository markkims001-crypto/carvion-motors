"""Independent inventory and enquiries for Carvion Motors hire and lease services.

These models intentionally do not reference the sale-marketplace Car table. A
vehicle listed here exists only in its own service inventory unless separately
created as a sale listing.
"""
from datetime import datetime
from sqlalchemy import CheckConstraint
from extensions import db


class HireVehicle(db.Model):
    __tablename__ = "hire_vehicles"
    __table_args__ = (
        CheckConstraint("daily_price > 0", name="ck_hire_vehicle_daily_price"),
        CheckConstraint("minimum_days >= 1", name="ck_hire_vehicle_min_days"),
        CheckConstraint("security_deposit IS NULL OR security_deposit >= 0", name="ck_hire_vehicle_deposit"),
    )

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_number = db.Column(db.String(30), nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False, default=0)
    fuel = db.Column(db.String(30), nullable=False)
    transmission = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(1000))
    daily_price = db.Column(db.Integer, nullable=False)
    weekly_price = db.Column(db.Integer)
    minimum_days = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    security_deposit = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="Published", server_default="Published", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    seller = db.relationship("User", foreign_keys=[seller_id])


class LeaseVehicle(db.Model):
    __tablename__ = "lease_vehicles"
    __table_args__ = (
        CheckConstraint("monthly_price > 0", name="ck_lease_vehicle_monthly_price"),
        CheckConstraint("minimum_months >= 1", name="ck_lease_vehicle_min_months"),
        CheckConstraint("security_deposit IS NULL OR security_deposit >= 0", name="ck_lease_vehicle_deposit"),
    )

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_number = db.Column(db.String(30), nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False, default=0)
    fuel = db.Column(db.String(30), nullable=False)
    transmission = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(1000))
    monthly_price = db.Column(db.Integer, nullable=False)
    minimum_months = db.Column(db.Integer, nullable=False, default=12, server_default="12")
    security_deposit = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="Published", server_default="Published", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    seller = db.relationship("User", foreign_keys=[seller_id])


class HireServiceRequest(db.Model):
    __tablename__ = "hire_service_requests"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("hire_vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    renter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    pickup_location = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Pending", server_default="Pending", index=True)
    seller_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    vehicle = db.relationship("HireVehicle")
    renter = db.relationship("User", foreign_keys=[renter_id])
    seller = db.relationship("User", foreign_keys=[seller_id])


class LeaseServiceRequest(db.Model):
    __tablename__ = "lease_service_requests"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("lease_vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    renter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_start_date = db.Column(db.Date, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Pending", server_default="Pending", index=True)
    seller_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    vehicle = db.relationship("LeaseVehicle")
    renter = db.relationship("User", foreign_keys=[renter_id])
    seller = db.relationship("User", foreign_keys=[seller_id])


class ServiceRequestMessage(db.Model):
    """Persistent two-way conversation messages for a hire request or lease enquiry."""
    __tablename__ = "service_request_messages"
    __table_args__ = (
        CheckConstraint("service IN ('hire', 'lease')", name="ck_service_request_message_service"),
        CheckConstraint("length(trim(body)) > 0", name="ck_service_request_message_body"),
    )

    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(10), nullable=False, index=True)
    request_id = db.Column(db.Integer, nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = db.Column(db.String(2000), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])
