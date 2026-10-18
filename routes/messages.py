"""Legacy inquiry-message endpoint retained for older templates.

New buyer/seller conversations use routes.chat. This endpoint remains
compatible with existing forms while applying the same access checks.
"""

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Inquiry, InquiryMessage, User


messages = Blueprint("messages", __name__, url_prefix="/messages")


def _back_to_inquiry(inquiry_id):
    """Use a known local destination when no referrer is provided."""
    return redirect(
        request.referrer
        or url_for("chat.inquiry_chat", inquiry_id=inquiry_id)
    )


@messages.route("/send/<int:inquiry_id>", methods=["POST"])
@login_required
def send_message(inquiry_id):
    inquiry = db.session.get(Inquiry, inquiry_id)
    if inquiry is None:
        flash("Inquiry not found.", "warning")
        return redirect(url_for("home"))

    text = (request.form.get("message") or "").strip()
    if not text:
        flash("Message cannot be empty.", "warning")
        return _back_to_inquiry(inquiry_id)

    if len(text) > 5000:
        flash("Message is too long. Please keep it under 5,000 characters.", "warning")
        return _back_to_inquiry(inquiry_id)

    role = (getattr(current_user, "role", "") or "").strip().lower()

    if role == "admin":
        # Administrators can respond only to the inquiry's known participants.
        receiver_id = (
            inquiry.buyer_id
            if inquiry.buyer_id != current_user.id
            else inquiry.seller_id
        )
    elif current_user.id in (inquiry.buyer_id, inquiry.seller_id):
        # Preserve the legacy workflow: buyer/seller messages are routed to an admin.
        admin_user = User.query.filter(
            db.func.lower(User.role) == "admin"
        ).first()
        if admin_user is None:
            flash("No administrator is currently available.", "warning")
            return _back_to_inquiry(inquiry_id)
        receiver_id = admin_user.id
    else:
        flash("Permission denied.", "danger")
        return redirect(url_for("home"))

    if receiver_id is None:
        flash("The message recipient could not be found.", "warning")
        return _back_to_inquiry(inquiry_id)

    try:
        message = InquiryMessage(
            inquiry_id=inquiry.id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            sender_role=role,
            message=text,
        )
        db.session.add(message)
        inquiry.status = "Replied"
        db.session.commit()
    except Exception:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception("Legacy inquiry message could not be saved.")
        flash("Your message could not be sent. Please try again.", "danger")
        return _back_to_inquiry(inquiry_id)

    flash("Message sent.", "success")
    return _back_to_inquiry(inquiry_id)
