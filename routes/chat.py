# routes/chat.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
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

def get_admin():
    """
    Get the first registered admin user.
    """
    return User.query.filter_by(role="admin").first()


def allowed_direct_chat(user1, user2):
    """
    Direct chat is only allowed between:
        Buyer <-> Admin
        Seller <-> Admin

    Buyer <-> Seller direct chat is handled through
    vehicle inquiries instead.
    """

    if not user1 or not user2:
        return False

    roles = {user1.role, user2.role}

    return (
        "admin" in roles
        and (
            "buyer" in roles
            or "seller" in roles
        )
    )


def get_or_create_conversation(user1_id, user2_id):
    """
    Find an existing conversation between two users,
    regardless of which user is user1/user2.

    If none exists, create one.
    """

    conversation = Conversation.query.filter(
        (
            (Conversation.user1_id == user1_id)
            &
            (Conversation.user2_id == user2_id)
        )
        |
        (
            (Conversation.user1_id == user2_id)
            &
            (Conversation.user2_id == user1_id)
        )
    ).first()

    if conversation:
        return conversation

    conversation = Conversation(
        user1_id=user1_id,
        user2_id=user2_id
    )

    db.session.add(conversation)
    db.session.flush()

    return conversation


# ============================================================
# BUYER <-> SELLER INQUIRY CHAT
# ============================================================

@chat.route("/chat/inquiry/<int:inquiry_id>", methods=["GET", "POST"])
@login_required
def inquiry_chat(inquiry_id):

    inquiry = db.session.get(Inquiry, inquiry_id)

    if not inquiry:
        flash("Inquiry not found.", "danger")
        return redirect(url_for("cars.all_cars"))

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------
    # Only the buyer and seller connected to the inquiry
    # can access this conversation.

    if current_user.id not in (
        inquiry.buyer_id,
        inquiry.seller_id
    ):
        flash("You are not authorized to view this conversation.", "danger")
        return redirect(url_for("cars.all_cars"))

    # --------------------------------------------------------
    # SEND MESSAGE
    # --------------------------------------------------------

    if request.method == "POST":

        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")
            return redirect(
                url_for(
                    "chat.inquiry_chat",
                    inquiry_id=inquiry.id
                )
            )

        # Determine recipient
        if current_user.id == inquiry.buyer_id:
            receiver_id = inquiry.seller_id
        else:
            receiver_id = inquiry.buyer_id

        # Create inquiry message
        new_message = InquiryMessage(
            inquiry_id=inquiry.id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            sender_role=current_user.role,
            message=message_text,
            is_read=False
        )

        db.session.add(new_message)

        # ----------------------------------------------------
        # UPDATE INQUIRY
        # ----------------------------------------------------

        inquiry.status = "Open"

        # ----------------------------------------------------
        # CREATE NOTIFICATION
        # ----------------------------------------------------

        notification_title = "New Inquiry Message"

        notification_message = (
            f"{current_user.name} sent you a new message "
            f"about {inquiry.car.brand} {inquiry.car.model}."
        )

        notification = Notification(
            user_id=receiver_id,
            car_id=inquiry.car_id,
            title=notification_title,
            message=notification_message,
            notification_type="inquiry",
            is_read=False
        )

        db.session.add(notification)

        # Save everything
        db.session.commit()

        flash("Message sent successfully.", "success")

        return redirect(
            url_for(
                "chat.inquiry_chat",
                inquiry_id=inquiry.id
            )
        )

    # --------------------------------------------------------
    # MARK RECEIVED MESSAGES AS READ
    # --------------------------------------------------------

    unread_messages = InquiryMessage.query.filter(
        InquiryMessage.inquiry_id == inquiry.id,
        InquiryMessage.receiver_id == current_user.id,
        InquiryMessage.is_read.is_(False)
    ).all()

    for message in unread_messages:
        message.is_read = True

    if unread_messages:
        db.session.commit()

    # --------------------------------------------------------
    # LOAD MESSAGES
    # --------------------------------------------------------

    messages = InquiryMessage.query.filter_by(
        inquiry_id=inquiry.id
    ).order_by(
        InquiryMessage.created_at.asc()
    ).all()

    return render_template(
        "chat/inquiry_chat.html",
        inquiry=inquiry,
        messages=messages
    )


# ============================================================
# START INQUIRY CHAT FROM A CAR
# ============================================================

@chat.route("/chat/car/<int:car_id>", methods=["GET", "POST"])
@login_required
def start_car_chat(car_id):

    car = db.session.get(Car, car_id)

    if not car:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("cars.all_cars"))

    # --------------------------------------------------------
    # ONLY BUYERS CAN START VEHICLE INQUIRIES
    # --------------------------------------------------------

    if current_user.role != "buyer":
        flash("Only buyers can start vehicle inquiries.", "warning")
        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )

    # --------------------------------------------------------
    # SELLER MUST EXIST
    # --------------------------------------------------------

    if not car.seller:
        flash("This vehicle does not have a seller.", "danger")
        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )

    # --------------------------------------------------------
    # FIND EXISTING INQUIRY
    # --------------------------------------------------------

    inquiry = Inquiry.query.filter_by(
        car_id=car.id,
        buyer_id=current_user.id
    ).first()

    # --------------------------------------------------------
    # CREATE INQUIRY IF NEEDED
    # --------------------------------------------------------

    if not inquiry:

        inquiry = Inquiry(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.seller_id,
            status="Open"
        )

        db.session.add(inquiry)
        db.session.flush()

    # --------------------------------------------------------
    # POST MESSAGE
    # --------------------------------------------------------

    if request.method == "POST":

        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")
            return redirect(
                url_for(
                    "chat.inquiry_chat",
                    inquiry_id=inquiry.id
                )
            )

        new_message = InquiryMessage(
            inquiry_id=inquiry.id,
            sender_id=current_user.id,
            receiver_id=car.seller_id,
            sender_role=current_user.role,
            message=message_text,
            is_read=False
        )

        db.session.add(new_message)

        inquiry.status = "Open"

        # Notify seller
        notification = Notification(
            user_id=car.seller_id,
            car_id=car.id,
            title="New Vehicle Inquiry",
            message=(
                f"{current_user.name} sent you a message "
                f"about {car.brand} {car.model}."
            ),
            notification_type="inquiry",
            is_read=False
        )

        db.session.add(notification)

        db.session.commit()

        flash("Your inquiry has been sent.", "success")

        return redirect(
            url_for(
                "chat.inquiry_chat",
                inquiry_id=inquiry.id
            )
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return redirect(
        url_for(
            "chat.inquiry_chat",
            inquiry_id=inquiry.id
        )
    )


# ============================================================
# BUYER INQUIRIES
# ============================================================

@chat.route("/chat/my-inquiries")
@login_required
def my_inquiries():

    inquiries = Inquiry.query.filter_by(
        buyer_id=current_user.id
    ).order_by(
        Inquiry.updated_at.desc()
    ).all()

    return render_template(
        "chat/my_inquiries.html",
        inquiries=inquiries
    )


# ============================================================
# SELLER INQUIRIES
# ============================================================

@chat.route("/chat/seller-inquiries")
@login_required
def seller_inquiries_chat():

    if current_user.role != "seller":
        flash("Seller access required.", "danger")
        return redirect(url_for("cars.all_cars"))

    inquiries = Inquiry.query.filter_by(
        seller_id=current_user.id
    ).order_by(
        Inquiry.updated_at.desc()
    ).all()

    return render_template(
        "chat/seller_inquiries.html",
        inquiries=inquiries
    )


# ============================================================
# BUYER / SELLER <-> ADMIN DIRECT CHAT
# ============================================================

@chat.route("/chat/admin", methods=["GET", "POST"])
@login_required
def admin_chat():

    # Admin should use the admin chat management page
    if current_user.role == "admin":
        return redirect(url_for("chat.admin_chats"))

    admin = get_admin()

    if not admin:
        flash("No administrator is currently available.", "danger")
        return redirect(url_for("dashboard"))

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if not allowed_direct_chat(current_user, admin):
        flash("You are not allowed to start this chat.", "danger")
        return redirect(url_for("dashboard"))

    # --------------------------------------------------------
    # GET / CREATE CONVERSATION
    # --------------------------------------------------------

    conversation = get_or_create_conversation(
        current_user.id,
        admin.id
    )

    # --------------------------------------------------------
    # SEND MESSAGE
    # --------------------------------------------------------

    if request.method == "POST":

        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")

            return redirect(
                url_for("chat.admin_chat")
            )

        new_message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            receiver_id=admin.id,
            message=message_text,
            is_read=False
        )

        db.session.add(new_message)

        db.session.commit()

        flash("Message sent.", "success")

        return redirect(
            url_for("chat.admin_chat")
        )

    # --------------------------------------------------------
    # MARK ADMIN MESSAGES AS READ
    # --------------------------------------------------------

    unread_messages = Message.query.filter(
        Message.conversation_id == conversation.id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False)
    ).all()

    for message in unread_messages:
        message.is_read = True

    if unread_messages:
        db.session.commit()

    # --------------------------------------------------------
    # LOAD MESSAGES
    # --------------------------------------------------------

    messages = Message.query.filter_by(
        conversation_id=conversation.id
    ).order_by(
        Message.created_at.asc()
    ).all()

    return render_template(
        "chat/admin_chat.html",
        conversation=conversation,
        messages=messages,
        admin=admin
    )


# ============================================================
# ADMIN CHAT LIST
# ============================================================

@chat.route("/admin/chats")
@login_required
def admin_chats():

    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    conversations = Conversation.query.filter(
        (
            Conversation.user1_id == current_user.id
        )
        |
        (
            Conversation.user2_id == current_user.id
        )
    ).order_by(
        Conversation.created_at.desc()
    ).all()

    # Only keep valid admin <-> buyer/seller conversations
    valid_conversations = []

    for conversation in conversations:

        if conversation.user1_id == current_user.id:
            other_user = conversation.user2
        else:
            other_user = conversation.user1

        if not other_user:
            continue

        if other_user.role not in ["buyer", "seller"]:
            continue

        valid_conversations.append(
            conversation
        )

    return render_template(
        "chat/admin_chats.html",
        conversations=valid_conversations
    )


# ============================================================
# ADMIN OPEN CONVERSATION
# ============================================================

@chat.route(
    "/admin/chat/<int:conversation_id>",
    methods=["GET", "POST"]
)
@login_required
def admin_conversation(conversation_id):

    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    conversation = db.session.get(
        Conversation,
        conversation_id
    )

    if not conversation:
        flash("Conversation not found.", "danger")
        return redirect(url_for("chat.admin_chats"))

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if current_user.id not in (
        conversation.user1_id,
        conversation.user2_id
    ):
        flash("You are not authorized to view this conversation.", "danger")
        return redirect(url_for("chat.admin_chats"))

    # Determine other user
    if conversation.user1_id == current_user.id:
        other_user = conversation.user2
    else:
        other_user = conversation.user1

    if not other_user:
        flash("Chat user not found.", "danger")
        return redirect(url_for("chat.admin_chats"))

    # Only buyer/seller <-> admin conversations
    if other_user.role not in ["buyer", "seller"]:
        flash("Invalid chat conversation.", "danger")
        return redirect(url_for("chat.admin_chats"))

    # --------------------------------------------------------
    # SEND MESSAGE
    # --------------------------------------------------------

    if request.method == "POST":

        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Message cannot be empty.", "warning")

            return redirect(
                url_for(
                    "chat.admin_conversation",
                    conversation_id=conversation.id
                )
            )

        new_message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            receiver_id=other_user.id,
            message=message_text,
            is_read=False
        )

        db.session.add(new_message)

        # Create notification for buyer/seller
        notification = Notification(
            user_id=other_user.id,
            title="New Admin Message",
            message=(
                f"Administrator sent you a new message."
            ),
            notification_type="message",
            is_read=False
        )

        db.session.add(notification)

        db.session.commit()

        flash("Message sent.", "success")

        return redirect(
            url_for(
                "chat.admin_conversation",
                conversation_id=conversation.id
            )
        )

    # --------------------------------------------------------
    # MARK RECEIVED MESSAGES AS READ
    # --------------------------------------------------------

    unread_messages = Message.query.filter(
        Message.conversation_id == conversation.id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False)
    ).all()

    for message in unread_messages:
        message.is_read = True

    if unread_messages:
        db.session.commit()

    # --------------------------------------------------------
    # LOAD MESSAGES
    # --------------------------------------------------------

    messages = Message.query.filter_by(
        conversation_id=conversation.id
    ).order_by(
        Message.created_at.asc()
    ).all()

    return render_template(
        "chat/admin_chat.html",
        conversation=conversation,
        messages=messages,
        other_user=other_user
    )


# ============================================================
# ADMIN START CHAT WITH USER
# ============================================================

@chat.route("/admin/start-chat/<int:user_id>")
@login_required
def admin_start_chat(user_id):

    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("chat.admin_chats"))

    # Admin can only start chats with buyers or sellers
    if user.role not in ["buyer", "seller"]:
        flash("You can only chat with buyers or sellers.", "warning")
        return redirect(url_for("chat.admin_chats"))

    conversation = get_or_create_conversation(
        current_user.id,
        user.id
    )

    db.session.commit()

    return redirect(
        url_for(
            "chat.admin_conversation",
            conversation_id=conversation.id
        )
    )