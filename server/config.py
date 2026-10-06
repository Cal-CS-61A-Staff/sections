import os
import re

import flask
from dotenv import load_dotenv

DEV_SQLITE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db")


def _database_url(is_dev: bool) -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        if not is_dev:
            raise RuntimeError("DATABASE_URL must be set outside development")
        return "sqlite:///" + DEV_SQLITE_PATH
    # Cloud SQL / Heroku style URLs don't name a driver.
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", url)


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Environment variable {key} must be set")
    return value


def load_config(app: flask.Flask):
    """Load app config from the environment (and a local .env file, if present).

    FLASK_ENV is one of development, staging, production, matching seating.
    """
    load_dotenv()
    env = os.getenv("FLASK_ENV", "development").lower()
    is_dev = env == "development"

    canvas_server_url = _require("CANVAS_SERVER_URL")
    admin_override = os.getenv("ADMIN_OVERRIDE_CANVAS_COURSE_ID")

    app.config.update(
        APP_ENV=env,
        SECRET_KEY=os.getenv("SECRET_KEY") or ("development" if is_dev else _require("SECRET_KEY")),
        SQLALCHEMY_DATABASE_URI=_database_url(is_dev),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        CANVAS_SERVER_URL=canvas_server_url.rstrip("/") + "/",
        CANVAS_CLIENT_ID=_require("CANVAS_CLIENT_ID"),
        CANVAS_CLIENT_SECRET=_require("CANVAS_CLIENT_SECRET"),
        # Temporary: one deployment serves one course until multi-course routing lands.
        CANVAS_COURSE_ID=int(_require("CANVAS_COURSE_ID")),
        # Value of the `course` column for this course. Defaults to CANVAS_COURSE_ID;
        # set it to read rows moved from the monorepo, which use keys like "cs61a".
        COURSE_KEY=os.getenv("COURSE_KEY") or None,
        COURSE_NAME=os.getenv("COURSE_NAME"),
        # Members of this bCourses course are staff and admin in every course.
        ADMIN_OVERRIDE_CANVAS_COURSE_ID=int(admin_override) if admin_override else None,
        SLACK_WEBHOOK_URL=os.getenv("SLACK_WEBHOOK_URL"),
        # Shared secret for the /api/sudo/* and export_attendance_secret endpoints.
        API_SECRET=os.getenv("API_SECRET"),
        PERMANENT_SESSION_LIFETIME=7200,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=not is_dev,
        SESSION_COOKIE_SAMESITE="Lax",
    )
