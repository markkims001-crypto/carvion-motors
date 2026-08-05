# routes/admin.py

from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
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
    InquiryMessage
)


# ==========================================
# ADMIN BLUEPRINT
# ==========================================

admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ==========================================
# ADMIN REQUIRED DECORATOR
# ==========================================

def admin_required(func):

    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):

        if current_user.role.lower() != "admin":

            flash(
                "Administrator access required.",
                "danger"
            )

            return redirect(
                url_for("home")
            )

        return func(*args, **kwargs)

    return wrapper


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@admin.route("/dashboard")
@admin_required
def dashboard():

    stats = {

        "total_users":
            User.query.count(),

        "buyers":
            User.query.filter_by(
                role="buyer"
            ).count(),

        "sellers":
            User.query.filter_by(
                role="seller"
            ).count(),

        "admins":
            User.query.filter_by(
                role="admin"
            ).count(),

        "total_cars":
            Car.query.count(),

        "pending_cars":
            Car.query.filter_by(
                status="Pending"
            ).count(),

        "approved_cars":
            Car.query.filter_by(
                status="Approved"
            ).count(),

        "rejected_cars":
            Car.query.filter_by(
                status="Rejected"
            ).count(),

        "total_inquiries":
            Inquiry.query.count(),

        "open_inquiries":
    Inquiry.query.filter_by(
        status="Open"
    ).count(),

        "replied_inquiries":
            Inquiry.query.filter_by(
                status="Replied"
            ).count()

    }

    recent_cars = Car.query.order_by(
        Car.created_at.desc()
    ).limit(5).all()

    recent_users = User.query.order_by(
        User.id.desc()
    ).limit(5).all()

    recent_inquiries = Inquiry.query.order_by(
        Inquiry.created_at.desc()
    ).limit(5).all()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        recent_cars=recent_cars,
        recent_users=recent_users,
        recent_inquiries=recent_inquiries
    )


# ==========================================
# USERS
# ==========================================

@admin.route("/users")
@admin_required
def users():

    users = User.query.order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin_users.html",
        users=users
    )


# ==========================================
# USER DETAILS
# ==========================================

@admin.route("/user/<int:user_id>")
@admin_required
def user_details(user_id):

    user = User.query.get_or_404(
        user_id
    )

    cars = Car.query.filter_by(
        seller_id=user.id
    ).all()

    return render_template(
        "admin_user_details.html",
        user=user,
        cars=cars
    )


# ==========================================
# CHANGE USER ROLE
# ==========================================

@admin.route(
    "/change_role/<int:user_id>/<role>"
)
@admin_required
def change_role(user_id, role):

    user = User.query.get_or_404(
        user_id
    )

    valid_roles = [
        "buyer",
        "seller",
        "admin"
    ]

    if role not in valid_roles:

        flash(
            "Invalid role selected.",
            "danger"
        )

        return redirect(
            url_for("admin.users")
        )

    user.role = role

    db.session.commit()

    flash(
        "User role updated successfully.",
        "success"
    )

    return redirect(
        url_for("admin.users")
    )


# ==========================================
# DELETE USER
# ==========================================

@admin.route(
    "/delete_user/<int:user_id>",
    methods=["POST"]
)
@admin_required
def delete_user(user_id):

    user = User.query.get_or_404(
        user_id
    )

    if user.id == current_user.id:

        flash(
            "You cannot delete your own account.",
            "warning"
        )

        return redirect(
            url_for("admin.users")
        )

    if user.role.lower() == "admin":

        flash(
            "Another administrator cannot be deleted.",
            "danger"
        )

        return redirect(
            url_for("admin.users")
        )

    db.session.delete(user)

    db.session.commit()

    flash(
        "User deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin.users")
    )
# ==========================================
# CAR MANAGEMENT
# ==========================================


# ==========================================
# ALL CARS
# ==========================================

@admin.route("/cars")
@admin_required
def cars():

    status = request.args.get(
        "status"
    )

    query = Car.query


    if status:

        query = query.filter_by(
            status=status
        )


    cars = query.order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "admin_cars.html",
        cars=cars
    )



# ==========================================
# CAR DETAILS
# ==========================================

@admin.route(
    "/car/<int:car_id>"
)
@admin_required
def car_details(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    return render_template(
        "admin_car_details.html",
        car=car
    )



# ==========================================
# APPROVE CAR
# ==========================================

@admin.route(
    "/approve_car/<int:car_id>",
    methods=["POST"]
)
@admin_required
def approve_car(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    car.status = "Approved"


    db.session.commit()


    flash(
        "Car listing approved successfully.",
        "success"
    )


    return redirect(
        url_for(
            "admin.cars"
        )
    )



# ==========================================
# REJECT CAR
# ==========================================

@admin.route(
    "/reject_car/<int:car_id>",
    methods=["POST"]
)
@admin_required
def reject_car(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    car.status = "Rejected"


    db.session.commit()


    flash(
        "Car listing rejected.",
        "warning"
    )


    return redirect(
        url_for(
            "admin.cars"
        )
    )



# ==========================================
# DELETE CAR
# ==========================================

@admin.route(
    "/delete_car/<int:car_id>",
    methods=["POST"]
)
@admin_required
def delete_car(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    # delete associated images

    for image in car.images:

        db.session.delete(
            image
        )


    db.session.delete(
        car
    )


    db.session.commit()


    flash(
        "Car listing deleted.",
        "success"
    )


    return redirect(
        url_for(
            "admin.cars"
        )
    )



# ==========================================
# BULK CAR FILTERS
# ==========================================

@admin.route(
    "/cars/pending"
)
@admin_required
def pending_cars():

    cars = Car.query.filter_by(
        status="Pending"
    ).order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "admin_cars.html",
        cars=cars
    )



@admin.route(
    "/cars/approved"
)
@admin_required
def approved_cars():

    cars = Car.query.filter_by(
        status="Approved"
    ).order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "admin_cars.html",
        cars=cars
    )



@admin.route(
    "/cars/rejected"
)
@admin_required
def rejected_cars():

    cars = Car.query.filter_by(
        status="Rejected"
    ).order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "admin_cars.html",
        cars=cars
    )
# ==========================================
# INQUIRY MANAGEMENT
# ==========================================


# ==========================================
# ALL INQUIRIES
# ==========================================

@admin.route("/inquiries")
@admin_required
def inquiries():

    status = request.args.get(
        "status"
    )


    query = Inquiry.query


    if status:

        query = query.filter_by(
            status=status
        )


    inquiries = query.order_by(
        Inquiry.created_at.desc()
    ).all()


    return render_template(
        "admin_inquiries.html",
        inquiries=inquiries
    )



# ==========================================
# INQUIRY DETAILS
# ==========================================

@admin.route(
    "/inquiry/<int:inquiry_id>"
)
@admin_required
def inquiry_details(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    messages = InquiryMessage.query.filter_by(
        inquiry_id=inquiry.id
    ).order_by(
        InquiryMessage.created_at.asc()
    ).all()


    return render_template(
        "admin_inquiry_details.html",
        inquiry=inquiry,
        messages=messages
    )
# ==========================================
# REPLY TO INQUIRY
# ==========================================

@admin.route(
    "/inquiry/<int:inquiry_id>/reply",
    methods=["POST"]
)
@admin_required
def reply_inquiry(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    message_text = request.form.get(
        "message"
    )


    if not message_text:

        flash(
            "Message cannot be empty.",
            "warning"
        )

        return redirect(
            url_for(
                "admin.inquiry_details",
                inquiry_id=inquiry.id
            )
        )


    # Admin reply message

    admin_message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=inquiry.buyer_id,

        sender_role=current_user.role,

        message=message_text,

        is_read=False

    )


    db.session.add(
        admin_message
    )


    inquiry.status = "Replied"


    db.session.commit()


    flash(
        "Reply sent to buyer.",
        "success"
    )


    return redirect(
        url_for(
            "admin.inquiry_details",
            inquiry_id=inquiry.id
        )
    )
# ==========================================
# MARK INQUIRY AS RESOLVED
# ==========================================

@admin.route(
    "/inquiry/<int:inquiry_id>/resolve",
    methods=["POST"]
)
@admin_required
def resolve_inquiry(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    inquiry.status = "Resolved"

    inquiry.is_closed = True


    db.session.commit()


    flash(
        "Inquiry marked as resolved.",
        "success"
    )


    return redirect(
        url_for(
            "admin.inquiry_details",
            inquiry_id=inquiry.id
        )
    )
# ==========================================
# DELETE INQUIRY
# ==========================================

@admin.route(
    "/delete_inquiry/<int:inquiry_id>",
    methods=["POST"]
)
@admin_required
def delete_inquiry(inquiry_id):

    inquiry = Inquiry.query.get_or_404(
        inquiry_id
    )


    db.session.delete(
        inquiry
    )


    db.session.commit()



    flash(
        "Inquiry deleted successfully.",
        "success"
    )


    return redirect(
        url_for(
            "admin.inquiries"
        )
    )



# ==========================================
# INQUIRY FILTERS
# ==========================================

@admin.route(
    "/inquiries/new"
)
@admin_required
def new_inquiries():

    inquiries = Inquiry.query.filter_by(
        status="Open"
    ).order_by(
        Inquiry.created_at.desc()
    ).all()


    return render_template(
        "admin_inquiries.html",
        inquiries=inquiries
    )



@admin.route(
    "/inquiries/replied"
)
@admin_required
def replied_inquiries():

    inquiries = Inquiry.query.filter_by(
        status="Replied"
    ).order_by(
        Inquiry.created_at.desc()
    ).all()


    return render_template(
        "admin_inquiries.html",
        inquiries=inquiries
    )
# ==========================================
# ADMIN SEARCH
# ==========================================


# ==========================================
# SEARCH USERS
# ==========================================

@admin.route("/search/users")
@admin_required
def search_users():

    keyword = request.args.get(
        "q"
    )


    if keyword:

        users = User.query.filter(
            db.or_(
                User.name.ilike(
                    f"%{keyword}%"
                ),
                User.email.ilike(
                    f"%{keyword}%"
                ),
                User.phone.ilike(
                    f"%{keyword}%"
                )
            )
        ).all()

    else:

        users = User.query.all()



    return render_template(
        "admin_users.html",
        users=users
    )



# ==========================================
# SEARCH CARS
# ==========================================

@admin.route("/search/cars")
@admin_required
def search_cars():

    keyword = request.args.get(
        "q"
    )


    if keyword:

        cars = Car.query.filter(
            db.or_(
                Car.brand.ilike(
                    f"%{keyword}%"
                ),
                Car.model.ilike(
                    f"%{keyword}%"
                ),
                Car.location.ilike(
                    f"%{keyword}%"
                )
            )
        ).all()

    else:

        cars = Car.query.all()



    return render_template(
        "admin_cars.html",
        cars=cars
    )



# ==========================================
# ADMIN STATISTICS
# ==========================================

@admin.route("/statistics")
@admin_required
def statistics():


    statistics = {

        "users":
            User.query.count(),


        "cars":
            Car.query.count(),


        "approved":
            Car.query.filter_by(
                status="Approved"
            ).count(),


        "pending":
            Car.query.filter_by(
                status="Pending"
            ).count(),


        "inquiries":
            Inquiry.query.count()

    }


    return render_template(
        "admin_statistics.html",
        statistics=statistics
    )



# ==========================================
# ADMIN ERROR HANDLERS
# ==========================================

@admin.errorhandler(404)
def admin_not_found(error):

    flash(
        "Admin page not found.",
        "warning"
    )


    return redirect(
        url_for(
            "admin.dashboard"
        )
    )



@admin.errorhandler(500)
def admin_server_error(error):

    db.session.rollback()


    flash(
        "Something went wrong. Please try again.",
        "danger"
    )


    return redirect(
        url_for(
            "admin.dashboard"
        )
    )