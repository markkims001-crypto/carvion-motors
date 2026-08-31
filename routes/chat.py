
# routes/chat.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import (
    login_required,
    current_user
)

from extensions import db

from models import (
    User,
    Car,
    Inquiry,
    InquiryMessage,
    Conversation,
    Message
)


# =====================================================
# CHAT BLUEPRINT
# =====================================================

chat = Blueprint(
    "chat",
    __name__
)


# =====================================================
# HELPER
# GET ADMIN
# =====================================================

def get_admin():

    return User.query.filter_by(
        role="admin"
    ).first()


# =====================================================
# HELPER
# CHECK DIRECT CHAT
#
# Allowed:
# Buyer  ↔ Admin
# Seller ↔ Admin
#
# Not allowed:
# Buyer  ↔ Buyer
# Seller ↔ Seller
# Buyer  ↔ Seller
# =====================================================

def allowed_direct_chat(user_a, user_b):

    roles = {
        user_a.role.lower(),
        user_b.role.lower()
    }

    return roles in [
        {"buyer", "admin"},
        {"seller", "admin"}
    ]


# =====================================================
# HELPER
# GET OR CREATE CONVERSATION
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
# CHANNEL 1
# BUYER ↔ SELLER
#
# Uses Inquiry + InquiryMessage
# =====================================================

@chat.route(
    "/chat/inquiry/<int:inquiry_id>",
    methods=["GET", "POST"]
)
@login_required
def inquiry_chat(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    # Only the buyer and seller of this inquiry
    # can access it.

    if current_user.id not in [
        inquiry.buyer_id,
        inquiry.seller_id
    ]:

        flash(
            "You are not allowed to access this conversation.",
            "danger"
        )

        return redirect(
            url_for("cars.all_cars")
        )


    # =================================================
    # SEND MESSAGE
    # =================================================

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


        # Buyer sends to seller

        if current_user.id == inquiry.buyer_id:

            receiver_id = inquiry.seller_id

        # Seller sends to buyer

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


    # =================================================
    # MARK RECEIVED MESSAGES AS READ
    # =================================================

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


    # =================================================
    # GET MESSAGES
    # =================================================

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
# CHANNEL 1
# START BUYER ↔ SELLER CHAT FROM CAR
# =====================================================

@chat.route(
    "/chat/car/<int:car_id>",
    methods=["POST"]
)
@login_required
def start_car_chat(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    # Only buyers can start vehicle inquiries.

    if current_user.role.lower() != "buyer":

        flash(
            "Only buyers can contact sellers about vehicles.",
            "danger"
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )


    # Buyer cannot contact themselves.

    if current_user.id == car.seller_id:

        flash(
            "You cannot contact yourself.",
            "warning"
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )


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
                "cars.car_details",
                car_id=car.id
            )
        )


    # =================================================
    # FIND EXISTING INQUIRY
    # =================================================

    inquiry = Inquiry.query.filter_by(

        car_id=car.id,

        buyer_id=current_user.id,

        seller_id=car.seller_id

    ).first()


    # =================================================
    # CREATE INQUIRY
    # =================================================

    if not inquiry:

        inquiry = Inquiry(

            car_id=car.id,

            buyer_id=current_user.id,

            seller_id=car.seller_id,

            status="Open"

        )

        db.session.add(inquiry)

        db.session.flush()


    # =================================================
    # CREATE FIRST MESSAGE
    # =================================================

    message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=car.seller_id,

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


# =====================================================
# BUYER INQUIRIES
# =====================================================

@chat.route(
    "/chat/my-inquiries"
)
@login_required
def my_inquiries():

    if current_user.role.lower() != "buyer":

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
# SELLER INQUIRIES
# =====================================================

@chat.route(
    "/chat/seller-inquiries"
)
@login_required
def seller_inquiries_chat():

    if current_user.role.lower() != "seller":

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
# CHANNEL 2 & 3
#
# BUYER ↔ ADMIN
# SELLER ↔ ADMIN
# =====================================================

@chat.route(
    "/chat/admin",
    methods=["GET", "POST"]
)
@login_required
def admin_chat():

    # Only buyers and sellers can use this page.

    if current_user.role.lower() not in [
        "buyer",
        "seller"
    ]:

        flash(
            "This chat is only for buyers and sellers.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    # =================================================
    # FIND ADMIN
    # =================================================

    admin = get_admin()


    if not admin:

        flash(
            "Administrator account not found.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    # =================================================
    # GET / CREATE CONVERSATION
    # =================================================

    conversation = get_or_create_conversation(

        current_user.id,

        admin.id

    )


    # =================================================
    # SEND MESSAGE
    # =================================================

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


    # =================================================
    # MARK ADMIN MESSAGES AS READ
    # =================================================

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


    # =================================================
    # GET MESSAGES
    # =================================================

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
# ADMIN
# VIEW ALL DIRECT CHATS
#
# Shows:
# Buyer ↔ Admin
# Seller ↔ Admin
# =====================================================

@chat.route(
    "/admin/chats"
)
@login_required
def admin_chats():

    if current_user.role.lower() != "admin":

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


    # Only keep valid admin conversations.

    valid_conversations = []


    for conversation in conversations:

        if conversation.user1_id == current_user.id:

            other_user = conversation.user2

        else:

            other_user = conversation.user1


        if other_user and allowed_direct_chat(
            current_user,
            other_user
        ):

            valid_conversations.append(
                conversation
            )


    return render_template(
    "chat/admin_chats.html",
    conversations=valid_conversations
)


# =====================================================
# ADMIN
# OPEN DIRECT CHAT
# =====================================================

@chat.route(
    "/admin/chat/<int:conversation_id>",
    methods=["GET", "POST"]
)
@login_required
def admin_conversation(conversation_id):

    if current_user.role.lower() != "admin":

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


    # Admin must belong to conversation.

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


    # =================================================
    # FIND OTHER USER
    # =================================================

    if conversation.user1_id == current_user.id:

        other_user = conversation.user2

    else:

        other_user = conversation.user1


    # =================================================
    # CHECK CHANNEL
    # =================================================

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


    # =================================================
    # ADMIN SENDS MESSAGE
    # =================================================

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
                    "chat.admin_conversation",
                    conversation_id=conversation.id
                )
            )


        message = Message(

            conversation_id=conversation.id,

            sender_id=current_user.id,

            receiver_id=other_user.id,

            message=message_text,

            is_read=False

        )


        db.session.add(message)


        conversation.updated_at = db.func.now()


        db.session.commit()


        return redirect(
            url_for(
                "chat.admin_conversation",
                conversation_id=conversation.id
            )
        )


    # =================================================
    # MARK MESSAGES AS READ
    # =================================================

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
# ADMIN
# START CHAT WITH USER
# =====================================================

@chat.route(
    "/admin/start-chat/<int:user_id>"
)
@login_required
def admin_start_chat(user_id):

    if current_user.role.lower() != "admin":

        flash(
            "Administrator access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    user = User.query.get_or_404(
        user_id
    )


    # Admin can only chat with buyers and sellers.

    if user.role.lower() not in [
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
