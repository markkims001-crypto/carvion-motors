"""Account-independent seller identities and controlled claim requests.

These tables are additive. Existing users, cars, and dealerships are unchanged.
"""
from extensions import db


class SellerProfile(db.Model):
    __tablename__ = "seller_profiles"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)  # individual / dealership
    display_name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(160), nullable=False)
    public_phone = db.Column(db.String(20), nullable=True)
    private_phone = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    claimed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assistance_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    advertising_consent_recorded = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    claimant = db.relationship("User", foreign_keys=[claimed_by_user_id])
    creator = db.relationship("User", foreign_keys=[created_by_admin_id])
    claim_requests = db.relationship("SellerProfileClaim", back_populates="profile")

    @property
    def is_claimed(self):
        return self.claimed_by_user_id is not None

    def can_manage(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if self.claimed_by_user_id == user.id:
            return True
        return user.role == "admin" and (
            self.claimed_by_user_id is None or self.assistance_enabled
        )


class SellerProfileClaim(db.Model):
    __tablename__ = "seller_profile_claims"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("seller_profiles.id"), nullable=False, index=True)
    requesting_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    review_notes = db.Column(db.Text, nullable=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    reviewed_at = db.Column(db.DateTime, nullable=True)

    profile = db.relationship("SellerProfile", back_populates="claim_requests")
    requester = db.relationship("User", foreign_keys=[requesting_user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_admin_id])


class SellerProfileAudit(db.Model):
    __tablename__ = "seller_profile_audit"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("seller_profiles.id"), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
