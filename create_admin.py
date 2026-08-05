from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash


app = create_app()


with app.app_context():

    admin = User.query.filter_by(
        email="admin@carvion.com"
    ).first()


    if admin:

        print("Admin already exists")

    else:

        admin = User(
            name="Carvion Admin",
            email="admin@carvion.com",
            phone="0700000000",
            password=generate_password_hash(
                "admin123"
            ),
            role="admin"
        )


        db.session.add(admin)

        db.session.commit()


        print("Admin created")
        print("Email: admin@carvion.com")
        print("Password: admin123")