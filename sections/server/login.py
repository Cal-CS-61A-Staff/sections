import flask
import time
from flask import redirect, session
from flask_login import LoginManager, login_user, logout_user
import canvasapi

from common.course_config import get_bcourses_id, get_course
from common.oauth_client import create_oauth_client
from common.url_for import url_for
from models import User, db

import common.canvas_service as canvas_service


def create_login_client(app: flask.Flask):
    login_manager = LoginManager()
    login_manager.init_app(app)

    def login(resp: dict):
        user_info = resp['user']
        user_id = user_info['id']
        # Use the callback token directly for Canvas profile and role checks.
        access_token = resp["access_token"]
        user_email = canvas_service.get_email(user_id, access_token)
        user_name = canvas_service.get_name(user_id, access_token)
        user_preferred_name = canvas_service.get_preferred_name(
            user_id, access_token
        )
        user_courses = canvas_service.get_user_courses(user_id, access_token)
        app_course_id: int = get_bcourses_id()
        course = get_course()

        user = User.query.filter_by(
            email=user_email, course=course
        ).one_or_none()
        if user is None:
            user = User(
                email=user_email,
                name=user_preferred_name,
                is_staff=False,
                is_admin=False,
                course=course,
            )
            db.session.add(user)

        user.name = user_preferred_name or user_name or user_email
        try:
            app_course = canvas_service.get_course(app_course_id, access_token)
            user.is_staff = canvas_service.is_staff(
                app_course, user_id, access_token
            )
            user.is_admin = canvas_service.is_admin(
                app_course, user_id, access_token
            )
        except canvasapi.exceptions.Forbidden:
            if 1549197 in [c.id for c in user_courses]:
                user.is_staff = True
                user.is_admin = True
            else:
                raise
        db.session.commit()
        login_user(user, remember=True)
        session.permanent = True
        # Keep only a short-lived staff access token; reauthorize when it expires.
        session.pop("canvas_access_token", None)
        session.pop("canvas_token_expires_at", None)
        if user.is_staff:
            session["canvas_access_token"] = access_token
            session["canvas_token_expires_at"] = time.time() + resp.get("expires_in", 3600)

    create_oauth_client(
        app,
        "sections",
        success_callback=login,
        store_canvas_tokens_in_session=False,
    )

    @login_manager.user_loader
    def load_user(user_id):
        course = get_course()
        return User.query.filter_by(id=user_id, course=course).one_or_none()

    @app.route("/oauth/logout")
    def logout():
        session.pop("canvas_access_token", None)
        session.pop("canvas_token_expires_at", None)
        logout_user()
        return redirect(url_for("index"))
