"""Opt-in saved vehicle searches and deduplicated in-app alert events."""
from extensions import db

class SavedVehicleSearch(db.Model):
    __tablename__ = "saved_vehicle_searches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    max_price = db.Column(db.Integer, nullable=True)
    min_year = db.Column(db.Integer, nullable=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def matches(self, car):
        return (not self.brand or self.brand.casefold() in car.brand.casefold()) and (
            not self.location or self.location.casefold() in car.location.casefold()
        ) and (self.max_price is None or car.price <= self.max_price) and (
            self.min_year is None or car.year >= self.min_year
        )

class VehicleAlertEvent(db.Model):
    __tablename__ = "vehicle_alert_events"
    id = db.Column(db.Integer, primary_key=True)
    search_id = db.Column(db.Integer, db.ForeignKey("saved_vehicle_searches.id"), nullable=False)
    car_id = db.Column(db.Integer, db.ForeignKey("cars.id"), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    __table_args__ = (db.UniqueConstraint("search_id", "car_id", "event_type", name="uq_vehicle_alert_event"),)
