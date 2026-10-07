import time

import flask
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from canvasapi.exceptions import Forbidden
from flask import abort, redirect, request, session, url_for
from flask_login import LoginManager, login_user, logout_user
from markupsafe import escape

import canvas_service
from course import get_course
from models import User, db

AFTER_LOGIN_KEY = "after_login"


def _safe_next(target):
    # Only redirect back to paths on this site.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def complete_login(token: dict):
    """Create or update the local user from a Canvas OAuth token response."""
    user_id = token["user"]["id"]
    access_token = token["access_token"]
    profile = canvas_service.get_profile(user_id, access_token)
    email = profile.get("primary_email") or profile.get("login_id")
    name = profile.get("short_name") or profile.get("name") or email
    is_staff, is_admin = canvas_service.get_course_roles(user_id, access_token)

    course = get_course()
    user = User.query.filter_by(email=email, course=course).one_or_none()
    if user is None:
        user = User(email=email, name=name, is_staff=False, is_admin=False, course=course)
        db.session.add(user)
    user.name = name
    user.is_staff = is_staff
    user.is_admin = is_admin
    db.session.commit()

    login_user(user, remember=True)
    session.permanent = True
    # Keep only a short-lived staff access token; reauthorize when it expires.
    session.pop("canvas_access_token", None)
    session.pop("canvas_token_expires_at", None)
    if user.is_staff:
        session["canvas_access_token"] = access_token
        session["canvas_token_expires_at"] = time.time() + token.get("expires_in", 3600)


def create_login_client(app: flask.Flask):
    login_manager = LoginManager()
    login_manager.init_app(app)

    oauth = OAuth(app)
    canvas_server_url = app.config["CANVAS_SERVER_URL"]
    canvas = oauth.register(
        "canvas",
        client_id=app.config["CANVAS_CLIENT_ID"],
        client_secret=app.config["CANVAS_CLIENT_SECRET"],
        access_token_url=canvas_server_url + "login/oauth2/token",
        authorize_url=canvas_server_url + "login/oauth2/auth",
        client_kwargs={
            "scope": " ".join(canvas_service.SCOPES),
            # Canvas expects the client credentials in the POST body.
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.filter_by(id=int(user_id), course=get_course()).one_or_none()

    @app.route("/oauth/canvas_login")
    def canvas_login():
        session[AFTER_LOGIN_KEY] = _safe_next(request.args.get("next"))
        return canvas.authorize_redirect(url_for("canvas_authorized", _external=True))

    @app.route("/oauth/canvas_authorized")
    def canvas_authorized():
        try:
            token = canvas.authorize_access_token()
        except OAuthError as e:
            return f"Access denied: {escape(e.description or e.error)}", 403
        try:
            complete_login(token)
        except Forbidden:
            abort(403, "You are not enrolled in this course on bCourses.")
        return redirect(session.pop(AFTER_LOGIN_KEY, None) or url_for("index"))

    @app.route("/oauth/logout")
    def logout():
        session.pop("canvas_access_token", None)
        session.pop("canvas_token_expires_at", None)
        logout_user()
        return redirect(url_for("index"))
