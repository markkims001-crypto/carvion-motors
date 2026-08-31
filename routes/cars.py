
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
    current_app,
)

from flask_login import login_required, current_user

from extensions import db

from models import (
    Car,
    CarImage,
    Inquiry,
    InquiryMessage,
    User,
    Favorite,
    CompareCar,
    Notification,
)

import cloudinary
import cloudinary.uploader


# =========================================================
# BLUEPRINT
# =========================================================

cars = Blueprint("cars", __name__)


# =========================================================
# HELPERS
# =========================================================

def allowed_file(filename):
    """Check whether an uploaded image has an allowed extension."""

    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    allowed_extensions = current_app.config.get(
        "ALLOWED_EXTENSIONS",
        {"jpg", "jpeg", "png", "webp"},
    )

    return extension in allowed_extensions


def configure_cloudinary():
    """Configure Cloudinary using the CLOUDINARY_URL environment variable."""

    cloudinary_url = os.environ.get("CLOUDINARY_URL")

    if cloudinary_url:
        cloudinary.config(cloudinary_url=cloudinary_url)


def get_favorite_ids():
    """Return the current user's favorite car IDs."""

    if not current_user.is_authenticated:
        return set()

    return {
        favorite.car_id
        for favorite in Favorite.query.filter_by(
            user_id=current_user.id
        ).all()
    }


def get_compare_ids():
    """Return the current user's comparison car IDs."""

    if not current_user.is_authenticated:
        return set()

    return {
        comparison.car_id
        for comparison in CompareCar.query.filter_by(
            user_id=current_user.id
        ).all()
    }


# =========================================================
# AVAILABLE CARS
# PUBLIC + SEARCH + FILTERING
# =========================================================

@cars.route("/cars")
def all_cars():

    brand = request.args.get("brand", "").strip()
    model = request.args.get("model", "").strip()
    location = request.args.get("location", "").strip()
    fuel = request.args.get("fuel", "").strip()
    transmission = request.args.get("transmission", "").strip()

    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)

    min_year = request.args.get("min_year", type=int)
    max_year = request.args.get("max_year", type=int)

    min_mileage = request.args.get("min_mileage", type=int)
    max_mileage = request.args.get("max_mileage", type=int)

    sort = request.args.get("sort", "newest").strip()

    # -----------------------------------------------------
    # BASE QUERY
    # -----------------------------------------------------

    query = Car.query.filter(
        Car.status == "Approved"
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if brand:
        query = query.filter(
            Car.brand.ilike(f"%{brand}%")
        )

    if model:
        query = query.filter(
            Car.model.ilike(f"%{model}%")
        )

    if location:
        query = query.filter(
            Car.location.ilike(f"%{location}%")
        )

    # -----------------------------------------------------
    # FUEL
    # -----------------------------------------------------

    if fuel:
        query = query.filter(
            Car.fuel == fuel
        )

    # -----------------------------------------------------
    # TRANSMISSION
    # -----------------------------------------------------

    if transmission:
        query = query.filter(
            Car.transmission == transmission
        )

    # -----------------------------------------------------
    # PRICE
    # -----------------------------------------------------

    if min_price is not None:
        query = query.filter(
            Car.price >= min_price
        )

    if max_price is not None:
        query = query.filter(
            Car.price <= max_price
        )

    # -----------------------------------------------------
    # YEAR
    # -----------------------------------------------------

    if min_year is not None:
        query = query.filter(
            Car.year >= min_year
        )

    if max_year is not None:
        query = query.filter(
            Car.year <= max_year
        )

    # -----------------------------------------------------
    # MILEAGE
    # -----------------------------------------------------

    if min_mileage is not None:
        query = query.filter(
            Car.mileage >= min_mileage
        )

    if max_mileage is not None:
        query = query.filter(
            Car.mileage <= max_mileage
        )

    # -----------------------------------------------------
    # SORTING
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # GET CARS
    # -----------------------------------------------------

    cars_list = query.all()

    # -----------------------------------------------------
    # FAVORITES + COMPARE
    # -----------------------------------------------------

    favorite_ids = get_favorite_ids()
    compare_ids = get_compare_ids()

    # -----------------------------------------------------
    # SEARCH DATA
    # -----------------------------------------------------

    search = {
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
        "sort": sort,
    }

    return render_template(
        "cars.html",
        cars=cars_list,
        favorite_ids=favorite_ids,
        compare_ids=compare_ids,
        search=search,
    )


# =========================================================
# CAR DETAILS
# =========================================================

@cars.route("/car/<int:car_id>")
def car_details(car_id):

    car = Car.query.get_or_404(car_id)

    # -----------------------------------------------------
    # HIDE UNAPPROVED VEHICLES
    # -----------------------------------------------------

    if car.status != "Approved":

        if (
            not current_user.is_authenticated
            or current_user.role.lower() != "admin"
        ):

            flash(
                "Vehicle not available yet.",
                "warning",
            )

            return redirect(
                url_for("cars.all_cars")
            )

    # -----------------------------------------------------
    # FAVORITE STATUS
    # -----------------------------------------------------

    is_favorite = False
    is_compare = False

    if current_user.is_authenticated:

        is_favorite = (
            Favorite.query.filter_by(
                user_id=current_user.id,
                car_id=car.id,
            ).first()
            is not None
        )

        is_compare = (
            CompareCar.query.filter_by(
                user_id=current_user.id,
                car_id=car.id,
            ).first()
            is not None
        )

    return render_template(
        "car_details.html",
        car=car,
        is_favorite=is_favorite,
        is_compare=is_compare,
    )


# =========================================================
# ADD CAR
# =========================================================

@cars.route("/add_car", methods=["GET", "POST"])
@login_required
def add_car():

    if request.method == "GET":
        return render_template("add_car.html")

    # -----------------------------------------------------
    # BASIC FORM DATA
    # -----------------------------------------------------

    try:

        registration_number = request.form.get(
            "registration_number",
            "",
        ).strip().upper()

        brand = request.form.get(
            "brand",
            "",
        ).strip()

        model = request.form.get(
            "model",
            "",
        ).strip()

        year = int(
            request.form.get("year", 0)
        )

        price = int(
            request.form.get("price", 0)
        )

        mileage = int(
            request.form.get("mileage", 0)
        )

        fuel = request.form.get(
            "fuel",
            "",
        ).strip()

        transmission = request.form.get(
            "transmission",
            "",
        ).strip()

        location = request.form.get(
            "location",
            "",
        ).strip()

    except (TypeError, ValueError):

        flash(
            "Please enter valid vehicle information.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------------------

    if not registration_number:
        flash(
            "Registration number is required.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    if not brand or not model:
        flash(
            "Brand and model are required.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    if year <= 0 or price <= 0 or mileage < 0:
        flash(
            "Please enter valid year, price and mileage.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # IMAGES
    # -----------------------------------------------------

    images = request.files.getlist("images")

    images = [
        image
        for image in images
        if image
        and image.filename
        and image.filename.strip()
    ]

    if len(images) < 5:

        flash(
            "Please upload at least 5 images.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # VALIDATE IMAGES
    # -----------------------------------------------------

    for image in images:

        if not allowed_file(image.filename):

            flash(
                "Invalid image file. "
                "Allowed formats: JPG, JPEG, PNG and WEBP.",
                "danger",
            )

            return redirect(
                url_for("cars.add_car")
            )

    # -----------------------------------------------------
    # REGISTRATION CHECK
    # -----------------------------------------------------

    existing_car = Car.query.filter_by(
        registration_number=registration_number
    ).first()

    if existing_car:

        flash(
            "This vehicle already exists.",
            "warning",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # CREATE CAR
    # -----------------------------------------------------

    car = Car(
        registration_number=registration_number,
        seller_id=current_user.id,
        brand=brand,
        model=model,
        year=year,
        price=price,
        mileage=mileage,
        fuel=fuel,
        transmission=transmission,
        engine=request.form.get("engine"),
        color=request.form.get("color"),
        condition=request.form.get("condition"),
        location=location,
        description=request.form.get("description"),
        status="Pending",
    )

    db.session.add(car)

    try:

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "CAR DATABASE ERROR:",
            error,
        )

        flash(
            "Unable to save the vehicle.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # CLOUDINARY
    # -----------------------------------------------------

    configure_cloudinary()

    uploaded_public_ids = []

    try:

        for image in images:

            result = cloudinary.uploader.upload(
                image,
                folder="carvion_motors/cars",
                public_id=uuid.uuid4().hex,
                resource_type="image",
            )

            image_url = result.get("secure_url")
            public_id = result.get("public_id")

            if not image_url:

                raise Exception(
                    "Cloudinary did not return a secure image URL."
                )

            car_image = CarImage(
                car_id=car.id,
                filename=image_url,
            )

            # Only use public_id if the model has it.
            if hasattr(car_image, "public_id"):
                car_image.public_id = public_id

            db.session.add(car_image)

            if public_id:
                uploaded_public_ids.append(public_id)

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "CLOUDINARY UPLOAD ERROR:",
            error,
        )

        # -------------------------------------------------
        # REMOVE CLOUDINARY UPLOADS
        # -------------------------------------------------

        for public_id in uploaded_public_ids:

            try:

                cloudinary.uploader.destroy(
                    public_id
                )

            except Exception as cleanup_error:

                print(
                    "CLOUDINARY CLEANUP ERROR:",
                    cleanup_error,
                )

        # -------------------------------------------------
        # REMOVE CAR
        # -------------------------------------------------

        try:

            saved_car = db.session.get(
                Car,
                car.id,
            )

            if saved_car:

                db.session.delete(
                    saved_car
                )

                db.session.commit()

        except Exception as delete_error:

            db.session.rollback()

            print(
                "CAR CLEANUP ERROR:",
                delete_error,
            )

        flash(
            "There was a problem uploading the vehicle images. "
            "Please check your Cloudinary configuration.",
            "danger",
        )

        return redirect(
            url_for("cars.add_car")
        )

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    flash(
        "Car submitted for approval successfully.",
        "success",
    )

    return redirect(
        url_for("cars.my_cars")
    )


# =========================================================
# SELLER DASHBOARD
# =========================================================

@cars.route("/seller/dashboard")
@login_required
def seller_dashboard():

    if current_user.role.lower() != "seller":

        flash(
            "Seller access required.",
            "danger",
        )

        return redirect(
            url_for("home")
        )

    my_cars = (
        Car.query
        .filter_by(
            seller_id=current_user.id
        )
        .order_by(
            Car.created_at.desc()
        )
        .all()
    )

    stats = {
        "total": Car.query.filter_by(
            seller_id=current_user.id
        ).count(),

        "approved": Car.query.filter_by(
            seller_id=current_user.id,
            status="Approved",
        ).count(),

        "pending": Car.query.filter_by(
            seller_id=current_user.id,
            status="Pending",
        ).count(),

        "rejected": Car.query.filter_by(
            seller_id=current_user.id,
            status="Rejected",
        ).count(),
    }

    return render_template(
        "seller_dashboard.html",
        cars=my_cars,
        stats=stats,
    )


# =========================================================
# MY CAR LISTINGS
# =========================================================

@cars.route("/my_cars")
@login_required
def my_cars():

    if current_user.role.lower() != "seller":

        flash(
            "Seller access required.",
            "danger",
        )

        return redirect(
            url_for("home")
        )

    cars_list = (
        Car.query
        .filter_by(
            seller_id=current_user.id
        )
        .order_by(
            Car.created_at.desc()
        )
        .all()
    )

    return render_template(
        "dashboard.html",
        cars=cars_list,
    )


# =========================================================
# EDIT CAR
# =========================================================

@cars.route(
    "/edit_car/<int:car_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_car(car_id):

    car = Car.query.get_or_404(car_id)

    if car.seller_id != current_user.id:

        flash(
            "You are not allowed to edit this car.",
            "danger",
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    if request.method == "POST":

        try:

            car.brand = request.form.get(
                "brand",
                "",
            ).strip()

            car.model = request.form.get(
                "model",
                "",
            ).strip()

            car.year = int(
                request.form.get("year", 0)
            )

            car.price = int(
                request.form.get("price", 0)
            )

            car.mileage = int(
                request.form.get("mileage", 0)
            )

            car.fuel = request.form.get(
                "fuel",
                "",
            ).strip()

            car.transmission = request.form.get(
                "transmission",
                "",
            ).strip()

            car.engine = request.form.get(
                "engine"
            )

            car.color = request.form.get(
                "color"
            )

            car.condition = request.form.get(
                "condition"
            )

            car.location = request.form.get(
                "location",
                "",
            ).strip()

            car.description = request.form.get(
                "description"
            )

            db.session.commit()

        except (TypeError, ValueError):

            db.session.rollback()

            flash(
                "Please enter valid vehicle information.",
                "danger",
            )

            return redirect(
                url_for(
                    "cars.edit_car",
                    car_id=car.id,
                )
            )

        flash(
            "Car updated successfully.",
            "success",
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    return render_template(
        "edit_car.html",
        car=car,
    )


# =========================================================
# DELETE CAR
# =========================================================

@cars.route(
    "/delete_car/<int:car_id>",
    methods=["POST"],
)
@login_required
def delete_car(car_id):

    car = Car.query.get_or_404(car_id)

    if car.seller_id != current_user.id:

        flash(
            "You cannot delete this car.",
            "danger",
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    configure_cloudinary()

    # -----------------------------------------------------
    # DELETE CLOUDINARY IMAGES
    # -----------------------------------------------------

    for image in list(car.images):

        try:

            public_id = getattr(
                image,
                "public_id",
                None,
            )

            if public_id:

                cloudinary.uploader.destroy(
                    public_id
                )

        except Exception as error:

            print(
                "CLOUDINARY DELETE ERROR:",
                error,
            )

        try:

            db.session.delete(image)

        except Exception as error:

            print(
                "IMAGE DATABASE DELETE ERROR:",
                error,
            )

    # -----------------------------------------------------
    # DELETE FAVORITES
    # -----------------------------------------------------

    Favorite.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -----------------------------------------------------
    # DELETE COMPARISON RECORDS
    # -----------------------------------------------------

    CompareCar.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -----------------------------------------------------
    # DELETE NOTIFICATIONS
    # -----------------------------------------------------

    Notification.query.filter_by(
        car_id=car.id
    ).delete(
        synchronize_session=False
    )

    # -----------------------------------------------------
    # DELETE CAR
    # -----------------------------------------------------

    db.session.delete(car)

    try:

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "CAR DELETE ERROR:",
            error,
        )

        flash(
            "Unable to delete the vehicle.",
            "danger",
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    flash(
        "Car removed successfully.",
        "success",
    )

    return redirect(
        url_for("cars.seller_dashboard")
    )


# =========================================================
# DELETE SINGLE IMAGE
# =========================================================

@cars.route(
    "/delete_image/<int:image_id>",
    methods=["POST"],
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
            "danger",
        )

        return redirect(
            url_for("cars.all_cars")
        )

    configure_cloudinary()

    # -----------------------------------------------------
    # DELETE CLOUDINARY IMAGE
    # -----------------------------------------------------

    try:

        public_id = getattr(
            image,
            "public_id",
            None,
        )

        if public_id:

            cloudinary.uploader.destroy(
                public_id
            )

    except Exception as error:

        print(
            "CLOUDINARY IMAGE DELETE ERROR:",
            error,
        )

    # -----------------------------------------------------
    # DELETE DATABASE RECORD
    # -----------------------------------------------------

    db.session.delete(image)

    try:

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "IMAGE DATABASE DELETE ERROR:",
            error,
        )

        flash(
            "Unable to delete the image.",
            "danger",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    flash(
        "Image deleted.",
        "success",
    )

    return redirect(
        url_for(
            "cars.car_details",
            car_id=car.id,
        )
    )


# =========================================================
# FAVORITES
# =========================================================

@cars.route(
    "/favorite/<int:car_id>",
    methods=["POST"],
)
@login_required
def toggle_favorite(car_id):

    car = Car.query.get_or_404(car_id)

    if (
        car.status != "Approved"
        and current_user.role.lower() != "admin"
    ):

        flash(
            "This vehicle is not available.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    favorite = Favorite.query.filter_by(
        user_id=current_user.id,
        car_id=car.id,
    ).first()

    # -----------------------------------------------------
    # REMOVE
    # -----------------------------------------------------

    if favorite:

        db.session.delete(favorite)

        db.session.commit()

        flash(
            f"{car.brand} {car.model} removed from favorites.",
            "info",
        )

    # -----------------------------------------------------
    # ADD
    # -----------------------------------------------------

    else:

        favorite = Favorite(
            user_id=current_user.id,
            car_id=car.id,
        )

        db.session.add(favorite)

        notification = Notification(
            user_id=current_user.id,
            car_id=car.id,
            title="Car Added to Favorites",
            message=(
                f"{car.brand} {car.model} "
                "has been saved to your favorites."
            ),
            notification_type="favorite",
        )

        db.session.add(notification)

        db.session.commit()

        flash(
            f"{car.brand} {car.model} added to favorites.",
            "success",
        )

    return redirect(
        request.referrer
        or url_for("cars.all_cars")
    )


# =========================================================
# FAVORITES PAGE
# =========================================================

@cars.route("/favorites")
@login_required
def favorites():

    favorite_records = (
        Favorite.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Favorite.created_at.desc()
        )
        .all()
    )

    cars_list = [
        favorite.car
        for favorite in favorite_records
        if favorite.car is not None
        and favorite.car.status == "Approved"
    ]

    return render_template(
        "favorites.html",
        cars=cars_list,
    )


# =========================================================
# REMOVE FAVORITE
# =========================================================

@cars.route(
    "/favorite/remove/<int:car_id>",
    methods=["POST"],
)
@login_required
def remove_favorite(car_id):

    favorite = Favorite.query.filter_by(
        user_id=current_user.id,
        car_id=car_id,
    ).first()

    if favorite:

        db.session.delete(favorite)
        db.session.commit()

        flash(
            "Vehicle removed from favorites.",
            "success",
        )

    return redirect(
        request.referrer
        or url_for("cars.favorites")
    )


# =========================================================
# COMPARE
# =========================================================

@cars.route(
    "/compare/<int:car_id>",
    methods=["POST"],
)
@login_required
def toggle_compare(car_id):

    car = Car.query.get_or_404(car_id)

    if (
        car.status != "Approved"
        and current_user.role.lower() != "admin"
    ):

        flash(
            "This vehicle is not available for comparison.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    existing = CompareCar.query.filter_by(
        user_id=current_user.id,
        car_id=car.id,
    ).first()

    # -----------------------------------------------------
    # REMOVE
    # -----------------------------------------------------

    if existing:

        db.session.delete(existing)
        db.session.commit()

        flash(
            f"{car.brand} {car.model} removed from comparison.",
            "info",
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    # -----------------------------------------------------
    # MAXIMUM 4
    # -----------------------------------------------------

    comparison_count = CompareCar.query.filter_by(
        user_id=current_user.id
    ).count()

    if comparison_count >= 4:

        flash(
            "You can compare a maximum of 4 vehicles.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    # -----------------------------------------------------
    # ADD
    # -----------------------------------------------------

    comparison = CompareCar(
        user_id=current_user.id,
        car_id=car.id,
    )

    db.session.add(comparison)

    notification = Notification(
        user_id=current_user.id,
        car_id=car.id,
        title="Car Added to Compare",
        message=(
            f"{car.brand} {car.model} "
            "has been added to your comparison list."
        ),
        notification_type="compare",
    )

    db.session.add(notification)

    db.session.commit()

    flash(
        f"{car.brand} {car.model} added to comparison.",
        "success",
    )

    return redirect(
        request.referrer
        or url_for("cars.all_cars")
    )


# =========================================================
# COMPARE PAGE
# =========================================================

@cars.route("/compare")
@login_required
def compare():

    records = (
        CompareCar.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            CompareCar.created_at.asc()
        )
        .all()
    )

    cars_list = [
        record.car
        for record in records
        if record.car is not None
        and record.car.status == "Approved"
    ]

    return render_template(
        "compare.html",
        cars=cars_list,
    )


# =========================================================
# REMOVE FROM COMPARE
# =========================================================

@cars.route(
    "/compare/remove/<int:car_id>",
    methods=["POST"],
)
@login_required
def remove_compare(car_id):

    comparison = CompareCar.query.filter_by(
        user_id=current_user.id,
        car_id=car_id,
    ).first()

    if comparison:

        db.session.delete(comparison)
        db.session.commit()

        flash(
            "Vehicle removed from comparison.",
            "success",
        )

    return redirect(
        request.referrer
        or url_for("cars.compare")
    )


# =========================================================
# CLEAR COMPARE
# =========================================================

@cars.route(
    "/compare/clear",
    methods=["POST"],
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
        "success",
    )

    return redirect(
        url_for("cars.compare")
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

@cars.route("/notifications")
@login_required
def notifications():

    notification_list = (
        Notification.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Notification.created_at.desc()
        )
        .all()
    )

    return render_template(
        "notifications.html",
        notifications=notification_list,
    )


# =========================================================
# MARK ONE NOTIFICATION AS READ
# =========================================================

@cars.route(
    "/notification/<int:notification_id>/read",
    methods=["POST"],
)
@login_required
def mark_notification_read(notification_id):

    notification = (
        Notification.query
        .filter_by(
            id=notification_id,
            user_id=current_user.id,
        )
        .first_or_404()
    )

    notification.is_read = True

    db.session.commit()

    if notification.car_id:

        return redirect(
            url_for(
                "cars.car_details",
                car_id=notification.car_id,
            )
        )

    return redirect(
        url_for("cars.notifications")
    )


# =========================================================
# MARK ALL NOTIFICATIONS AS READ
# =========================================================

@cars.route(
    "/notifications/read-all",
    methods=["POST"],
)
@login_required
def mark_all_notifications_read():

    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).update(
        {
            "is_read": True,
        },
        synchronize_session=False,
    )

    db.session.commit()

    flash(
        "All notifications marked as read.",
        "success",
    )

    return redirect(
        url_for("cars.notifications")
    )


# =========================================================
# BUYER SENDS INQUIRY
# =========================================================

@cars.route(
    "/inquiry/<int:car_id>",
    methods=["POST"],
)
@login_required
def send_inquiry(car_id):

    car = Car.query.get_or_404(car_id)

    # -----------------------------------------------------
    # ONLY BUYERS
    # -----------------------------------------------------

    if current_user.role.lower() != "buyer":

        flash(
            "Only buyers can contact sellers about vehicles.",
            "danger",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    # -----------------------------------------------------
    # OWN CAR
    # -----------------------------------------------------

    if current_user.id == car.seller_id:

        flash(
            "You cannot inquire about your own car.",
            "warning",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    message_text = request.form.get(
        "message",
        "",
    ).strip()

    if not message_text:

        flash(
            "Message cannot be empty.",
            "danger",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    # -----------------------------------------------------
    # FIND EXISTING INQUIRY
    # -----------------------------------------------------

    inquiry = Inquiry.query.filter_by(
        car_id=car.id,
        buyer_id=current_user.id,
        seller_id=car.seller_id,
    ).first()

    # -----------------------------------------------------
    # CREATE INQUIRY
    # -----------------------------------------------------

    if not inquiry:

        inquiry = Inquiry(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.seller_id,
            status="Open",
        )

        db.session.add(inquiry)
        db.session.commit()

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    message = InquiryMessage(
        inquiry_id=inquiry.id,
        sender_id=current_user.id,
        receiver_id=car.seller_id,
        sender_role=current_user.role,
        message=message_text,
        is_read=False,
    )

    db.session.add(message)

    inquiry.status = "Open"

    # -----------------------------------------------------
    # SELLER NOTIFICATION
    # -----------------------------------------------------

    notification = Notification(
        user_id=car.seller_id,
        car_id=car.id,
        title="New Vehicle Inquiry",
        message=(
            f"{current_user.name} sent you a "
            f"new inquiry about "
            f"{car.brand} {car.model}."
        ),
        notification_type="inquiry",
    )

    db.session.add(notification)

    db.session.commit()

    flash(
        "Message sent to the seller.",
        "success",
    )

    return redirect(
        url_for(
            "chat.inquiry_chat",
            inquiry_id=inquiry.id,
        )
    )


# =========================================================
# BUYER INQUIRIES
# =========================================================

@cars.route("/buyer_inquiries")
@login_required
def buyer_inquiries():

    inquiries = (
        Inquiry.query
        .filter_by(
            buyer_id=current_user.id
        )
        .order_by(
            Inquiry.created_at.desc()
        )
        .all()
    )

    return render_template(
        "buyer_inquiries.html",
        inquiries=inquiries,
    )


# =========================================================
# SELLER INQUIRIES
# =========================================================

@cars.route("/seller_inquiries")
@login_required
def seller_inquiries():

    inquiries = (
        Inquiry.query
        .filter_by(
            seller_id=current_user.id
        )
        .order_by(
            Inquiry.created_at.desc()
        )
        .all()
    )

    return render_template(
        "seller_inquiries.html",
        inquiries=inquiries,
    )


# =========================================================
# CONTACT SELLER / ADMIN
# =========================================================

@cars.route(
    "/contact_seller/<int:car_id>",
    methods=["POST"],
)
@login_required
def contact_seller(car_id):

    car = Car.query.get_or_404(car_id)

    message_text = request.form.get(
        "message",
        "",
    ).strip()

    if not message_text:

        flash(
            "Message cannot be empty.",
            "danger",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    # -----------------------------------------------------
    # FIND ADMIN FIRST
    # -----------------------------------------------------

    admin = User.query.filter_by(
        role="admin"
    ).first()

    if not admin:

        flash(
            "No administrator is currently available.",
            "danger",
        )

        return redirect(
            url_for(
                "cars.car_details",
                car_id=car.id,
            )
        )

    # -----------------------------------------------------
    # CREATE INQUIRY
    # -----------------------------------------------------

    inquiry = Inquiry(
        car_id=car.id,
        buyer_id=current_user.id,
        seller_id=car.seller_id,
        status="Open",
    )

    db.session.add(inquiry)
    db.session.commit()

    # -----------------------------------------------------
    # MESSAGE TO ADMIN
    # -----------------------------------------------------

    message = InquiryMessage(
        inquiry_id=inquiry.id,
        sender_id=current_user.id,
        receiver_id=admin.id,
        sender_role=current_user.role,
        message=message_text,
        is_read=False,
    )

    db.session.add(message)

    # -----------------------------------------------------
    # ADMIN NOTIFICATION
    # -----------------------------------------------------

    notification = Notification(
        user_id=admin.id,
        car_id=car.id,
        title="New Contact Request",
        message=(
            f"{current_user.name} contacted "
            f"you regarding "
            f"{car.brand} {car.model}."
        ),
        notification_type="inquiry",
    )

    db.session.add(notification)

    db.session.commit()

    flash(
        "Your request has been sent successfully.",
        "success",
    )

    return redirect(
        url_for(
            "cars.car_details",
            car_id=car.id,
        )
    )
