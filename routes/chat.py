
# routes/chat.py

from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)

from flask_login import login_required, current_user

from extensions import db

from models import (
    User,
    Car,
    Inquiry,
    InquiryMessage,
    Conversation,
    Message,
    Notification,
)


# ============================================================
# BLUEPRINT
# ============================================================

chat = Blueprint("chat", __name__)


# ============================================================
# HELPERS
# ============================================================

def normalized_role(user):
    """Return a normalized role for consistent permission checks."""
    return (getattr(user, "role", "") or "").strip().lower()


def get_admin():
    """Get the first registered administrator."""
    return User.query.filter(
        db.func.lower(User.role) == "admin"
    ).first()


def allowed_direct_chat(user1, user2):
    """Allow administrator chats with buyers and sellers."""
    if not user1 or not user2:
        return False

    roles = {normalized_role(user1), normalized_role(user2)}

    return (
        "admin" in roles
        and bool(roles.intersection({"buyer", "seller"}))
    )


def get_or_create_conversation(user1_id, user2_id):
    """Find an existing conversation or create one."""
    conversation = Conversation.query.filter(
        db.or_(
            db.and_(
                Conversation.user1_id == user1_id,
                Conversation.user2_id == user2_id,
            ),
            db.and_(
                Conversation.user1_id == user2_id,
                Conversation.user2_id == user1_id,
            ),
        )
    ).first()

    if conversation:
        return conversation

    conversation = Conversation(
        user1_id=user1_id,
        user2_id=user2_id,
    )

    db.session.add(conversation)
    db.session.flush()

    return conversation


def get_or_create_inquiry(car, buyer_id):
    """
    Return the existing inquiry for this buyer and vehicle,
    or create and flush a new one.
    """
    inquiry = Inquiry.query.filter_by(
        car_id=car.id,
        buyer_id=buyer_id,
        seller_id=car.seller_id,
    ).first()

    if inquiry is None:
        inquiry = Inquiry(
            car_id=car.id,
            buyer_id=buyer_id,
            seller_id=car.seller_id,
            status="Open",
        )
        db.session.add(inquiry)
        db.session.flush()

    return inquiry


def send_inquiry_message(inquiry, sender, message_text):
    """
    Save a message and notify the other participant.
    The caller must commit the transaction.
    """
    if sender.id == inquiry.buyer_id:
        receiver_id = inquiry.seller_id
    elif sender.id == inquiry.seller_id:
        receiver_id = inquiry.buyer_id
    else:
        raise PermissionError(
            "You are not a participant in this inquiry."
        )

    message = InquiryMessage(
        inquiry_id=inquiry.id,
        sender_id=sender.id,
        receiver_id=receiver_id,
        sender_role=normalized_role(sender),
        message=message_text,
        is_read=False,
    )

    db.session.add(message)

    inquiry.status = "Open"
    inquiry.updated_at = datetime.utcnow()

    notification = Notification(
        user_id=receiver_id,
        car_id=inquiry.car_id,
        title="New Inquiry Message",
        message=(
            f"{sender.name} sent you a message about "
            f"{inquiry.car.brand} {inquiry.car.model}."
        ),
        notification_type="inquiry",
        is_read=False,
    )

    db.session.add(notification)

    return message


def safe_flash_error(message, error):
    """Log database errors without exposing technical details to users."""
    db.session.rollback()
    current_app.logger.exception(
        "%s: %s",
        message,
        str(error),
    )
    flash(message, "danger")


# ============================================================
# BUYER / SELLER INQUIRY CHAT
# ============================================================

@chat.route(
    "/chat/inquiry/<int:inquiry_id>",
    methods=["GET", "POST"],
)
@login_required
def inquiry_chat(inquiry_id):
    inquiry = db.session.get(Inquiry, inquiry_id)

    if inquiry is None:
        flash("Inquiry not found.", "danger")
        return redirect(url_for("cars.all_cars"))

    if current_user.id not in (
        inquiry.buyer_id,
        inquiry.seller_id,
    ):
        flash(
            "You are not authorized to view this conversation.",
            "danger",
        )
        return redirect(url_for("cars.all_cars"))

    if request.method == "POST":
        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")
            return redirect(
                url_for(
                    "chat.inquiry_chat",
                    inquiry_id=inquiry.id,
                )
            )

        try:
            send_inquiry_message(
                inquiry,
                current_user,
                message_text,
            )

            db.session.commit()
            flash("Message sent successfully.", "success")

        except Exception as error:
            safe_flash_error(
                "Your message could not be sent. Please try again.",
                error,
            )

        return redirect(
            url_for(
                "chat.inquiry_chat",
                inquiry_id=inquiry_id,
            )
        )

    try:
        InquiryMessage.query.filter(
            InquiryMessage.inquiry_id == inquiry.id,
            InquiryMessage.receiver_id == current_user.id,
            InquiryMessage.is_read.is_(False),
        ).update(
            {"is_read": True},
            synchronize_session=False,
        )

        db.session.commit()

        messages = InquiryMessage.query.filter_by(
            inquiry_id=inquiry.id,
        ).order_by(
            InquiryMessage.created_at.asc(),
            InquiryMessage.id.asc(),
        ).all()

    except Exception as error:
        safe_flash_error(
            "Unable to load the conversation.",
            error,
        )
        return redirect(url_for("cars.all_cars"))

    return render_template(
        "chat/inquiry_chat.html",
        inquiry=inquiry,
        messages=messages,
    )


# ============================================================
# START OR CONTINUE A VEHICLE INQUIRY
# ============================================================

@chat.route(
    "/chat/car/<int:car_id>",
    methods=["GET", "POST"],
)
@login_required
def start_car_chat(car_id):
    car = db.session.get(Car, car_id)

    if car is None:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("cars.all_cars"))

    if normalized_role(current_user) != "buyer":
        flash(
            "Only buyers can start vehicle inquiries.",
            "warning",
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    if not car.seller_id or not car.seller:
        flash("This vehicle has no assigned seller.", "danger")
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    if car.seller_id == current_user.id:
        flash(
            "You cannot inquire about your own vehicle.",
            "warning",
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    try:
        inquiry = get_or_create_inquiry(
            car,
            current_user.id,
        )

        if request.method == "POST":
            message_text = request.form.get(
                "message", ""
            ).strip()

            if not message_text:
                db.session.commit()
                flash("Message cannot be empty.", "warning")
                return redirect(
                    url_for(
                        "chat.inquiry_chat",
                        inquiry_id=inquiry.id,
                    )
                )

            send_inquiry_message(
                inquiry,
                current_user,
                message_text,
            )

        # Commit the inquiry even if this request is a GET.
        db.session.commit()

        if request.method == "POST":
            flash("Your inquiry has been sent.", "success")

        return redirect(
            url_for(
                "chat.inquiry_chat",
                inquiry_id=inquiry.id,
            )
        )

    except Exception as error:
        safe_flash_error(
            "We could not process your inquiry. Please try again.",
            error,
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )


# ============================================================
# BUYER INQUIRIES
# ============================================================

@chat.route("/chat/my-inquiries")
@login_required
def my_inquiries():
    if normalized_role(current_user) != "buyer":
        flash("Buyer access required.", "warning")
        return redirect(url_for("cars.all_cars"))

    inquiries = Inquiry.query.filter_by(
        buyer_id=current_user.id,
    ).order_by(
        Inquiry.updated_at.desc(),
        Inquiry.id.desc(),
    ).all()

    return render_template(
        "chat/my_inquiries.html",
        inquiries=inquiries,
    )


# ============================================================
# SELLER INQUIRIES
# ============================================================

@chat.route("/chat/seller-inquiries")
@login_required
def seller_inquiries_chat():
    if normalized_role(current_user) != "seller":
        flash("Seller access required.", "danger")
        return redirect(url_for("cars.all_cars"))

    inquiries = Inquiry.query.filter_by(
        seller_id=current_user.id,
    ).order_by(
        Inquiry.updated_at.desc(),
        Inquiry.id.desc(),
    ).all()

    return render_template(
        "chat/seller_inquiries.html",
        inquiries=inquiries,
    )


# ============================================================
# BUYER / SELLER <-> ADMIN DIRECT CHAT
# ============================================================

@chat.route("/chat/admin", methods=["GET", "POST"])
@login_required
def admin_chat():
    if normalized_role(current_user) == "admin":
        return redirect(url_for("chat.admin_chats"))

    admin = get_admin()

    if admin is None:
        flash(
            "No administrator is currently available.",
            "danger",
        )
        return redirect(url_for("dashboard"))

    if not allowed_direct_chat(current_user, admin):
        flash("You are not allowed to start this chat.", "danger")
        return redirect(url_for("dashboard"))

    try:
        conversation = get_or_create_conversation(
            current_user.id,
            admin.id,
        )

        if request.method == "POST":
            message_text = request.form.get(
                "message", ""
            ).strip()

            if not message_text:
                db.session.commit()
                flash("Message cannot be empty.", "warning")
                return redirect(url_for("chat.admin_chat"))

            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                receiver_id=admin.id,
                message=message_text,
                is_read=False,
            )

            db.session.add(message)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()

            flash("Message sent.", "success")
            return redirect(url_for("chat.admin_chat"))

        db.session.commit()

        Message.query.filter(
            Message.conversation_id == conversation.id,
            Message.receiver_id == current_user.id,
            Message.is_read.is_(False),
        ).update(
            {"is_read": True},
            synchronize_session=False,
        )

        db.session.commit()

        messages = Message.query.filter_by(
            conversation_id=conversation.id,
        ).order_by(
            Message.created_at.asc(),
        ).all()

        return render_template(
            "chat/admin_chat.html",
            conversation=conversation,
            messages=messages,
            admin=admin,
        )

    except Exception as error:
        safe_flash_error(
            "Unable to open the administrator chat.",
            error,
        )
        return redirect(url_for("dashboard"))


# ============================================================
# ADMIN CHAT LIST
# ============================================================

@chat.route("/admin/chats")
@login_required
def admin_chats():
    if normalized_role(current_user) != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    conversations = Conversation.query.filter(
        db.or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id,
        )
    ).order_by(
        Conversation.updated_at.desc(),
        Conversation.id.desc(),
    ).all()

    valid_conversations = []

    for conversation in conversations:
        if conversation.user1_id == current_user.id:
            other_user = conversation.user2
        else:
            other_user = conversation.user1

        if (
            other_user
            and normalized_role(other_user) in ("buyer", "seller")
        ):
            valid_conversations.append(conversation)

    return render_template(
        "chat/admin_chats.html",
        conversations=valid_conversations,
    )


# ============================================================
# ADMIN OPEN CONVERSATION
# ============================================================

@chat.route(
    "/admin/chat/<int:conversation_id>",
    methods=["GET", "POST"],
)
@login_required
def admin_conversation(conversation_id):
    if normalized_role(current_user) != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    conversation = db.session.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        flash("Conversation not found.", "danger")
        return redirect(url_for("chat.admin_chats"))

    if current_user.id not in (
        conversation.user1_id,
        conversation.user2_id,
    ):
        flash(
            "You are not authorized to view this conversation.",
            "danger",
        )
        return redirect(url_for("chat.admin_chats"))

    if conversation.user1_id == current_user.id:
        other_user = conversation.user2
    else:
        other_user = conversation.user1

    if (
        other_user is None
        or normalized_role(other_user) not in ("buyer", "seller")
    ):
        flash("Invalid chat conversation.", "danger")
        return redirect(url_for("chat.admin_chats"))

    if request.method == "POST":
        message_text = request.form.get(
            "message", ""
        ).strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")
            return redirect(
                url_for(
                    "chat.admin_conversation",
                    conversation_id=conversation.id,
                )
            )

        try:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                receiver_id=other_user.id,
                message=message_text,
                is_read=False,
            )

            db.session.add(message)

            notification = Notification(
                user_id=other_user.id,
                title="New Admin Message",
                message="Administrator sent you a new message.",
                notification_type="message",
                is_read=False,
            )

            db.session.add(notification)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()

            flash("Message sent.", "success")

        except Exception as error:
            safe_flash_error(
                "Unable to send the message.",
                error,
            )

        return redirect(
            url_for(
                "chat.admin_conversation",
                conversation_id=conversation.id,
            )
        )

    try:
        Message.query.filter(
            Message.conversation_id == conversation.id,
            Message.receiver_id == current_user.id,
            Message.is_read.is_(False),
        ).update(
            {"is_read": True},
            synchronize_session=False,
        )

        db.session.commit()

        messages = Message.query.filter_by(
            conversation_id=conversation.id,
        ).order_by(
            Message.created_at.asc(),
        ).all()

    except Exception as error:
        safe_flash_error(
            "Unable to load the conversation.",
            error,
        )
        return redirect(url_for("chat.admin_chats"))

    return render_template(
        "chat/admin_chat.html",
        conversation=conversation,
        messages=messages,
        other_user=other_user,
    )


# ============================================================
# ADMIN START CHAT WITH USER
# ============================================================

@chat.route("/admin/start-chat/<int:user_id>")
@login_required
def admin_start_chat(user_id):
    if normalized_role(current_user) != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)

    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("chat.admin_chats"))

    if normalized_role(user) not in ("buyer", "seller"):
        flash(
            "You can only chat with buyers or sellers.",
            "warning",
        )
        return redirect(url_for("chat.admin_chats"))

    try:
        conversation = get_or_create_conversation(
            current_user.id,
            user.id,
        )

        db.session.commit()

        return redirect(
            url_for(
                "chat.admin_conversation",
                conversation_id=conversation.id,
            )
        )

    except Exception as error:
        safe_flash_error(
            "Unable to start the conversation.",
            error,
        )
        return redirect(url_for("chat.admin_chats"))
