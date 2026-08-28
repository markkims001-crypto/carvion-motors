# routes/chat.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import (
    User,
    Car,
    Inquiry,
    InquiryMessage,
    Conversation,
    Message
)


chat = Blueprint("chat", __name__)


# =====================================================
# HELPER: CHECK IF USERS CAN DIRECTLY CHAT
# =====================================================

def allowed_direct_chat(user_a, user_b):

    roles = {user_a.role, user_b.role}

    # Seller <-> Admin
    if roles == {"seller", "admin"}:
        return True

    # Buyer <-> Admin
    if roles == {"buyer", "admin"}:
        return True

    # Seller <-> Seller
    if user_a.role == "seller" and user_b.role == "seller":
        return False

    # Buyer <-> Buyer
    if user_a.role == "buyer" and user_b.role == "buyer":
        return False

    # Buyer <-> Seller uses InquiryMessage instead
    if roles == {"buyer", "seller"}:
        return False

    return False


# =====================================================
# HELPER: GET OR CREATE DIRECT CONVERSATION
# =====================================================

def get_or_create_conversation(user1_id, user2_id):

    conversation = Conversation.query.filter(
        (
            (Conversation.user1_id == user1_id) &
            (Conversation.user2_id == user2_id)
        )
        |
        (
            (Conversation.user1_id == user2_id) &
            (Conversation.user2_id == user1_id)
        )
    ).first()

    if not conversation:

        conversation = Conversation(
            user1_id=user1_id,
            user2_id=user2_id
        )

        db.session.add(conversation)
        db.session.commit()

    return conversation


# =====================================================
# SELLER ↔ BUYER CHAT
# =====================================================

@chat.route("/chat/inquiry/<int:inquiry_id>", methods=["GET", "POST"])
@login_required
def inquiry_chat(inquiry_id):

    inquiry = Inquiry.query.get_or_404(inquiry_id)

    # Only the buyer and seller belonging to this inquiry
    # may access this conversation.

    if current_user.id not in [
        inquiry.buyer_id,
        inquiry.seller_id
    ]:

        flash(
            "You are not allowed to access this conversation.",
            "danger"
        )

        return redirect(url_for("cars.all_cars"))


    if request.method == "POST":

        message_text = request.form.get(
            "message",
            ""
        ).strip()


        if not message_text:

            flash(
                "Message cannot be empty.",
                "danger"
            )

            return redirect(
                url_for(
                    "chat.inquiry_chat",
                    inquiry_id=inquiry.id
                )
            )


        # Determine receiver

        if current_user.id == inquiry.buyer_id:

            receiver_id = inquiry.seller_id

        else:

            receiver_id = inquiry.buyer_id


        message = InquiryMessage(

            inquiry_id=inquiry.id,

            sender_id=current_user.id,

            receiver_id=receiver_id,

            sender_role=current_user.role,

            message=message_text,

            is_read=False
        )


        db.session.add(message)

        inquiry.status = "Open"

        db.session.commit()


        return redirect(
            url_for(
                "chat.inquiry_chat",
                inquiry_id=inquiry.id
            )
        )


    # Mark messages received by current user as read

    InquiryMessage.query.filter(

        InquiryMessage.inquiry_id == inquiry.id,

        InquiryMessage.receiver_id == current_user.id,

        InquiryMessage.is_read == False

    ).update(
        {
            InquiryMessage.is_read: True
        },
        synchronize_session=False
    )


    db.session.commit()


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


# =====================================================
# BUYER ↔ SELLER: START CHAT FROM CAR
# =====================================================

@chat.route(
    "/chat/car/<int:car_id>",
    methods=["POST"]
)
@login_required
def start_car_chat(car_id):

    car = Car.query.get_or_404(car_id)


    if current_user.id == car.seller_id:

        flash(
            "You cannot chat with yourself.",
            "warning"
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )


    if current_user.role != "buyer":

        flash(
            "Only buyers can start a vehicle inquiry.",
            "danger"
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )


    # Look for an existing inquiry

    inquiry = Inquiry.query.filter_by(
        car_id=car.id,
        buyer_id=current_user.id,
        seller_id=car.seller_id
    ).first()


    if not inquiry:

        inquiry = Inquiry(

            car_id=car.id,

            buyer_id=current_user.id,

            seller_id=car.seller_id,

            status="Open"
        )

        db.session.add(inquiry)

        db.session.commit()


    message_text = request.form.get(
        "message",
        ""
    ).strip()


    if message_text:

        message = InquiryMessage(

            inquiry_id=inquiry.id,

            sender_id=current_user.id,

            receiver_id=car.seller_id,

            sender_role=current_user.role,

            message=message_text,

            is_read=False
        )

        db.session.add(message)

        db.session.commit()


    return redirect(
        url_for(
            "chat.inquiry_chat",
            inquiry_id=inquiry.id
        )
    )


# =====================================================
# BUYER INQUIRY LIST
# =====================================================

@chat.route("/chat/my-inquiries")
@login_required
def my_inquiries():

    if current_user.role != "buyer":

        flash(
            "Buyer access required.",
            "danger"
        )

        return redirect(
            url_for("cars.all_cars")
        )


    inquiries = Inquiry.query.filter_by(
        buyer_id=current_user.id
    ).order_by(
        Inquiry.updated_at.desc()
    ).all()


    return render_template(
        "chat/buyer_inquiries.html",
        inquiries=inquiries
    )


# =====================================================
# SELLER INQUIRY LIST
# =====================================================

@chat.route("/chat/seller-inquiries")
@login_required
def seller_inquiries_chat():

    if current_user.role != "seller":

        flash(
            "Seller access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    inquiries = Inquiry.query.filter_by(
        seller_id=current_user.id
    ).order_by(
        Inquiry.updated_at.desc()
    ).all()


    return render_template(
        "chat/seller_inquiries.html",
        inquiries=inquiries
    )


# =====================================================
# DIRECT CHAT WITH ADMIN
#
# Seller ↔ Admin
# Buyer  ↔ Admin
# =====================================================

@chat.route("/chat/admin", methods=["GET", "POST"])
@login_required
def admin_chat():

    # Admin himself doesn't need to use this route
    # to start a conversation.

    if current_user.role not in [
        "buyer",
        "seller"
    ]:

        flash(
            "This chat is for buyers and sellers.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    admin = User.query.filter_by(
        role="admin"
    ).first()


    if not admin:

        flash(
            "No administrator account is available.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    conversation = get_or_create_conversation(
        current_user.id,
        admin.id
    )


    if request.method == "POST":

        message_text = request.form.get(
            "message",
            ""
        ).strip()


        if not message_text:

            flash(
                "Message cannot be empty.",
                "danger"
            )

            return redirect(
                url_for("chat.admin_chat")
            )


        message = Message(

            conversation_id=conversation.id,

            sender_id=current_user.id,

            receiver_id=admin.id,

            message=message_text,

            is_read=False
        )


        db.session.add(message)

        conversation.updated_at = db.func.now()

        db.session.commit()


        return redirect(
            url_for("chat.admin_chat")
        )


    # Mark admin messages received by current user as read

    Message.query.filter(

        Message.conversation_id == conversation.id,

        Message.receiver_id == current_user.id,

        Message.is_read == False

    ).update(
        {
            Message.is_read: True
        },
        synchronize_session=False
    )


    db.session.commit()


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


# =====================================================
# ADMIN: VIEW ALL DIRECT CONVERSATIONS
# =====================================================

@chat.route("/admin/chats")
@login_required
def admin_chats():

    if current_user.role != "admin":

        flash(
            "Administrator access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    conversations = Conversation.query.filter(
        (
            Conversation.user1_id == current_user.id
        )
        |
        (
            Conversation.user2_id == current_user.id
        )
    ).order_by(
        Conversation.updated_at.desc()
    ).all()


    return render_template(
        "chat/admin_chats.html",
        conversations=conversations
    )


# =====================================================
# ADMIN: OPEN DIRECT CONVERSATION
# =====================================================

@chat.route(
    "/admin/chat/<int:conversation_id>",
    methods=["GET", "POST"]
)
@login_required
def admin_conversation(conversation_id):

    if current_user.role != "admin":

        flash(
            "Administrator access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    conversation = Conversation.query.get_or_404(
        conversation_id
    )


    if current_user.id not in [
        conversation.user1_id,
        conversation.user2_id
    ]:

        flash(
            "You are not allowed to access this conversation.",
            "danger"
        )

        return redirect(
            url_for("chat.admin_chats")
        )


    # Find the other person

    if conversation.user1_id == current_user.id:

        other_user = conversation.user2

    else:

        other_user = conversation.user1


    # Only Buyer <-> Admin and Seller <-> Admin

    if not allowed_direct_chat(
        current_user,
        other_user
    ):

        flash(
            "This conversation type is not allowed.",
            "danger"
        )

        return redirect(
            url_for("chat.admin_chats")
        )


    if request.method == "POST":

        message_text = request.form.get(
            "message",
            ""
        ).strip()


        if message_text:

            message = Message(

                conversation_id=conversation.id,

                sender_id=current_user.id,

                receiver_id=other_user.id,

                message=message_text,

                is_read=False
            )


            db.session.add(message)

            db.session.commit()


            return redirect(
                url_for(
                    "chat.admin_conversation",
                    conversation_id=conversation.id
                )
            )


    Message.query.filter(

        Message.conversation_id == conversation.id,

        Message.receiver_id == current_user.id,

        Message.is_read == False

    ).update(
        {
            Message.is_read: True
        },
        synchronize_session=False
    )


    db.session.commit()


    messages = Message.query.filter_by(
        conversation_id=conversation.id
    ).order_by(
        Message.created_at.asc()
    ).all()


    return render_template(
        "chat/admin_conversation.html",
        conversation=conversation,
        other_user=other_user,
        messages=messages
    )


# =====================================================
# ADMIN: START CHAT WITH USER
# =====================================================

@chat.route(
    "/admin/start-chat/<int:user_id>",
    methods=["GET"]
)
@login_required
def admin_start_chat(user_id):

    if current_user.role != "admin":

        flash(
            "Administrator access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    user = User.query.get_or_404(user_id)


    if user.role not in [
        "buyer",
        "seller"
    ]:

        flash(
            "Admin can only chat with buyers and sellers.",
            "danger"
        )

        return redirect(
            url_for("chat.admin_chats")
        )


    conversation = get_or_create_conversation(
        current_user.id,
        user.id
    )


    return redirect(
        url_for(
            "chat.admin_conversation",
            conversation_id=conversation.id
        )
    )