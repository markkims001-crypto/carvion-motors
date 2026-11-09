"""Dealership profiles; separate from buyer/seller authorization roles."""
from extensions import db


class Dealership(db.Model):
    __tablename__ = "dealerships"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(150), nullable=False, unique=True, index=True)
    location = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    logo_url = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    owner = db.relationship("User", backref=db.backref("dealership", uselist=False))
