
from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime


# ==========================================
# LOGIN MANAGER
# ==========================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ==========================================
# USER MODEL
# ==========================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(20),
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="buyer",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )


    # ==========================================
    # SELLER CARS
    # ==========================================

    cars = db.relationship(
        "Car",
        back_populates="seller",
        cascade="all, delete-orphan"
    )


    # ==========================================
    # BUYER INQUIRIES
    # ==========================================

    buyer_inquiries = db.relationship(
        "Inquiry",
        foreign_keys="Inquiry.buyer_id",
        back_populates="buyer"
    )


    # ==========================================
    # SELLER INQUIRIES
    # ==========================================

    seller_inquiries = db.relationship(
        "Inquiry",
        foreign_keys="Inquiry.seller_id",
        back_populates="seller"
    )


    # ==========================================
    # INQUIRY MESSAGES
    # ==========================================

    sent_messages = db.relationship(
        "InquiryMessage",
        foreign_keys="InquiryMessage.sender_id",
        back_populates="sender"
    )

    received_messages = db.relationship(
        "InquiryMessage",
        foreign_keys="InquiryMessage.receiver_id",
        back_populates="receiver"
    )


    # ==========================================
    # DIRECT CONVERSATIONS
    #
    # Used for:
    # Seller ↔ Admin
    # Buyer  ↔ Admin
    #
    # Seller ↔ Seller and Buyer ↔ Buyer
    # are blocked by the application logic.
    # ==========================================

    conversations_as_user1 = db.relationship(
        "Conversation",
        foreign_keys="Conversation.user1_id",
        back_populates="user1",
        cascade="all, delete-orphan"
    )

    conversations_as_user2 = db.relationship(
        "Conversation",
        foreign_keys="Conversation.user2_id",
        back_populates="user2",
        cascade="all, delete-orphan"
    )


    # ==========================================
    # DIRECT MESSAGES
    # ==========================================

    direct_messages_sent = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan"
    )

    direct_messages_received = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan"
    )


# ==========================================
# CAR MODEL
# ==========================================

class Car(db.Model):

    __tablename__ = "cars"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    registration_number = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    brand = db.Column(
        db.String(50),
        nullable=False
    )

    model = db.Column(
        db.String(50),
        nullable=False
    )

    year = db.Column(
        db.Integer,
        nullable=False
    )

    price = db.Column(
        db.Integer,
        nullable=False
    )

    mileage = db.Column(
        db.Integer,
        nullable=False
    )

    fuel = db.Column(
        db.String(30),
        nullable=False
    )

    transmission = db.Column(
        db.String(30),
        nullable=False
    )

    engine = db.Column(
        db.String(50)
    )

    color = db.Column(
        db.String(30)
    )

    condition = db.Column(
        db.String(30)
    )

    location = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    status = db.Column(
        db.String(20),
        default="Pending"
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    updated_at = db.Column(
        db.DateTime,
        onupdate=db.func.now()
    )


    # ==========================================
    # SELLER
    # ==========================================

    seller = db.relationship(
        "User",
        back_populates="cars"
    )


    # ==========================================
    # IMAGES
    # ==========================================

    images = db.relationship(
        "CarImage",
        back_populates="car",
        cascade="all, delete-orphan"
    )


    # ==========================================
    # INQUIRIES
    # ==========================================

    inquiries = db.relationship(
        "Inquiry",
        back_populates="car",
        cascade="all, delete-orphan"
    )


# ==========================================
# CAR IMAGE MODEL
# ==========================================

class CarImage(db.Model):

    __tablename__ = "car_images"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id"),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    image_type = db.Column(
        db.String(50)
    )

    uploaded_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )


    car = db.relationship(
        "Car",
        back_populates="images"
    )


# ==========================================
# INQUIRY MODEL
#
# Buyer ↔ Seller communication about a car
# ==========================================

class Inquiry(db.Model):

    __tablename__ = "inquiries"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    car_id = db.Column(
        db.Integer,
        db.ForeignKey("cars.id"),
        nullable=False
    )

    buyer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="Open"
    )

    admin_notes = db.Column(
        db.Text
    )

    admin_reply = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


    # ==========================================
    # CAR
    # ==========================================

    car = db.relationship(
        "Car",
        back_populates="inquiries"
    )


    # ==========================================
    # BUYER
    # ==========================================

    buyer = db.relationship(
        "User",
        foreign_keys=[buyer_id],
        back_populates="buyer_inquiries"
    )


    # ==========================================
    # SELLER
    # ==========================================

    seller = db.relationship(
        "User",
        foreign_keys=[seller_id],
        back_populates="seller_inquiries"
    )


    # ==========================================
    # INQUIRY MESSAGES
    # ==========================================

    messages = db.relationship(
        "InquiryMessage",
        back_populates="inquiry",
        cascade="all, delete-orphan"
    )


# ==========================================
# INQUIRY MESSAGE MODEL
#
# Buyer ↔ Seller
#
# This is kept for your existing inquiry system.
# ==========================================

class InquiryMessage(db.Model):

    __tablename__ = "inquiry_messages"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    inquiry_id = db.Column(
        db.Integer,
        db.ForeignKey("inquiries.id"),
        nullable=True
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    sender_role = db.Column(
        db.String(20),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    # ==========================================
    # INQUIRY
    # ==========================================

    inquiry = db.relationship(
        "Inquiry",
        back_populates="messages"
    )


    # ==========================================
    # SENDER
    # ==========================================

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_messages"
    )


    # ==========================================
    # RECEIVER
    # ==========================================

    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="received_messages"
    )


# ==========================================
# DIRECT CONVERSATION MODEL
#
# Used for:
#
# Seller ↔ Admin
# Buyer  ↔ Admin
#
# NOT intended for:
#
# Seller ↔ Seller
# Buyer  ↔ Buyer
# ==========================================

class Conversation(db.Model):

    __tablename__ = "conversations"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user1_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    user2_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


    # ==========================================
    # USER 1
    # ==========================================

    user1 = db.relationship(
        "User",
        foreign_keys=[user1_id],
        back_populates="conversations_as_user1"
    )


    # ==========================================
    # USER 2
    # ==========================================

    user2 = db.relationship(
        "User",
        foreign_keys=[user2_id],
        back_populates="conversations_as_user2"
    )


    # ==========================================
    # MESSAGES
    # ==========================================

    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


# ==========================================
# DIRECT MESSAGE MODEL
#
# Used for:
#
# Seller ↔ Admin
# Buyer  ↔ Admin
# ==========================================

class Message(db.Model):

    __tablename__ = "messages"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id"),
        nullable=False
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    # ==========================================
    # CONVERSATION
    # ==========================================

    conversation = db.relationship(
        "Conversation",
        back_populates="messages"
    )


    # ==========================================
    # SENDER
    # ==========================================

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="direct_messages_sent"
    )


    # ==========================================
    # RECEIVER
    # ==========================================

    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="direct_messages_received"
    )

