"""Which course the current request belongs to.

For now each deployment serves the single course named by CANVAS_COURSE_ID.
Multi-course support will read the course from the URL instead, without
changing these function signatures, so callers stay the same.
"""

from flask import current_app


def get_canvas_course_id() -> int:
    return current_app.config["CANVAS_COURSE_ID"]


def get_course() -> str:
    """The key stored in each row's ``course`` column."""
    return current_app.config.get("COURSE_KEY") or str(get_canvas_course_id())


def format_coursecode(course: str) -> str:
    return current_app.config.get("COURSE_NAME") or course
