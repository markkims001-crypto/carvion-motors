# routes/cars.py

import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app
)

from flask_login import (
    login_required,
    current_user
)

from werkzeug.utils import secure_filename

from extensions import db

from models import (
    Car,
    CarImage,
    Inquiry,
    InquiryMessage,
    User
)


cars = Blueprint(
    "cars",
    __name__
)


# =====================================================
# IMAGE VALIDATION
# =====================================================

def allowed_file(filename):

    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )



# =====================================================
# AVAILABLE CARS (PUBLIC)
# =====================================================

@cars.route("/cars")
def all_cars():

    brand = request.args.get("brand")
    location = request.args.get("location")
    fuel = request.args.get("fuel")
    transmission = request.args.get("transmission")

    query = Car.query.filter_by(
        status="Approved"
    )


    if brand:
        query = query.filter(
            Car.brand.ilike(f"%{brand}%")
        )


    if location:
        query = query.filter(
            Car.location.ilike(f"%{location}%")
        )


    if fuel:
        query = query.filter(
            Car.fuel == fuel
        )


    if transmission:
        query = query.filter(
            Car.transmission == transmission
        )


    cars_list = query.order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "cars.html",
        cars=cars_list
    )



# =====================================================
# CAR DETAILS
# =====================================================

@cars.route("/car/<int:car_id>")
def car_details(car_id):

    car = Car.query.get_or_404(
        car_id
    )


    # hide unapproved cars

    if car.status != "Approved":

        if (
            not current_user.is_authenticated
            or current_user.role != "admin"
        ):

            flash(
                "Vehicle not available yet.",
                "warning"
            )

            return redirect(
                url_for("cars.all_cars")
            )


    return render_template(
        "car_details.html",
        car=car
    )



# =====================================================
# ADD CAR LISTING
# =====================================================

@cars.route(
    "/add_car",
    methods=["GET", "POST"]
)
@login_required
def add_car():

    if request.method == "POST":

        registration_number = (
            request.form["registration_number"]
            .strip()
            .upper()
        )


        # Upgrade buyer to seller

        if current_user.role == "buyer":

            current_user.role = "seller"

            db.session.commit()


        # ==========================
        # GET MULTIPLE IMAGES
        # ==========================

        images = request.files.getlist("images")


        images = [
            img for img in images
            if img.filename != ""
        ]


        if len(images) < 5:

            flash(
                "Please upload at least 5 images.",
                "danger"
            )

            return redirect(
                url_for("cars.add_car")
            )


        for image in images:

            if not allowed_file(image.filename):

                flash(
                    "Invalid image file.",
                    "danger"
                )

                return redirect(
                    url_for("cars.add_car")
                )



        # ==========================
        # CHECK NUMBER PLATE
        # ==========================

        existing_car = Car.query.filter_by(
            registration_number=registration_number
        ).first()


        if existing_car:

            flash(
                "This vehicle already exists.",
                "warning"
            )

            return redirect(
                url_for("cars.add_car")
            )



        # ==========================
        # SAVE CAR
        # ==========================

        car = Car(

            registration_number=registration_number,

            seller_id=current_user.id,

            brand=request.form["brand"],

            model=request.form["model"],

            year=int(request.form["year"]),

            price=int(request.form["price"]),

            mileage=int(request.form["mileage"]),

            fuel=request.form["fuel"],

            transmission=request.form["transmission"],

            engine=request.form.get("engine"),

            color=request.form.get("color"),

            condition=request.form.get("condition"),

            location=request.form["location"],

            description=request.form.get("description"),

            status="Pending"
        )


        db.session.add(car)

        db.session.commit()



        # ==========================
        # SAVE IMAGES
        # ==========================

        upload_folder = current_app.config["UPLOAD_FOLDER"]


        for image in images:


            extension = image.filename.rsplit(".", 1)[1].lower()


            filename = (
                str(uuid.uuid4())
                + "."
                + extension
            )


            image.save(
                os.path.join(
                    upload_folder,
                    filename
                )
            )


            car_image = CarImage(

                car_id=car.id,

                filename="uploads/" + filename

            )


            db.session.add(car_image)



        db.session.commit()


        flash(
            "Car submitted for approval.",
            "success"
        )


        return redirect(
            url_for("cars.my_cars")
        )


    # THIS MUST BE HERE
    return render_template(
        "add_car.html"
    )
# =====================================================
# SELLER DASHBOARD
# =====================================================

@cars.route("/seller/dashboard")
@login_required
def seller_dashboard():

    if current_user.role != "seller":

        flash(
            "Seller access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    my_cars = Car.query.filter_by(
        seller_id=current_user.id
    ).order_by(
        Car.created_at.desc()
    ).all()


    stats = {

        "total": Car.query.filter_by(
            seller_id=current_user.id
        ).count(),


        "approved": Car.query.filter_by(
            seller_id=current_user.id,
            status="Approved"
        ).count(),


        "pending": Car.query.filter_by(
            seller_id=current_user.id,
            status="Pending"
        ).count(),


        "rejected": Car.query.filter_by(
            seller_id=current_user.id,
            status="Rejected"
        ).count()

    }


    return render_template(
        "seller_dashboard.html",
        cars=my_cars,
        stats=stats
    )
# =====================================================
# MY CAR LISTINGS
# =====================================================

@cars.route("/my_cars")
@login_required
def my_cars():

    if current_user.role != "seller":

        flash(
            "Seller access required.",
            "danger"
        )

        return redirect(
            url_for("home")
        )


    cars_list = Car.query.filter_by(
        seller_id=current_user.id
    ).order_by(
        Car.created_at.desc()
    ).all()


    return render_template(
        "dashboard.html",
        cars=cars_list
    )
# =====================================================
# EDIT CAR
# =====================================================

@cars.route("/edit_car/<int:car_id>", methods=["GET", "POST"])
@login_required
def edit_car(car_id):

    car = Car.query.get_or_404(car_id)

    if car.seller_id != current_user.id:

        flash(
            "You are not allowed to edit this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )


    if request.method == "POST":

        car.brand = request.form["brand"]
        car.model = request.form["model"]
        car.year = int(request.form["year"])
        car.price = int(request.form["price"])
        car.mileage = int(request.form["mileage"])
        car.fuel = request.form["fuel"]
        car.transmission = request.form["transmission"]
        car.engine = request.form.get("engine")
        car.color = request.form.get("color")
        car.location = request.form["location"]
        car.description = request.form.get("description")


        db.session.commit()


        flash(
            "Car updated successfully.",
            "success"
        )


        return redirect(
            url_for("cars.seller_dashboard")
        )


    return render_template(
        "edit_car.html",
        car=car
    )



# =====================================================
# DELETE CAR
# =====================================================

@cars.route(
    "/delete_car/<int:car_id>",
    methods=["POST"]
)
@login_required
def delete_car(car_id):

    car = Car.query.get_or_404(car_id)


    if car.seller_id != current_user.id:

        flash(
            "You cannot delete this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )


    # remove images from folder

    for image in car.images:

        path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            image.filename.replace(
                "uploads/",
                ""
            )
        )


        if os.path.exists(path):

            os.remove(path)



        db.session.delete(image)



    db.session.delete(car)

    db.session.commit()


    flash(
        "Car removed successfully.",
        "success"
    )


    return redirect(
        url_for("cars.seller_dashboard")
    )



# =====================================================
# DELETE SINGLE IMAGE
# =====================================================

@cars.route(
    "/delete_image/<int:image_id>",
    methods=["POST"]
)
@login_required
def delete_image(image_id):

    image = CarImage.query.get_or_404(
        image_id
    )


    car = Car.query.get_or_404(
        image.car_id
    )


    if car.seller_id != current_user.id:

        flash(
            "Permission denied.",
            "danger"
        )

        return redirect(
            url_for("cars.all_cars")
        )



    path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        image.filename.replace(
            "uploads/",
            ""
        )
    )


    if os.path.exists(path):

        os.remove(path)



    db.session.delete(image)

    db.session.commit()


    flash(
        "Image deleted.",
        "success"
    )


    return redirect(
        url_for(
            "cars.car_details",
            car_id=car.id
        )
    )



# =====================================================
# BUYER SENDS INQUIRY
# =====================================================

@cars.route(
    "/inquiry/<int:car_id>",
    methods=["POST"]
)
@login_required
def send_inquiry(car_id):

    car = Car.query.get_or_404(car_id)


    # Only buyers can start buyer-seller inquiries

    if current_user.role != "buyer":

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


    # Seller cannot contact themselves

    if current_user.id == car.seller_id:

        flash(
            "You cannot inquire about your own car.",
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


    # Find existing conversation

    inquiry = Inquiry.query.filter_by(

        car_id=car.id,

        buyer_id=current_user.id,

        seller_id=car.seller_id

    ).first()


    # Create inquiry if it doesn't exist

    if not inquiry:

        inquiry = Inquiry(

            car_id=car.id,

            buyer_id=current_user.id,

            seller_id=car.seller_id,

            status="Open"
        )

        db.session.add(inquiry)

        db.session.commit()


    # Create the actual message

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


    flash(
        "Message sent to the seller.",
        "success"
    )


    return redirect(
        url_for(
            "chat.inquiry_chat",
            inquiry_id=inquiry.id
        )
    )



# =====================================================
# BUYER INQUIRIES
# =====================================================

@cars.route("/buyer_inquiries")
@login_required
def buyer_inquiries():

    inquiries = Inquiry.query.filter_by(
        buyer_id=current_user.id
    ).order_by(
        Inquiry.created_at.desc()
    ).all()


    return render_template(
        "buyer_inquiries.html",
        inquiries=inquiries
    )



# =====================================================
# SELLER INQUIRIES
# =====================================================

@cars.route("/seller_inquiries")
@login_required
def seller_inquiries():

    inquiries = Inquiry.query.filter_by(
        seller_id=current_user.id
    ).order_by(
        Inquiry.created_at.desc()
    ).all()


    return render_template(
        "seller_inquiries.html",
        inquiries=inquiries
    )
# =====================================================
# BUYER CONTACT ADMIN / SELLER
# =====================================================

@cars.route(
    "/contact_seller/<int:car_id>",
    methods=["POST"]
)
@login_required
def contact_seller(car_id):

    car = Car.query.get_or_404(car_id)


    message_text = request.form.get(
        "message"
    )


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



    # Create inquiry

    inquiry = Inquiry(

        car_id=car.id,

        buyer_id=current_user.id,

        seller_id=car.seller_id,

        status="Open"

    )


    db.session.add(inquiry)

    db.session.commit()



    # Create first message

    admin = User.query.filter_by(role="admin").first()

    message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=admin.id,

        sender_role=current_user.role,

        message=message_text

    )


    db.session.add(message)

    db.session.commit()



    flash(
        "Your request has been sent successfully.",
        "success"
    )


    return redirect(
        url_for(
            "cars.car_details",
            car_id=car.id
        )
    )
