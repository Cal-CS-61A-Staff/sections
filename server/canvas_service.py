from canvasapi import Canvas
from flask import current_app

from course import get_canvas_course_id

# Requested at login. Must be a subset of the scopes on the sections Canvas developer key.
SCOPES = [
    "url:GET|/api/v1/users/:id",
    "url:GET|/api/v1/courses/:id",
    "url:GET|/api/v1/users/:user_id/courses",
    "url:GET|/api/v1/users/:user_id/profile",
    "url:GET|/api/v1/courses/:course_id/enrollments",
    "url:GET|/api/v1/accounts/:account_id/users",
]

STAFF_ENROLLMENT_TYPES = ("TaEnrollment", "TeacherEnrollment")


def _client(access_token: str) -> Canvas:
    return Canvas(current_app.config["CANVAS_SERVER_URL"], access_token)


def get_profile(user_id, access_token: str) -> dict:
    """Canvas profile with ``primary_email``, ``name`` and ``short_name``."""
    return _client(access_token).get_user(user_id).get_profile()


def in_admin_override_course(user_id, access_token: str) -> bool:
    override_id = current_app.config.get("ADMIN_OVERRIDE_CANVAS_COURSE_ID")
    if override_id is None:
        return False
    courses = _client(access_token).get_user(user_id).get_courses(
        enrollment_state="active", per_page=100
    )
    return any(c.id == override_id for c in courses)


def get_course_roles(user_id, access_token: str) -> tuple[bool, bool]:
    """Return ``(is_staff, is_admin)`` for the user in this app's course.

    Staff are TAs and Teachers; admins are Teachers and Lead TAs. Raises
    ``canvasapi.exceptions.Forbidden`` if the user can't see the course.
    """
    if in_admin_override_course(user_id, access_token):
        return True, True
    course = _client(access_token).get_course(get_canvas_course_id())
    is_staff = is_admin = False
    for e in course.get_enrollments(user_id=str(user_id)):
        if e.type in STAFF_ENROLLMENT_TYPES:
            is_staff = True
        if e.type == "TeacherEnrollment" or e.role == "Lead TA":
            is_admin = True
    return is_staff, is_admin


def get_student_from_email(email: str, access_token: str):
    """Name of the student in this app's course with login ``email``, or None."""
    course = _client(access_token).get_course(get_canvas_course_id())
    for enrollment in course.get_enrollments(type=["StudentEnrollment"]):
        if enrollment.user["login_id"] == email:
            return enrollment.user["name"]
    return None
