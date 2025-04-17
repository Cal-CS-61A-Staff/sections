from flask import session, request, url_for
from canvasapi import Canvas
from canvasapi.user import User
from canvasapi.course import Course

# from server.services.canvas.fake_canvas import FakeCanvas, FakeCourse, FakeUser
# from server.typings.exception import Redirect

def _get_client(key=None) -> Canvas:
    if not key:
        key = session.get('access_token', None) # TODO: check if this works
    if not key:
        # session['after_login'] = request.url
        # raise Redirect(url_for('auth.login'))
        raise Exception('this should not be here')
    return Canvas("https://ucberkeleysandbox.instructure.com/", key) # TODO: hard coded for now, use app.config

def get_user(user_id, key=None) -> User:
    return _get_client(key).get_user(user_id)

def get_course(course_id, key=None) -> Course:
    return _get_client(key).get_course(course_id)

def get_email(user_id, key=None) -> str | None:
    return get_user(user_id).get_profile().get('primary_email')

def get_name(user_id, key=None) -> str | None:
    return get_user(user_id).get_profile().get('name')

def get_user_courses(user_id, key=None) -> list[Course]:
    return [c for c in get_user(user_id).get_courses(enrollment_status='active', include=['term'], per_page=100)]

def is_staff(course, user_id):
    """ Returns whether a user is a TA or Teacher of the given course.

    Args:
        course (Course): CanvasAPI course object
        user_id (str | int): Canvas id for the user

    Returns:
        bool: True if user has staff role in course.
    """
    for e in course.get_enrollments(user_id=str(user_id)):
        staff_types = ["TaEnrollment", "TeacherEnrollment"]
        if e.type in staff_types:
            print("Is staff")
            return True
    return False
