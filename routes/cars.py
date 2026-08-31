
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

from extensions import db

from models import (
    Car,
    CarImage,
    Inquiry,
    InquiryMessage,
    User,
    Favorite,
    CompareCar,
    Notification
)

# =====================================================
# CLOUDINARY
# =====================================================

import cloudinary
import cloudinary.uploader


# =====================================================
# BLUEPRINT
# =====================================================

cars = Blueprint(
    "cars",
    __name__
)


# =====================================================
# IMAGE VALIDATION
# =====================================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


# =====================================================
# CLOUDINARY CONFIGURATION
# =====================================================

def configure_cloudinary():

    cloudinary_url = os.environ.get(
        "CLOUDINARY_URL"
    )

    if cloudinary_url:
        cloudinary.config(
            cloudinary_url=cloudinary_url
        )


# =====================================================
# AVAILABLE CARS
# PUBLIC + ADVANCED SEARCH
# =====================================================

@cars.route("/cars")
def all_cars():

    brand = request.args.get(
        "brand",
        ""
    ).strip()

    model = request.args.get(
        "model",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    fuel = request.args.get(
        "fuel",
        ""
    ).strip()

    transmission = request.args.get(
        "transmission",
        ""
    ).strip()

    min_price = request.args.get(
        "min_price",
        type=int
    )

    max_price = request.args.get(
        "max_price",
        type=int
    )

    min_year = request.args.get(
        "min_year",
        type=int
    )

    max_year = request.args.get(
        "max_year",
        type=int
    )

    min_mileage = request.args.get(
        "min_mileage",
        type=int
    )

    max_mileage = request.args.get(
        "max_mileage",
        type=int
    )

    sort = request.args.get(
        "sort",
        "newest"
    )

    # -------------------------------------------------
    # BASE QUERY
    # -------------------------------------------------

    query = Car.query.filter_by(
        status="Approved"
    )

    # -------------------------------------------------
    # BRAND
    # -------------------------------------------------

    if brand:

        query = query.filter(
            Car.brand.ilike(
                f"%{brand}%"
            )
        )

    # -------------------------------------------------
    # MODEL
    # -------------------------------------------------

    if model:

        query = query.filter(
            Car.model.ilike(
                f"%{model}%"
            )
        )

    # -------------------------------------------------
    # LOCATION
    # -------------------------------------------------

    if location:

        query = query.filter(
            Car.location.ilike(
                f"%{location}%"
            )
        )

    # -------------------------------------------------
    # FUEL
    # -------------------------------------------------

    if fuel:

        query = query.filter(
            Car.fuel == fuel
        )

    # -------------------------------------------------
    # TRANSMISSION
    # -------------------------------------------------

    if transmission:

        query = query.filter(
            Car.transmission == transmission
        )

    # -------------------------------------------------
    # PRICE
    # -------------------------------------------------

    if min_price is not None:

        query = query.filter(
            Car.price >= min_price
        )

    if max_price is not None:

        query = query.filter(
            Car.price <= max_price
        )

    # -------------------------------------------------
    # YEAR
    # -------------------------------------------------

    if min_year is not None:

        query = query.filter(
            Car.year >= min_year
        )

    if max_year is not None:

        query = query.filter(
            Car.year <= max_year
        )

    # -------------------------------------------------
    # MILEAGE
    # -------------------------------------------------

    if min_mileage is not None:

        query = query.filter(
            Car.mileage >= min_mileage
        )

    if max_mileage is not None:

        query = query.filter(
            Car.mileage <= max_mileage
        )

    # -------------------------------------------------
    # SORTING
    # -------------------------------------------------

    if sort == "price_low":

        query = query.order_by(
            Car.price.asc()
        )

    elif sort == "price_high":

        query = query.order_by(
            Car.price.desc()
        )

    elif sort == "year_new":

        query = query.order_by(
            Car.year.desc()
        )

    elif sort == "mileage_low":

        query = query.order_by(
            Car.mileage.asc()
        )

    elif sort == "oldest":

        query = query.order_by(
            Car.created_at.asc()
        )

    else:

        query = query.order_by(
            Car.created_at.desc()
        )

    cars_list = query.all()

    # -------------------------------------------------
    # FAVORITES / COMPARE STATUS
    # -------------------------------------------------

    favorite_ids = set()

    compare_ids = set()

    if current_user.is_authenticated:

        favorite_ids = {
            favorite.car_id
            for favorite in Favorite.query.filter_by(
                user_id=current_user.id
            ).all()
        }

        compare_ids = {
            comparison.car_id
            for comparison in CompareCar.query.filter_by(
                user_id=current_user.id
            ).all()
        }

    return render_template(
        "cars.html",
        cars=cars_list,
        favorite_ids=favorite_ids,
        compare_ids=compare_ids,
        search={
            "brand": brand,
            "model": model,
            "location": location,
            "fuel": fuel,
            "transmission": transmission,
            "min_price": min_price,
            "max_price": max_price,
            "min_year": min_year,
            "max_year": max_year,
            "min_mileage": min_mileage,
            "max_mileage": max_mileage,
            "sort": sort
        }
    )


# =====================================================
# CAR DETAILS
# =====================================================

@cars.route("/car/<int:car_id>")
def car_details(car_id):

    car = Car.query.get_or_404(
        car_id
    )

    # -------------------------------------------------
    # HIDE UNAPPROVED CARS
    # -------------------------------------------------

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

    # -------------------------------------------------
    # FAVORITE / COMPARE STATUS
    # -------------------------------------------------

    is_favorite = False
    is_compare = False

    if current_user.is_authenticated:

        is_favorite = (
            Favorite.query.filter_by(
                user_id=current_user.id,
                car_id=car.id
            ).first()
            is not None
        )

        is_compare = (
            CompareCar.query.filter_by(
                user_id=current_user.id,
                car_id=car.id
            ).first()
            is not None
        )

    return render_template(
        "car_details.html",
        car=car,
        is_favorite=is_favorite,
        is_compare=is_compare
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
            request.form[
                "registration_number"
            ]
            .strip()
            .upper()
        )

        # -------------------------------------------------
        # UPGRADE BUYER TO SELLER
        # -------------------------------------------------

        if current_user.role == "buyer":

            current_user.role = "seller"

            db.session.commit()

        # -------------------------------------------------
        # GET MULTIPLE IMAGES
        # -------------------------------------------------

        images = request.files.getlist(
            "images"
        )

        images = [
            image
            for image in images
            if image
            and image.filename
            and image.filename.strip()
        ]

        # -------------------------------------------------
        # MINIMUM 5 IMAGES
        # -------------------------------------------------

        if len(images) < 5:

            flash(
                "Please upload at least 5 images.",
                "danger"
            )

            return redirect(
                url_for("cars.add_car")
            )

        # -------------------------------------------------
        # VALIDATE IMAGES
        # -------------------------------------------------

        for image in images:

            if not allowed_file(
                image.filename
            ):

                flash(
                    "Invalid image file. "
                    "Allowed formats: JPG, JPEG, PNG and WEBP.",
                    "danger"
                )

                return redirect(
                    url_for("cars.add_car")
                )

        # -------------------------------------------------
        # CHECK REGISTRATION NUMBER
        # -------------------------------------------------

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

        # -------------------------------------------------
        # CREATE CAR
        # -------------------------------------------------

        car = Car(

            registration_number=registration_number,

            seller_id=current_user.id,

            brand=request.form["brand"],

            model=request.form["model"],

            year=int(
                request.form["year"]
            ),

            price=int(
                request.form["price"]
            ),

            mileage=int(
                request.form["mileage"]
            ),

            fuel=request.form["fuel"],

            transmission=request.form[
                "transmission"
            ],

            engine=request.form.get(
                "engine"
            ),

            color=request.form.get(
                "color"
            ),

            condition=request.form.get(
                "condition"
            ),

            location=request.form[
                "location"
            ],

            description=request.form.get(
                "description"
            ),

            status="Pending"
        )

        db.session.add(car)

        db.session.commit()

        # -------------------------------------------------
        # CONFIGURE CLOUDINARY
        # -------------------------------------------------

        configure_cloudinary()

        # -------------------------------------------------
        # UPLOAD IMAGES TO CLOUDINARY
        # -------------------------------------------------

        uploaded_images = []

        try:

            for image in images:

                result = cloudinary.uploader.upload(

                    image,

                    folder="carvion_motors/cars",

                    public_id=(
                        f"{uuid.uuid4().hex}"
                    ),

                    resource_type="image"
                )

                image_url = result.get(
                    "secure_url"
                )

                public_id = result.get(
                    "public_id"
                )

                if not image_url:

                    raise Exception(
                        "Cloudinary did not return an image URL."
                    )

                car_image = CarImage(

                    car_id=car.id,

                    filename=image_url
                )

                # Store public ID if the model supports it.
                if hasattr(
                    car_image,
                    "public_id"
                ):

                    car_image.public_id = public_id

                db.session.add(
                    car_image
                )

                uploaded_images.append(
                    public_id
                )

            db.session.commit()

        except Exception as error:

            db.session.rollback()

            # Attempt to clean up successfully uploaded
            # Cloudinary images if database saving fails.

            for public_id in uploaded_images:

                try:

                    cloudinary.uploader.destroy(
                        public_id
                    )

                except Exception:
                    pass

            # Remove the car because its images failed.

            try:

                db.session.delete(car)

                db.session.commit()

            except Exception:

                db.session.rollback()

            print(
                "CLOUDINARY UPLOAD ERROR:",
                error
            )

            flash(
                "There was a problem uploading the vehicle images. "
                "Please try again.",
                "danger"
            )

            return redirect(
                url_for("cars.add_car")
            )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        flash(
            "Car submitted for approval successfully.",
            "success"
        )

        return redirect(
            url_for("cars.my_cars")
        )

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

@cars.route(
    "/edit_car/<int:car_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_car(car_id):

    car = Car.query.get_or_404(
        car_id
    )

    if car.seller_id != current_user.id:

        flash(
            "You are not allowed to edit this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    if request.method == "POST":

        car.brand = request.form[
            "brand"
        ]

        car.model = request.form[
            "model"
        ]

        car.year = int(
            request.form["year"]
        )

        car.price = int(
            request.form["price"]
        )

        car.mileage = int(
            request.form["mileage"]
        )

        car.fuel = request.form[
            "fuel"
        ]

        car.transmission = request.form[
            "transmission"
        ]

        car.engine = request.form.get(
            "engine"
        )

        car.color = request.form.get(
            "color"
        )

        car.location = request.form[
            "location"
        ]

        car.description = request.form.get(
            "description"
        )

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

    car = Car.query.get_or_404(
        car_id
    )

    if car.seller_id != current_user.id:

        flash(
            "You cannot delete this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    # -------------------------------------------------
    # CONFIGURE CLOUDINARY
    # -------------------------------------------------

    configure_cloudinary()

    # -------------------------------------------------
    # REMOVE CLOUDINARY IMAGES
    # -------------------------------------------------

    for image in car.images:

        try:

            public_id = getattr(
                image,
                "public_id",
                None
            )

            if public_id:

                cloudinary.uploader.destroy(
                    public_id
                )

            else:

                # Try extracting the public ID from URL
                # for older Cloudinary records.

                filename = image.filename or ""

                if "res.cloudinary.com" in filename:

                    parts = filename.split("/")

                    if "upload" in parts:

                        upload_index = parts.index(
                            "upload"
                        )

                        public_parts = parts[
                            upload_index + 1:
                        ]

                        public_parts = [
                            part
                            for part in public_parts
                            if not part.startswith("v")
                        ]

                        public_id = "/".join(
                            public_parts
                        )

                        public_id = os.path.splitext(
                            public_id
                        )[0]

                        if public_id:

                            cloudinary.uploader.destroy(
                                public_id
                            )

        except Exception as error:

            print(
                "CLOUDINARY DELETE ERROR:",
                error
            )

        db.session.delete(
            image
        )

    # -------------------------------------------------
    # DELETE FAVORITES
    # -------------------------------------------------

    Favorite.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -------------------------------------------------
    # DELETE COMPARE RECORDS
    # -------------------------------------------------

    CompareCar.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -------------------------------------------------
    # DELETE NOTIFICATIONS
    # -------------------------------------------------

    Notification.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -------------------------------------------------
    # DELETE CAR
    # -------------------------------------------------

    db.session.delete(
        car
    )

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

    # -------------------------------------------------
    # CONFIGURE CLOUDINARY
    # -------------------------------------------------

    configure_cloudinary()

    # -------------------------------------------------
    # DELETE FROM CLOUDINARY
    # -------------------------------------------------

    try:

        public_id = getattr(
            image,
            "public_id",
            None
        )

        if public_id:

            cloudinary.uploader.destroy(
                public_id
            )

    except Exception as error:

        print(
            "CLOUDINARY IMAGE DELETE ERROR:",
            error
        )

    # -------------------------------------------------
    # DELETE DATABASE RECORD
    # -------------------------------------------------

    db.session.delete(
        image
    )

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
# FAVORITES
# =====================================================

@cars.route(
    "/favorite/<int:car_id>",
    methods=["POST"]
)
@login_required
def toggle_favorite(car_id):

    car = Car.query.get_or_404(
        car_id
    )

    if (
        car.status != "Approved"
        and
        current_user.role != "admin"
    ):

        flash(
            "This vehicle is not available.",
            "warning"
        )

        return redirect(
            request.referrer
            or
            url_for("cars.all_cars")
        )

    favorite = Favorite.query.filter_by(

        user_id=current_user.id,

        car_id=car.id

    ).first()

    # -------------------------------------------------
    # REMOVE
    # -------------------------------------------------

    if favorite:

        db.session.delete(
            favorite
        )

        db.session.commit()

        flash(
            f"{car.brand} {car.model} removed from favorites.",
            "info"
        )

    # -------------------------------------------------
    # ADD
    # -------------------------------------------------

    else:

        favorite = Favorite(

            user_id=current_user.id,

            car_id=car.id
        )

        db.session.add(
            favorite
        )

        notification = Notification(

            user_id=current_user.id,

            car_id=car.id,

            title="Car Added to Favorites",

            message=(
                f"{car.brand} {car.model} "
                "has been saved to your favorites."
            ),

            notification_type="favorite"
        )

        db.session.add(
            notification
        )

        db.session.commit()

        flash(
            f"{car.brand} {car.model} added to favorites.",
            "success"
        )

    return redirect(
        request.referrer
        or
        url_for("cars.all_cars")
    )


# =====================================================
# FAVORITES PAGE
# =====================================================

@cars.route("/favorites")
@login_required
def favorites():

    favorite_records = Favorite.query.filter_by(

        user_id=current_user.id

    ).order_by(

        Favorite.created_at.desc()

    ).all()

    cars_list = [

        favorite.car

        for favorite in favorite_records

        if favorite.car is not None

        and favorite.car.status == "Approved"

    ]

    return render_template(
        "favorites.html",
        cars=cars_list
    )


# =====================================================
# REMOVE FAVORITE
# =====================================================

@cars.route(
    "/favorite/remove/<int:car_id>",
    methods=["POST"]
)
@login_required
def remove_favorite(car_id):

    favorite = Favorite.query.filter_by(

        user_id=current_user.id,

        car_id=car_id

    ).first()

    if favorite:

        db.session.delete(
            favorite
        )

        db.session.commit()

        flash(
            "Vehicle removed from favorites.",
            "success"
        )

    return redirect(
        request.referrer
        or
        url_for("cars.favorites")
    )


# =====================================================
# COMPARE
# =====================================================

@cars.route(
    "/compare/<int:car_id>",
    methods=["POST"]
)
@login_required
def toggle_compare(car_id):

    car = Car.query.get_or_404(
        car_id
    )

    if (
        car.status != "Approved"
        and
        current_user.role != "admin"
    ):

        flash(
            "This vehicle is not available for comparison.",
            "warning"
        )

        return redirect(
            request.referrer
            or
            url_for("cars.all_cars")
        )

    existing = CompareCar.query.filter_by(

        user_id=current_user.id,

        car_id=car.id

    ).first()

    # -------------------------------------------------
    # REMOVE
    # -------------------------------------------------

    if existing:

        db.session.delete(
            existing
        )

        db.session.commit()

        flash(
            f"{car.brand} {car.model} removed from comparison.",
            "info"
        )

    # -------------------------------------------------
    # ADD
    # -------------------------------------------------

    else:

        comparison_count = CompareCar.query.filter_by(

            user_id=current_user.id

        ).count()

        if comparison_count >= 4:

            flash(
                "You can compare a maximum of 4 vehicles.",
                "warning"
            )

            return redirect(
                request.referrer
                or
                url_for("cars.all_cars")
            )

        comparison = CompareCar(

            user_id=current_user.id,

            car_id=car.id
        )

        db.session.add(
            comparison
        )

        notification = Notification(

            user_id=current_user.id,

            car_id=car.id,

            title="Car Added to Compare",

            message=(
                f"{car.brand} {car.model} "
                "has been added to your comparison list."
            ),

            notification_type="compare"
        )

        db.session.add(
            notification
        )

        db.session.commit()

        flash(
            f"{car.brand} {car.model} added to comparison.",
            "success"
        )

    return redirect(
        request.referrer
        or
        url_for("cars.all_cars")
    )


# =====================================================
# COMPARE PAGE
# =====================================================

@cars.route("/compare")
@login_required
def compare():

    records = CompareCar.query.filter_by(

        user_id=current_user.id

    ).order_by(

        CompareCar.created_at.asc()

    ).all()

    cars_list = [

        record.car

        for record in records

        if record.car is not None

        and record.car.status == "Approved"

    ]

    return render_template(
        "compare.html",
        cars=cars_list
    )


# =====================================================
# REMOVE FROM COMPARE
# =====================================================

@cars.route(
    "/compare/remove/<int:car_id>",
    methods=["POST"]
)
@login_required
def remove_compare(car_id):

    comparison = CompareCar.query.filter_by(

        user_id=current_user.id,

        car_id=car_id

    ).first()

    if comparison:

        db.session.delete(
            comparison
        )

        db.session.commit()

        flash(
            "Vehicle removed from comparison.",
            "success"
        )

    return redirect(
        request.referrer
        or
        url_for("cars.compare")
    )


# =====================================================
# CLEAR COMPARE
# =====================================================

@cars.route(
    "/compare/clear",
    methods=["POST"]
)
@login_required
def clear_compare():

    CompareCar.query.filter_by(

        user_id=current_user.id

    ).delete(
        synchronize_session=False
    )

    db.session.commit()

    flash(
        "Comparison list cleared.",
        "success"
    )

    return redirect(
        url_for("cars.compare")
    )


# =====================================================
# NOTIFICATIONS
# =====================================================

@cars.route("/notifications")
@login_required
def notifications():

    notification_list = Notification.query.filter_by(

        user_id=current_user.id

    ).order_by(

        Notification.created_at.desc()

    ).all()

    return render_template(
        "notifications.html",
        notifications=notification_list
    )


# =====================================================
# MARK ONE NOTIFICATION AS READ
# =====================================================

@cars.route(
    "/notification/<int:notification_id>/read",
    methods=["POST"]
)
@login_required
def mark_notification_read(
    notification_id
):

    notification = Notification.query.filter_by(

        id=notification_id,

        user_id=current_user.id

    ).first_or_404()

    notification.is_read = True

    db.session.commit()

    if notification.car_id:

        return redirect(
            url_for(
                "cars.car_details",
                car_id=notification.car_id
            )
        )

    return redirect(
        url_for(
            "cars.notifications"
        )
    )


# =====================================================
# MARK ALL NOTIFICATIONS AS READ
# =====================================================

@cars.route(
    "/notifications/read-all",
    methods=["POST"]
)
@login_required
def mark_all_notifications_read():

    Notification.query.filter_by(

        user_id=current_user.id,

        is_read=False

    ).update(

        {
            "is_read": True
        },

        synchronize_session=False
    )

    db.session.commit()

    flash(
        "All notifications marked as read.",
        "success"
    )

    return redirect(
        url_for(
            "cars.notifications"
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

    car = Car.query.get_or_404(
        car_id
    )

    # -------------------------------------------------
    # ONLY BUYERS
    # -------------------------------------------------

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

    # -------------------------------------------------
    # SELLER CANNOT CONTACT THEMSELVES
    # -------------------------------------------------

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

    # -------------------------------------------------
    # FIND EXISTING INQUIRY
    # -------------------------------------------------

    inquiry = Inquiry.query.filter_by(

        car_id=car.id,

        buyer_id=current_user.id,

        seller_id=car.seller_id

    ).first()

    # -------------------------------------------------
    # CREATE INQUIRY
    # -------------------------------------------------

    if not inquiry:

        inquiry = Inquiry(

            car_id=car.id,

            buyer_id=current_user.id,

            seller_id=car.seller_id,

            status="Open"
        )

        db.session.add(
            inquiry
        )

        db.session.commit()

    # -------------------------------------------------
    # CREATE MESSAGE
    # -------------------------------------------------

    message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=car.seller_id,

        sender_role=current_user.role,

        message=message_text,

        is_read=False
    )

    db.session.add(
        message
    )

    inquiry.status = "Open"

    db.session.commit()

    # -------------------------------------------------
    # SELLER NOTIFICATION
    # -------------------------------------------------

    notification = Notification(

        user_id=car.seller_id,

        car_id=car.id,

        title="New Vehicle Inquiry",

        message=(
            f"{current_user.name} sent you a "
            f"new inquiry about "
            f"{car.brand} {car.model}."
        ),

        notification_type="inquiry"
    )

    db.session.add(
        notification
    )

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

    car = Car.query.get_or_404(
        car_id
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

    # -------------------------------------------------
    # CREATE INQUIRY
    # -------------------------------------------------

    inquiry = Inquiry(

        car_id=car.id,

        buyer_id=current_user.id,

        seller_id=car.seller_id,

        status="Open"
    )

    db.session.add(
        inquiry
    )

    db.session.commit()

    # -------------------------------------------------
    # FIND ADMIN
    # -------------------------------------------------

    admin = User.query.filter_by(
        role="admin"
    ).first()

    if not admin:

        flash(
            "No administrator is currently available.",
            "danger"
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id
            )
        )

    # -------------------------------------------------
    # FIRST MESSAGE TO ADMIN
    # -------------------------------------------------

    message = InquiryMessage(

        inquiry_id=inquiry.id,

        sender_id=current_user.id,

        receiver_id=admin.id,

        sender_role=current_user.role,

        message=message_text,

        is_read=False
    )

    db.session.add(
        message
    )

    # -------------------------------------------------
    # ADMIN NOTIFICATION
    # -------------------------------------------------

    notification = Notification(

        user_id=admin.id,

        car_id=car.id,

        title="New Contact Request",

        message=(
            f"{current_user.name} contacted "
            f"you regarding "
            f"{car.brand} {car.model}."
        ),

        notification_type="inquiry"
    )

    db.session.add(
        notification
    )

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
