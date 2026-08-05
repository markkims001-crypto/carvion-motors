from flask import (
    Blueprint,
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
    Inquiry,
    InquiryMessage,
    User
)


messages = Blueprint(
    "messages",
    __name__,
    url_prefix="/messages"
)



# ==========================================
# SEND MESSAGE
# ==========================================

@messages.route(
    "/send/<int:inquiry_id>",
    methods=["POST"]
)
@login_required
def send_message(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    text = request.form.get(
        "message"
    )


    if not text:

        flash(
            "Message cannot be empty.",
            "warning"
        )

        return redirect(
            request.referrer
        )



    # Determine receiver

    if current_user.role == "admin":

        # Admin replies to buyer/seller

        receiver_id = (
            inquiry.buyer_id
            if inquiry.buyer_id != current_user.id
            else inquiry.seller_id
        )


    elif current_user.id == inquiry.buyer_id:

        # Buyer sends to admin

        receiver_id = User.query.filter_by(
            role="admin"
        ).first().id


    elif current_user.id == inquiry.seller_id:

        # Seller sends to admin

        receiver_id = User.query.filter_by(
            role="admin"
        ).first().id


    else:

        flash(
            "Permission denied.",
            "danger"
        )

        return redirect(
            request.referrer
        )



    message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=receiver_id,

        message=text

    )


    db.session.add(
        message
    )


    inquiry.status = "Replied"


    db.session.commit()



    flash(
        "Message sent.",
        "success"
    )


    return redirect(
        request.referrer
    )