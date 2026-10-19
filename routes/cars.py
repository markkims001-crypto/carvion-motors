
# routes/cars.py

import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import cloudinary
import cloudinary.uploader
import cloudinary.api

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app
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
    Report
 )


# ============================================================
# BLUEPRINT
# ============================================================

cars = Blueprint("cars", __name__)


# ============================================================
# CLOUDINARY CONFIGURATION
# ============================================================

def configure_cloudinary():

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")

    if not cloud_name:
        raise RuntimeError(
            "CLOUDINARY_CLOUD_NAME is missing on the server."
        )

    if not api_key:
        raise RuntimeError(
            "CLOUDINARY_API_KEY is missing on the server."
        )

    if not api_secret:
        raise RuntimeError(
            "CLOUDINARY_API_SECRET is missing on the server."
        )

    if not upload_preset:
        raise RuntimeError(
            "CLOUDINARY_UPLOAD_PRESET is missing on the server."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )

    return {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
        "upload_preset": upload_preset
    }


# ============================================================
# CLOUDINARY TEST
# ============================================================

def test_cloudinary():

    configure_cloudinary()

    result = cloudinary.api.ping()

    if not result or result.get("status") != "ok":

        raise RuntimeError(
            f"Cloudinary ping failed: {result}"
        )

    return True


# ============================================================
# IMAGE VALIDATION
# ============================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    allowed_extensions = current_app.config.get(
        "ALLOWED_EXTENSIONS",
        {"jpg", "jpeg", "png", "webp"}
    )

    return extension in allowed_extensions


# ============================================================
# AVAILABLE CARS
# ============================================================

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

    query = Car.query.filter_by(
        status="Approved"
    )

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

    if fuel:
        query = query.filter(
            Car.fuel == fuel
        )

    if transmission:
        query = query.filter(
            Car.transmission == transmission
        )

    if min_price is not None:
        query = query.filter(
            Car.price >= min_price
        )

    if max_price is not None:
        query = query.filter(
            Car.price <= max_price
        )

    if min_year is not None:
        query = query.filter(
            Car.year >= min_year
        )

    if max_year is not None:
        query = query.filter(
            Car.year <= max_year
        )

    if min_mileage is not None:
        query = query.filter(
            Car.mileage >= min_mileage
        )

    if max_mileage is not None:
        query = query.filter(
            Car.mileage <= max_mileage
        )

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

    favorite_ids = set()
    compare_ids = set()

    if current_user.is_authenticated:

        favorite_ids = {
            item.car_id
            for item in Favorite.query.filter_by(
                user_id=current_user.id
            ).all()
        }

        compare_ids = {
            item.car_id
            for item in CompareCar.query.filter_by(
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


# ============================================================
# CAR DETAILS
# ============================================================

@cars.route("/car/<int:car_id>")
def car_details(car_id):

    car = db.get_or_404(Car, car_id)

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


# ============================================================
# ADD CAR
# ============================================================

@cars.route(
    "/add_car",
    methods=["GET", "POST"]
)
@login_required
def add_car():

    if request.method == "GET":

        return render_template(
            "add_car.html"
        )

    print("================================================")
    print("ADD CAR ROUTE WAS CALLED")
    print("METHOD:", request.method)
    print("USER:", current_user.id)
    print("================================================")

    # ========================================================
    # FORM DATA
    # ========================================================

    try:

        registration_number = request.form.get(
            "registration_number",
            ""
        ).strip().upper()

        brand = request.form.get(
            "brand",
            ""
        ).strip()

        model = request.form.get(
            "model",
            ""
        ).strip()

        year = int(
            request.form.get(
                "year",
                0
            )
        )

        price = int(
            request.form.get(
                "price",
                0
            )
        )

        mileage = int(
            request.form.get(
                "mileage",
                0
            )
        )

        fuel = request.form.get(
            "fuel",
            ""
        ).strip()

        transmission = request.form.get(
            "transmission",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

    except (
        ValueError,
        TypeError
    ):

        flash(
            "Please enter valid vehicle information.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    # ========================================================
    # REQUIRED FIELDS
    # ========================================================

    if not registration_number:

        flash(
            "Registration number is required.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    if not brand or not model:

        flash(
            "Brand and model are required.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    if year <= 0:

        flash(
            "Please enter a valid year.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    if price <= 0:

        flash(
            "Please enter a valid price.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    # ========================================================
    # VALIDATE VEHICLE DATA AGAINST THE DATABASE SCHEMA
    # ========================================================

    current_year = datetime.now().year
    engine = (request.form.get("engine") or "").strip()
    color = (request.form.get("color") or "").strip()
    condition = (request.form.get("condition") or "").strip()
    description = (request.form.get("description") or "").strip()

    validation_error = None

    if len(registration_number) > 20:
        validation_error = "Registration number must be 20 characters or fewer."
    elif not 1900 <= year <= current_year + 1:
        validation_error = f"Enter a vehicle year between 1900 and {current_year + 1}."
    elif mileage < 0:
        validation_error = "Mileage cannot be negative."
    elif len(brand) > 50 or len(model) > 50:
        validation_error = "Brand and model must be 50 characters or fewer."
    elif not fuel or len(fuel) > 30:
        validation_error = "Please select a valid fuel type."
    elif fuel not in {"Petrol", "Diesel", "Hybrid", "Plug-in Hybrid", "Electric", "Other"}:
        validation_error = "Please select a valid fuel type."
    elif not transmission or len(transmission) > 30:
        validation_error = "Please select a valid transmission."
    elif transmission not in {"Automatic", "Manual", "CVT", "Other"}:
        validation_error = "Please select a valid transmission."
    elif not location:
        validation_error = "Location is required."
    elif len(location) > 100:
        validation_error = "Location must be 100 characters or fewer."
    elif len(engine) > 50:
        validation_error = "Engine details must be 50 characters or fewer."
    elif len(color) > 30:
        validation_error = "Color must be 30 characters or fewer."
    elif len(condition) > 30 or (condition and condition not in {"Brand New", "Foreign Used", "Local Used"}):
        validation_error = "Please select a valid vehicle condition."
    elif len(description) > 5000:
        validation_error = "Description must be 5,000 characters or fewer."

    if validation_error:
        flash(validation_error, "danger")
        return redirect(url_for("cars.add_car"))

    # ========================================================
    # GET IMAGES
    # ========================================================

    images = request.files.getlist("images")

    valid_images = []

    for image in images:

        if (
            image
            and image.filename
            and image.filename.strip()
        ):

            valid_images.append(image)

    print("================================================")
    print("CAR IMAGE UPLOAD START")
    print("Number of received files:", len(valid_images))

    for image in valid_images:

        print(
            "Received image:",
            image.filename
        )

    print("================================================")

    # ========================================================
    # MINIMUM 5 IMAGES
    # ========================================================

    if len(valid_images) < 5:

        flash(
            f"Please upload at least 5 images. "
            f"You selected {len(valid_images)}.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    # ========================================================
    # VALIDATE IMAGE TYPES
    # ========================================================

    for image in valid_images:

        if not allowed_file(image.filename):

            flash(
                f"Invalid image file: {image.filename}. "
                "Allowed formats are JPG, JPEG, PNG and WEBP.",
                "danger"
            )

            return redirect(
                url_for("cars.add_car")
            )

    # ========================================================
    # CHECK REGISTRATION
    # ========================================================

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

    # ========================================================
    # CLOUDINARY CONFIGURATION
    # ========================================================

    cloudinary_settings = None

    try:

        print("Testing Cloudinary connection...")

        cloudinary_settings = configure_cloudinary()

        print("Cloudinary configuration loaded.")
        print(
            "Cloud name:",
            cloudinary_settings["cloud_name"]
        )
        print(
            "Upload preset:",
            cloudinary_settings["upload_preset"]
        )

        ping_result = cloudinary.api.ping()

        print(
            "Cloudinary ping:",
            ping_result
        )

        if (
            not ping_result
            or ping_result.get("status") != "ok"
        ):

            raise RuntimeError(
                f"Cloudinary ping failed: {ping_result}"
            )

        print("Cloudinary connection OK.")

    except Exception as error:

        print("================================================")
        print("CLOUDINARY CONNECTION ERROR")
        print("ERROR TYPE:", type(error).__name__)
        print("ERROR:", str(error))
        print("ERROR REPR:", repr(error))
        print("================================================")

        current_app.logger.exception("Cloudinary connection failed during vehicle creation")
        flash(
            "Image hosting is temporarily unavailable. Please try again later.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    # ========================================================
    # CREATE CAR
    # ========================================================

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

        engine=engine or None,

        color=color or None,

        condition=condition or None,

        location=location,

        description=description or None,

        status="Approved"
    )

    uploaded_public_ids = []

    try:

        # ====================================================
        # SAVE CAR FIRST
        # ====================================================

        db.session.add(car)

        db.session.flush()

        print(
            "Created temporary car ID:",
            car.id
        )

        # ====================================================
        # UPLOAD EVERY IMAGE
        # ====================================================

        upload_preset = cloudinary_settings["upload_preset"]

        print(
            "Using Cloudinary upload preset:",
            upload_preset
        )

        for index, image in enumerate(
            valid_images,
            start=1
        ):

            print("------------------------------------------------")
            print(
                f"Uploading image "
                f"{index}/{len(valid_images)}"
            )
            print(
                "Filename:",
                image.filename
            )

            image.stream.seek(0)

            public_id = (
                f"car_{car.id}_"
                f"{uuid.uuid4().hex}"
            )

            print(
                "Cloudinary public ID:",
                public_id
            )

            try:

                result = cloudinary.uploader.upload(

                    image.stream,

                    upload_preset=upload_preset,

                    folder="carvion_motors/cars",

                    public_id=public_id,

                    resource_type="image",

                    overwrite=False,

                    use_filename=False,

                    unique_filename=False,

                    secure=True
                )

            except Exception as upload_error:

                print("------------------------------------------------")
                print("INDIVIDUAL CLOUDINARY UPLOAD FAILED")
                print(
                    "IMAGE:",
                    image.filename
                )
                print(
                    "ERROR TYPE:",
                    type(upload_error).__name__
                )
                print(
                    "ERROR:",
                    str(upload_error)
                )
                print(
                    "ERROR REPR:",
                    repr(upload_error)
                )
                print("------------------------------------------------")

                raise

            print(
                "Cloudinary upload successful."
            )

            image_url = result.get(
                "secure_url"
            )

            cloudinary_public_id = result.get(
                "public_id"
            )

            print(
                "Secure URL:",
                image_url
            )

            print(
                "Public ID:",
                cloudinary_public_id
            )

            # Record the remote asset immediately so it can be cleaned up
            # if the response is incomplete or the database save later fails.
            if cloudinary_public_id:
                uploaded_public_ids.append(cloudinary_public_id)

            if not image_url:

                raise RuntimeError(
                    "Cloudinary upload succeeded "
                    "but secure_url was missing."
                )

            if not cloudinary_public_id:

                raise RuntimeError(
                    "Cloudinary upload succeeded "
                    "but public_id was missing."
                )

            car_image = CarImage(

                car_id=car.id,

                filename=image_url,

                public_id=cloudinary_public_id

            )

            db.session.add(car_image)

        # ====================================================
        # VERIFY IMAGE COUNT
        # ====================================================

        if len(uploaded_public_ids) < 5:

            raise RuntimeError(
                "Fewer than 5 images were uploaded."
            )

        # ====================================================
        # COMMIT
        # ====================================================

               # ====================================================
        # PROMOTE BUYER TO SELLER AND COMMIT
        # ====================================================

        if current_user.role == "buyer":
            current_user.role = "seller"

        # Notify every administrator that a new listing has been published.
        administrators = User.query.filter(
            db.func.lower(User.role) == "admin"
        ).all()
        for administrator in administrators:
            db.session.add(Notification(
                user_id=administrator.id,
                car_id=car.id,
                title="New Vehicle Listing",
                message=(
                    f"{car.brand} {car.model} ({car.registration_number}) "
                    f"was published by {current_user.name}."
                ),
                notification_type="vehicle",
                is_read=False,
            ))

        db.session.commit()

        print("================================================")
        print("CAR CREATED SUCCESSFULLY")
        print("Car ID:", car.id)
        print("Images:", len(uploaded_public_ids))
        print("================================================")

    except Exception as error:

        print("================================================")
        print("CAR IMAGE UPLOAD ERROR")
        print("ERROR TYPE:", type(error).__name__)
        print("ERROR:", str(error))
        print("ERROR REPR:", repr(error))
        print("================================================")

        db.session.rollback()

        # ====================================================
        # CLOUDINARY CLEANUP
        # ====================================================

        for public_id in uploaded_public_ids:

            try:

                print(
                    "Deleting uploaded Cloudinary image:",
                    public_id
                )

                cloudinary.uploader.destroy(
                    public_id,
                    resource_type="image"
                )

            except Exception as cleanup_error:

                print(
                    "Cloudinary cleanup error:",
                    repr(cleanup_error)
                )

        current_app.logger.exception("Vehicle creation or image upload failed")
        flash(
            "We couldn't publish your listing because an upload or save failed. "
            "Please try again.",
            "danger"
        )

        return redirect(
            url_for("cars.add_car")
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    flash(
        "Your car listing is now live. "
        "Your account is now a seller.",
        "success"
    )

    return redirect(
        url_for("cars.my_cars")
    )


# ============================================================
# SELLER DASHBOARD
# ============================================================

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


# ============================================================
# MY CARS
# ============================================================

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


# ============================================================
# EDIT CAR
# ============================================================

@cars.route(
    "/edit_car/<int:car_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_car(car_id):

    car = db.get_or_404(Car, car_id)

    if car.seller_id != current_user.id:

        flash(
            "You are not allowed to edit this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    if request.method == "POST":

        # Validate all values before mutating the model.
        try:
            brand = request.form.get("brand", car.brand).strip()
            model = request.form.get("model", car.model).strip()
            year = int(request.form.get("year", str(car.year)))
            price = int(request.form.get("price", str(car.price)))
            mileage = int(request.form.get("mileage", str(car.mileage)))
            fuel = request.form.get("fuel", car.fuel).strip()
            transmission = request.form.get("transmission", car.transmission).strip()
            location = request.form.get("location", car.location).strip()
            engine = (request.form.get("engine") or "").strip() or None
            color = (request.form.get("color") or "").strip() or None
            condition = (request.form.get("condition") or "").strip() or None
            description = (request.form.get("description") or "").strip() or None
        except (TypeError, ValueError):
            flash(
                "Enter a valid whole number for year, price, and mileage.",
                "danger"
            )
            return render_template("edit_car.html", car=car), 400

        errors = []
        if not brand or len(brand) > 50:
            errors.append("Brand is required and must be 50 characters or fewer.")
        if not model or len(model) > 50:
            errors.append("Model is required and must be 50 characters or fewer.")
        latest_year = datetime.now().year + 1
        if year < 1900 or year > latest_year:
            errors.append(f"Year must be between 1900 and {latest_year}.")
        if price <= 0:
            errors.append("Price must be greater than zero.")
        if mileage < 0:
            errors.append("Mileage cannot be negative.")
        if not fuel or len(fuel) > 30:
            errors.append("Fuel type is required and must be 30 characters or fewer.")
        if not transmission or len(transmission) > 30:
            errors.append("Transmission is required and must be 30 characters or fewer.")
        if not location or len(location) > 100:
            errors.append("Location is required and must be 100 characters or fewer.")
        if engine and len(engine) > 50:
            errors.append("Engine must be 50 characters or fewer.")
        if color and len(color) > 30:
            errors.append("Color must be 30 characters or fewer.")
        if condition and len(condition) > 30:
            errors.append("Condition must be 30 characters or fewer.")
        if description and len(description) > 5000:
            errors.append("Description must be 5,000 characters or fewer.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("edit_car.html", car=car), 400

        try:
            car.brand = brand
            car.model = model
            car.year = year
            car.price = price
            car.mileage = mileage
            car.fuel = fuel
            car.transmission = transmission
            car.engine = engine
            car.color = color
            car.condition = condition
            car.location = location
            car.description = description
            db.session.commit()

            flash("Car updated successfully.", "success")
            return redirect(url_for("cars.seller_dashboard"))

        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Unexpected error while updating vehicle %s", car_id
            )
            flash(
                "Unable to update vehicle right now. Please try again.",
                "danger"
            )

        return render_template(
        "edit_car.html",
        car=car
    )


# ============================================================
# DELETE CAR
# ============================================================

@cars.route(
    "/delete_car/<int:car_id>",
    methods=["POST"]
)
@login_required
def delete_car(car_id):

    car = db.get_or_404(Car, car_id)

    if car.seller_id != current_user.id:

        flash(
            "You cannot delete this car.",
            "danger"
        )

        return redirect(
            url_for("cars.seller_dashboard")
        )

    # Capture image identifiers, but only remove remote images after the
    # database transaction succeeds.
    public_ids = [
        image.public_id
        for image in list(car.images)
        if getattr(image, "public_id", None)
    ]

    try:
        # Reports have a car foreign key without ON DELETE CASCADE.
        Report.query.filter_by(car_id=car.id).delete(
            synchronize_session=False
        )
        Favorite.query.filter_by(car_id=car.id).delete(
            synchronize_session=False
        )
        CompareCar.query.filter_by(car_id=car.id).delete(
            synchronize_session=False
        )
        Notification.query.filter_by(car_id=car.id).delete(
            synchronize_session=False
        )
        db.session.delete(car)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to delete vehicle %s from the database", car_id
        )
        flash(
            "Unable to remove this vehicle right now. Please try again.",
            "danger"
        )
        return redirect(url_for("cars.seller_dashboard"))

    try:
        configure_cloudinary()
        for public_id in public_ids:
            try:
                cloudinary.uploader.destroy(
                    public_id,
                    resource_type="image"
                )
            except Exception:
                current_app.logger.exception(
                    "Unable to delete Cloudinary image %s for vehicle %s",
                    public_id, car_id
                )
    except Exception:
        current_app.logger.exception(
            "Cloudinary is unavailable while cleaning up images for vehicle %s",
            car_id
        )

    flash("Car removed successfully.", "success")
    return redirect(url_for("cars.seller_dashboard"))


@cars.route(
    "/delete_image/<int:image_id>",
    methods=["POST"]
)
@login_required
def delete_image(image_id):

    image = db.get_or_404(CarImage, image_id)

    car = db.get_or_404(Car, image.car_id)

    if car.seller_id != current_user.id:

        flash(
            "Permission denied.",
            "danger"
        )

        return redirect(
            url_for("cars.all_cars")
        )

    # Listings must retain at least five images.
    if len(car.images) <= 5:
        flash(
            "A vehicle listing must keep at least 5 images. Add another image before removing one.",
            "warning"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    public_id = getattr(image, "public_id", None)
    if public_id:
        try:
            configure_cloudinary()
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type="image"
            )
            if result and result.get("result") not in {"ok", "not found"}:
                current_app.logger.error(
                    "Unexpected Cloudinary delete result for image %s: %s",
                    image_id, result.get("result")
                )
                flash(
                    "The image could not be removed. Please try again.",
                    "danger"
                )
                return redirect(
                    url_for("cars.car_details", car_id=car.id)
                )
        except Exception:
            current_app.logger.exception(
                "Unable to delete Cloudinary image %s", image_id
            )
            flash(
                "The image could not be removed. Please try again.",
                "danger"
            )
            return redirect(
                url_for("cars.car_details", car_id=car.id)
            )

    try:
        db.session.delete(image)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to remove image record %s", image_id
        )
        flash(
            "Unable to remove the image right now. Please try again.",
            "danger"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    flash("Image deleted.", "success")
    return redirect(url_for("cars.car_details", car_id=car.id))


# ============================================================
# FAVORITES
# ============================================================

@cars.route(
    "/favorite/<int:car_id>",
    methods=["POST"]
)
@login_required
def toggle_favorite(car_id):

    car = db.get_or_404(Car, car_id)

    if (
        car.status != "Approved"
        and current_user.role != "admin"
    ):

        flash(
            "This vehicle is not available.",
            "warning"
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    favorite = Favorite.query.filter_by(
        user_id=current_user.id,
        car_id=car.id
    ).first()

    if favorite:

        db.session.delete(favorite)

        db.session.commit()

        flash(
            f"{car.brand} {car.model} "
            "removed from favorites.",
            "info"
        )

    else:

        favorite = Favorite(
            user_id=current_user.id,
            car_id=car.id
        )

        db.session.add(favorite)

        # Notify the listing owner about buyer interest, not the user
        # who clicked Favorite. Avoid sending a seller a notification about
        # their own listing.
        if car.seller_id != current_user.id:
            db.session.add(Notification(
                user_id=car.seller_id,
                car_id=car.id,
                title="Someone Saved Your Vehicle",
                message=(
                    f"A user saved your {car.brand} {car.model} "
                    "listing to their favorites."
                ),
                notification_type="favorite",
                is_read=False,
            ))

        db.session.commit()

        flash(
            f"{car.brand} {car.model} "
            "added to favorites.",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("cars.all_cars")
    )


# ============================================================
# FAVORITES PAGE
# ============================================================

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


# ============================================================
# REMOVE FAVORITE
# ============================================================

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

        db.session.delete(favorite)

        db.session.commit()

        flash(
            "Vehicle removed from favorites.",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("cars.favorites")
    )


# ============================================================
# COMPARE
# ============================================================

@cars.route(
    "/compare/<int:car_id>",
    methods=["POST"]
)
@login_required
def toggle_compare(car_id):

    car = db.get_or_404(Car, car_id)

    if (
        car.status != "Approved"
        and current_user.role != "admin"
    ):

        flash(
            "This vehicle is not available for comparison.",
            "warning"
        )

        return redirect(
            request.referrer
            or url_for("cars.all_cars")
        )

    existing = CompareCar.query.filter_by(
        user_id=current_user.id,
        car_id=car.id
    ).first()

    if existing:

        db.session.delete(existing)

        db.session.commit()

        flash(
            f"{car.brand} {car.model} "
            "removed from comparison.",
            "info"
        )

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
                or url_for("cars.all_cars")
            )

        comparison = CompareCar(
            user_id=current_user.id,
            car_id=car.id
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
            notification_type="compare"
        )

        db.session.add(notification)

        db.session.commit()

        flash(
            f"{car.brand} {car.model} "
            "added to comparison.",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("cars.all_cars")
    )


# ============================================================
# COMPARE PAGE
# ============================================================

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


# ============================================================
# REMOVE COMPARE
# ============================================================

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

        db.session.delete(comparison)

        db.session.commit()

        flash(
            "Vehicle removed from comparison.",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("cars.compare")
    )


# ============================================================
# CLEAR COMPARE
# ============================================================

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


# ============================================================
# NOTIFICATIONS
# ============================================================

@cars.route("/notifications")
@login_required
def notifications():

    # Opening the notifications page counts as viewing all notifications.
    # Restrict the update to the signed-in user's notifications.
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update(
        {"is_read": True},
        synchronize_session=False
    )
    db.session.commit()

    notification_list = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    return render_template(
        "notifications.html",
        notifications=notification_list
    )


# ============================================================
# MARK NOTIFICATION READ
# ============================================================

@cars.route(
    "/notification/<int:notification_id>/read",
    methods=["POST"]
)
@login_required
def mark_notification_read(notification_id):

    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()

    notification.is_read = True

    db.session.commit()

    role = (getattr(current_user, "role", "") or "").lower()

    if notification.notification_type == "inquiry":
        if role == "seller":
            return redirect(url_for("chat.seller_inquiries_chat"))
        if role == "buyer":
            return redirect(url_for("chat.my_inquiries"))

    if notification.notification_type == "message":
        if role == "admin":
            return redirect(url_for("chat.admin_chats"))
        if role in {"buyer", "seller"}:
            return redirect(url_for("chat.admin_chat"))

    if notification.car_id:
        if (
            role == "seller"
            and notification.notification_type in {"approval", "rejection", "vehicle"}
        ):
            return redirect(url_for("cars.my_cars"))

        if role == "admin" and notification.notification_type == "report":
            return redirect(url_for("admin.reports"))

        if role == "admin":
            return redirect(url_for("admin.car_details", car_id=notification.car_id))

        return redirect(
            url_for("cars.car_details", car_id=notification.car_id)
        )

    if notification.notification_type == "report" and (
        (getattr(current_user, "role", "") or "").lower() == "admin"
    ):
        return redirect(url_for("admin.reports"))

    if notification.notification_type == "user" and (
        (getattr(current_user, "role", "") or "").lower() == "admin"
    ):
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("cars.notifications"))


# ============================================================
# MARK ALL NOTIFICATIONS READ
# ============================================================

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
        url_for("cars.notifications")
    )



# ============================================================
# SHARED BUYER-TO-SELLER INQUIRY HANDLER
# ============================================================

def process_vehicle_inquiry(car_id):

    car = db.get_or_404(Car, car_id)

    # Only publicly available listings may receive buyer inquiries.
    # Do not let direct POST requests bypass the public listing filter.
    if car.status != "Approved":
        flash("This vehicle is not available for inquiries.", "warning")
        return redirect(url_for("cars.all_cars"))

    role = (getattr(current_user, "role", "") or "").strip().lower()
    if role not in ("buyer", "seller"):
        flash("Your account cannot contact sellers.", "danger")
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    if not car.seller_id:
        flash("This vehicle has no assigned seller.", "danger")
        return redirect(url_for("cars.car_details", car_id=car.id))

    if current_user.id == car.seller_id:
        flash("You cannot inquire about your own vehicle.", "warning")
        return redirect(url_for("cars.car_details", car_id=car.id))

    message_text = request.form.get("message", "").strip()

    if not message_text:
        flash("Please enter a message.", "warning")
        return redirect(url_for("cars.car_details", car_id=car.id))

    if len(message_text) > 5000:
        flash("Your message is too long. Please keep it under 5,000 characters.", "warning")
        return redirect(url_for("cars.car_details", car_id=car.id))

    try:
        # Reuse the existing inquiry for this buyer and vehicle.
        inquiry = Inquiry.query.filter_by(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.seller_id,
        ).first()

        # Create the inquiry if it does not already exist.
        if inquiry is None:
            inquiry = Inquiry(
                car_id=car.id,
                buyer_id=current_user.id,
                seller_id=car.seller_id,
                status="Open",
            )
            db.session.add(inquiry)
            db.session.flush()

        # Send the message to the SELLER, not the administrator.
        message = InquiryMessage(
            inquiry_id=inquiry.id,
            sender_id=current_user.id,
            receiver_id=car.seller_id,
            sender_role=role,
            message=message_text,
            is_read=False,
        )
        db.session.add(message)

        inquiry.status = "Open"

        notification = Notification(
            user_id=car.seller_id,
            car_id=car.id,
            title="New Vehicle Inquiry",
            message=(
                f"{current_user.name} sent you a message "
                f"about {car.brand} {car.model}."
            ),
            notification_type="inquiry",
            is_read=False,
        )
        db.session.add(notification)

        # Save the inquiry, message, and notification together.
        db.session.commit()

        flash("Your message has been sent to the seller.", "success")

        return redirect(
            url_for("chat.inquiry_chat", inquiry_id=inquiry.id)
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to process vehicle inquiry")

        flash(
            "We could not send your inquiry. Please try again.",
            "danger",
        )
        return redirect(url_for("cars.car_details", car_id=car.id))


# ============================================================
# BUYER SENDS INQUIRY
# ============================================================

@cars.route("/inquiry/<int:car_id>", methods=["POST"])
@login_required
def send_inquiry(car_id):
    return process_vehicle_inquiry(car_id)


# ============================================================
# CONTACT SELLER
# ============================================================

@cars.route("/contact_seller/<int:car_id>", methods=["POST"])
@login_required
def contact_seller(car_id):
    return process_vehicle_inquiry(car_id)


# ============================================================
# BUYER INQUIRIES — LEGACY URL COMPATIBILITY
# ============================================================

@cars.route("/buyer_inquiries")
@login_required
def buyer_inquiries():

    if current_user.role != "buyer":
        flash("Buyer access required.", "danger")
        return redirect(url_for("cars.all_cars"))

    return redirect(url_for("chat.my_inquiries"))


# ============================================================
# SELLER INQUIRIES — LEGACY URL COMPATIBILITY
# ============================================================

@cars.route("/seller_inquiries")
@login_required
def seller_inquiries():

    if current_user.role != "seller":
        flash("Seller access required.", "danger")
        return redirect(url_for("cars.all_cars"))

    return redirect(url_for("chat.seller_inquiries_chat"))

# ============================================================
# REPORT A CAR LISTING
# ============================================================

@cars.route(
    "/car/<int:car_id>/report",
    methods=["POST"]
)
@login_required
def report_listing(car_id):

    car = db.get_or_404(Car, car_id)

    # Only allow reports on publicly available listings.
    if car.status != "Approved":
        flash(
            "This listing is not available for reporting.",
            "warning"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    # Users cannot report their own vehicles.
    if car.seller_id == current_user.id:
        flash(
            "You cannot report your own listing.",
            "warning"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    allowed_reasons = {
        "Suspicious price or scam",
        "Misleading information",
        "Incorrect vehicle details",
        "Duplicate listing",
        "Suspected stolen vehicle",
        "Other",
    }

    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()

    if reason not in allowed_reasons:
        flash(
            "Please select a valid reason for your report.",
            "danger"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    if len(details) > 2000:
        flash(
            "Additional details must not exceed 2,000 characters.",
            "danger"
        )
        return redirect(
            url_for("cars.car_details", car_id=car.id)
        )

    try:
        # Prevent repeated pending reports from the same user
        # about the same vehicle.
        existing_report = Report.query.filter_by(
            car_id=car.id,
            reporter_id=current_user.id,
            status="Pending"
        ).first()

        if existing_report:
            flash(
                "You already have a pending report for this listing.",
                "info"
            )
            return redirect(
                url_for("cars.car_details", car_id=car.id)
            )

        report = Report(
            car_id=car.id,
            reporter_id=current_user.id,
            reason=reason,
            details=details or None,
            status="Pending"
        )

        db.session.add(report)

        # Notify administrators so reports do not depend on manual checking.
        administrators = User.query.filter(
            db.func.lower(User.role) == "admin"
        ).all()
        for administrator in administrators:
            db.session.add(Notification(
                user_id=administrator.id,
                car_id=car.id,
                title="New Listing Report",
                message=(
                    f"{current_user.name} reported {car.brand} {car.model}: "
                    f"{reason}."
                ),
                notification_type="report",
                is_read=False,
            ))

        db.session.commit()

        flash(
            "Your report has been submitted for admin review.",
            "success"
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to submit car listing report"
        )

        flash(
            "We could not submit your report. Please try again.",
            "danger"
        )

    return redirect(
        url_for("cars.car_details", car_id=car.id)
    )
