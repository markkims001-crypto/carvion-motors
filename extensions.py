from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from datetime import datetime, timezone

def utcnow():
    """Return the current UTC time as a naive datetime for legacy DB columns.

    Existing timestamp columns are timezone-naive and store UTC values. Keeping
    that representation avoids mixing aware and naive datetimes while avoiding
    the deprecated datetime.utcnow() API.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


db = SQLAlchemy()

login_manager = LoginManager()

login_manager.login_view = "auth.login"

login_manager.login_message = "Please log in first."