import csv
import re

from io import StringIO
from datetime import datetime
from functools import wraps
from json import dumps
from typing import List, Optional, Union
from zoneinfo import ZoneInfo
from import_sheet import parse_time_string

import flask
from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required, login_user
from sqlalchemy.orm import joinedload

from common.course_config import format_coursecode, get_course, is_admin
from common.rpc.auth import post_slack_message, validate_secret
from common.rpc.secrets import only
from common.rpc.sections import rpc_export_attendance
from import_sheet import import_sections_from_url, import_enrollment_from_url
from models import (
    Attendance,
    AttendanceStatus,
    CourseConfig,
    Failure,
    Section,
    Session,
    User,
    db,
)

FIRST_WEEK_START = datetime(year=2022, month=6, day=27).timestamp()
ONE_WEEK = 60 * 60 * 24 * 7  # number of seconds in a week
IS_SUMMER = True
MAX_ABSENCES = 2
UNASSIGNED = "UNASSIGNED"


def staff_required(func):
    @wraps(func)
    @login_required
    def wrapped(**kwargs):
        if not current_user.is_staff:
            raise Failure("Only staff can perform this action")
        return func(**kwargs)

    return wrapped


def admin_required(func):
    @wraps(func)
    @staff_required
    def wrapped(**kwargs):
        if not current_user.is_admin:
            raise Failure("Only course admins can perform this action.")
        return func(**kwargs)

    return wrapped


def section_sorter(section: Section) -> int:
    score = 0
    big = 10000
    if current_user.is_staff and section.staff is None:
        score -= big * 100
    if (
        section.staff is not None
        and section.staff.id == current_user.id
        or current_user.id in [student.id for student in section.students]
    ):
        score -= big * 10
    spare_capacity = max(0, section.capacity - len(section.students))
    if spare_capacity:
        score -= big * spare_capacity
    score += section.id
    return score


def parse_emails(emails):
    return re.split(r"[\s,]+", emails.strip())


def get_config() -> CourseConfig:
    return CourseConfig.query.filter_by(course=get_course()).one()

def add_student_helper(student: User, target_section: Section):
    if len(set([s.name for s in student.sections])) != len(student.sections):
        raise Failure("Student has multiple sections of the same type")

    # If user is already in a section of the same type, remove it and add target section
    for s in student.sections:
        if s.name == target_section.name:
            student.sections.remove(s)
            break
    student.sections.append(target_section)

def create_state_client(app: flask.Flask):
    def api(handler):
        def wrapped():
            try:
                return jsonify({"success": True, "data": handler(**request.json)})
            except Failure as failure:
                return jsonify({"success": False, "message": str(failure)})

        app.add_url_rule(
            f"/api/{handler.__name__}", handler.__name__, wrapped, methods=["POST"]
        )

        def sudo_wrapped():
            data = request.json
            secret = data["secret"]
            email = data["email"]
            args = data["args"]

            course = data.get("course", None)
            course = validate_secret(secret=secret, course=course)
            if course != get_course():
                abort(401)

            user = User.query.filter_by(course=course, email=email).one()
            login_user(user)
            try:
                return jsonify({"success": True, "data": handler(**args)})
            except Failure as failure:
                return jsonify({"success": False, "message": str(failure)})

        app.add_url_rule(
            f"/api/sudo/{handler.__name__}",
            "sudo_" + handler.__name__,
            sudo_wrapped,
            methods=["POST"],
        )

        return handler

    @app.route("/", endpoint="index")
    @app.route("/history/")
    @app.route("/lab/")
    @app.route("/disc/")
    @app.route("/tutoring/")
    @app.route("/admin/")
    @app.route("/section/<path:path>")
    @app.route("/user/<path:path>")
    def generic(**_):
        return render_template("index.html", course=format_coursecode(get_course()))

    @app.route("/debug")
    def debug():
        refresh_state()
        return "<body></body>"

    @api
    def refresh_state():
        """
        Returns overall information about the section in json.

        Backend API functions calling refresh_state should be called
        using the useAPI hook in frontend.
        """
        config = CourseConfig.query.filter_by(course=get_course()).one_or_none()
        if config is None:
            config = CourseConfig(course=get_course())
            db.session.add(config)
            db.session.commit()

        out = {
            "enrolledSections": None,
            "taughtSections": None,
            "sections": [],
            "currentUser": None,
            "course": format_coursecode(get_course()),
            "config": config.json,
            "custom": None,
        }

        if current_user.is_authenticated:
            out["enrolledSections"] = [
                section.json
                for section in sorted(current_user.sections, key=section_sorter)
            ]
            out["taughtSections"] = [
                section.json
                for section in sorted(current_user.sections_taught, key=section_sorter)
            ]
            out["sections"] = [
                section.json
                for section in sorted(
                    Section.query.filter_by(course=get_course()).all(),
                    key=section_sorter,
                )
            ]
            out["currentUser"] = current_user.full_json

        return out

    @api
    @staff_required
    def fetch_section(section_id: Union[int, str]):
        """
        Returns info about a specific section in json.

        Backend API functions calling fetch_section should be
        called using the useSectionAPI hook in frontend.
        """
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).first()
        if not section:
            return {
                "id": section_id,
                "staff": None,
                "students": [],
                "description": "",
                "capacity": -1,
                "canSelfEnroll": False,
                "needsEnrollmentCode": False,
                "tags": "",
                "enrollmentCode": None,

                "name": "",
                "startTime": -1,
                "endTime": -1,
                "location": "",
                "callLink": ""
            }
        return section.full_json

    @api
    @login_required
    def join_section(target_section_id: str, enrollment_code: str = ""):
        target_section_id = int(target_section_id)
        # check if they can be added to the new section
        target_section: Section = Section.query.filter_by(
            id=target_section_id, course=get_course()
        ).one()

        # TODO: Really shouldn't be hard coded, but has to be with the code right now
        config = get_config()
        if target_section.name == "Discussion" and not config.can_students_join_disc:
            if any(current_user.sections):
                raise Failure("Students cannot change their enrolled discussion!")
            else:
                raise Failure("Students cannot add themselves themselves to discussions!")
        if target_section.name == "Lab" and not config.can_students_join_lab:
            if any(current_user.sections):
                raise Failure("Students cannot change their enrolled lab!")
            else:
                raise Failure("Students cannot add themselves themselves to labs!")
        if target_section.name == "Tutoring" and not config.can_students_join_tutoring:
            if any(current_user.sections):
                raise Failure("Students cannot change their enrolled tutorial!")
            else:
                raise Failure("Students cannot add themselves themselves to tutorials!")

        # If student is already enrolled in a section of the same type/name (Lab/Disc/etc)
        if any(map(lambda section: section.name == target_section.name, current_user.sections)):
            if target_section.name == "Discussion" and not config.can_students_change_disc:
                raise Failure("Students cannot change their enrolled discussion!")
            if target_section.name == "Lab" and not config.can_students_change_lab:
                raise Failure("Students cannot change their enrolled lab!")
            if target_section.name == "Tutoring" and not config.can_students_change_tutoring:
                raise Failure("Students cannot change their enrolled tutorials!")

        if target_section.capacity <= len(target_section.students):
            raise Failure("Target tutorial section is already full.")
        if (
            target_section.needs_enrollment_code
            and enrollment_code != target_section.enrollment_code
        ):
            raise Failure("Invalid enrollment code; cannot join section.")
        if not target_section.can_self_enroll:
            raise Failure("Cannot self-join this section.")
        # remove them from *all* old_sections for now

        add_student_helper(current_user, target_section)
        db.session.commit()

        return refresh_state()

    @api
    @login_required
    def leave_section(target_section_id: str):
        target_section_id = int(target_section_id)

        target_section: Section = Section.query.filter_by(
            id=target_section_id, course=get_course()
        ).one()

        # TODO: Really shouldn't be hard coded, but has to be with the code right now
        config = get_config()
        if target_section.name == "Discussion" and not config.can_students_change_disc:
            raise Failure("Students cannot remove themselves from discussions!")
        if target_section.name == "Lab" and not config.can_students_change_lab:
            raise Failure("Students cannot remove themselves from labs!")
        if target_section.name == "Tutoring" and not config.can_students_change_tutoring:
            raise Failure("Students cannot remove themselves from tutorials!")

        try:
            current_user.sections.remove(target_section)
        except:
            raise Failure("Removing student from section failed")
        db.session.commit()
        return refresh_state()

    @api
    @login_required
    def leave_all_sections():
        if not get_config().can_students_change:
            raise Failure("Students cannot remove themselves from sections!")

        current_user.sections = []

        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def claim_section(section_id: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        if section.name == "Lab":
            if not get_config().can_tutors_change_lab:
                raise Failure("Tutors cannot add themselves to labs!")
        elif section.name == "Discussion":
            if not get_config().can_tutors_change_disc:
                raise Failure("Tutors cannot add themselves to discussions!")
        elif section.name == "Tutoring":
            if not get_config().can_tutors_change_tutoring:
                raise Failure("Tutors cannot add themselves to tutoring sections!")

        if section.staff:
            raise Failure("Section is already claimed!")
        section.staff = current_user
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def unassign_section(section_id: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        if section.staff is None:
            raise Failure("Section is already unassigned!")
        if section.staff.email == current_user.email:
            if (section.name == "Lab" and not get_config().can_tutors_change_lab) or \
               (section.name == "Discussion" and not get_config().can_tutors_change_disc) or \
               (section.name == "Tutoring" and not get_config().can_tutors_change_tutoring):
                raise Failure("Tutors cannot remove themselves from sections!")
        else:
            if (section.name == "Lab" and not get_config().can_tutors_reassign_lab) or \
               (section.name == "Discussion" and not get_config().can_tutors_reassign_disc) or \
               (section.name == "Tutoring" and not get_config().can_tutors_reassign_tutoring):
                raise Failure("Tutors cannot remove other tutors from sections!")
        section.staff = None
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def update_section_description(section_id: str, description: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.description = description
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def update_section_call_link(section_id: str, call_link: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.call_link = call_link
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def update_section_enrollment_code(section_id: str, enrollment_code: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.enrollment_code = enrollment_code
        db.session.commit()
        return refresh_state()

    @api
    @admin_required
    def update_section_location(section_id: str, new_location: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.location = new_location
        db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @admin_required
    def update_section_time(section_id: str, day: str, start_time: str, end_time: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.start_time = parse_time_string(day, start_time)
        section.end_time = parse_time_string(day, end_time)
        db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @admin_required
    def update_section_tags(section_id: str, tags: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        section.tags = tags.split(",")
        db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @staff_required
    def start_session(section_id: str, start_time: int):
        section_id = int(section_id)
        existing_session = Session.query.filter_by(
            start_time=start_time, section_id=section_id
        ).first()
        if existing_session is None:
            db.session.add(
                Session(
                    start_time=start_time,
                    section_id=section_id,
                    course=get_course(),
                )
            )
            db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @staff_required
    def set_attendance(session_id: str, students: str, status: Optional[str]):
        session_id = int(session_id)
        session = Session.query.filter_by(id=session_id, course=get_course()).one()
        status = AttendanceStatus[status]
        for email in parse_emails(students):
            student = User.query.filter_by(
                email=email, course=get_course()
            ).one_or_none()
            if student is None:
                raise Failure(f"Student {email} is not enrolled")
            Attendance.query.filter_by(session_id=session_id, student=student).delete()
            if student is not None and status is not None:
                db.session.add(
                    Attendance(
                        status=status,
                        session_id=session_id,
                        student=student,
                        course=get_course(),
                    )
                )
        db.session.commit()
        return fetch_section(section_id=session.section_id)

    @api
    @admin_required
    def update_config(**kwargs):
        config = get_config()
        for key, value in kwargs.items():
            setattr(config, key, value)
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def remove_student(student: str, section_id: str):
        section_id = int(section_id)
        student = User.query.filter_by(email=student, course=get_course()).one()
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        student.sections.remove(section)
        db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @admin_required
    def remove_students(students: str):
        for s in parse_emails(students):
            student = User.query.filter_by(email=s, course=get_course()).one_or_none()
            if student:
                student.sections = []
        db.session.commit()
        return refresh_state()

    @api
    @staff_required
    def add_student(email: str, section_id: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        student = User.query.filter_by(email=email, course=get_course()).one_or_none()
        if student is None:
            student = User(email=email, name=email, is_staff=False, course=get_course())

        # for decoupling
        add_student_helper(student, section)
        db.session.commit()

        return fetch_section(section_id=section_id)

    @api
    @staff_required
    def add_students(emails: str, section_id: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        for email in parse_emails(emails):
            student = User.query.filter_by(
                email=email, course=get_course()
            ).one_or_none()
            if student is None:
                student = User(
                    email=email, name=email, is_staff=False, is_admin=False, course=get_course()
                )
            add_student_helper(student, section)
        db.session.commit()
        return fetch_section(section_id=section_id)

    @api
    @admin_required
    def delete_section(section_id: str):
        section_id = int(section_id)
        section = Section.query.filter_by(id=section_id, course=get_course()).one()
        if section.students:
            raise Failure("Cannot delete a non-empty section")
        db.session.delete(section)
        db.session.commit()

        return refresh_state()

    @api
    @admin_required
    def export_attendance():
        return export_helper()

    @rpc_export_attendance.bind(app)
    @only("grade-display", allow_staging=True)
    def export_attendance_rpc():
        login_user(User.query.filter_by(course="cs61a", is_staff=True).first())
        return export_helper()

    @api
    def export_attendance_secret(secret: str):
        if validate_secret(secret=secret) == "cs61a":
            return export_helper()

    def export_helper():
        stringify = dumps
        attendances = dict()
        emails = set()
        for user in (
            User.query.filter_by(is_staff=False, course=get_course())
            .options(joinedload(User.attendances).joinedload(Attendance.session))
            .all()
        ):
            emails.add(user.email)
            for attendance in user.attendances:
                try:
                    section_name = attendance.session.section.name
                except AttributeError:
                    section_name = "Session not associated with a section"
                if section_name not in attendances:
                    attendances[section_name] = {}
                if user.email not in attendances[section_name]:
                    attendances[section_name][user.email] = []
                attendances[section_name][user.email].append(
                    {
                        "section_id": attendance.session.section_id,
                        "start_time": attendance.session.start_time,
                        "status": attendance.status.name,
                    }
                )
        for email in emails:
            for attendance in attendances.values():
                if email not in attendance:
                    attendance[email] = []

        return {
            **refresh_state(),
            "custom": {
                "fileName": "attendances.json",
                "attendances": stringify(
                    [{"type": k, "attendances": v} for k, v in attendances.items()]
                ),
            },
        }

    @api
    @admin_required
    def export_rosters():
        # Produce CSV based on Import Enrollment Form Style:
        # Column titles are Student Email, Staff Email, Location, Day, Start, Type
        out = StringIO()
        writer = csv.writer(out)
        writer.writerow(["Student Email", "Staff Email", "Location", "Day", "Start", "Type"])

        for section in Section.query.filter_by(course=get_course()).all():
            staff_email = section.staff.email if section.staff else ""
            location = section.location or ""
            day = ""
            start = ""
            
            DAY_MAP = {
                0: "M",
                1: "T",
                2: "W",
                3: "Th",
                4: "F",
            }

            try:

                if isinstance(section.start_time, (int, float)):
                    # Interpret stored UNIX timestamps in America/LA timezones
                    tz = ZoneInfo("America/Los_Angeles")
                    dt = datetime.fromtimestamp(section.start_time, tz=tz)
                    day = DAY_MAP.get(dt.weekday(), "")  # e.g. "M", "Tu"
                    start = dt.strftime("%I:%M%p").lower().replace('m', '')  # e.g. "08:00a"
                else:
                    # fallback: output as-is (just as a string)
                    start = str(section.start_time or "")
            except Exception:
                day = ""
                start = str(section.start_time or "")

            for student in section.students:
                writer.writerow([student.email, staff_email, location, day, start, section.name or ""])

        csv_text = out.getvalue()
        return {
            **refresh_state(),
            "custom": {"fileName": "rosters.csv", "rosters": csv_text},
        }

    @api
    @staff_required
    def fetch_user(user_id: str):
        user_id = int(user_id)
        user = User.query.filter_by(id=user_id, course=get_course()).one_or_none()
        return user.full_json

    @api
    @admin_required
    def remind_tutors_to_setup_zoom_links():
        sections: List[Section] = Section.query.filter_by(
            call_link=None, course=get_course()
        ).all()
        tutor_emails = set()
        for section in sections:
            tutor_emails.add(section.staff.email)
        tutor_emails = sorted(tutor_emails)
        if not tutor_emails:
            raise Failure("All tutors have set up their Zoom links!")

        message = (
            "The following tutors have not yet set up their Zoom links for all their sections:\n"
            + "\n".join(f" • <!{email}>" for email in tutor_emails)
            + "\n Please do so ASAP! Thanks."
        )

        post_slack_message(course=get_course(), message=message, purpose="tutors")

        return refresh_state()

    @api
    @admin_required
    def import_sections_from_sheet(url: str):
        import_sections_from_url(url)
        return refresh_state()

    @api
    @admin_required
    def import_enrollment_from_sheet(url: str):
        import_enrollment_from_url(url)
        return refresh_state()

    @api
    @admin_required
    def reset_sections():
        course = get_course()
        for section in Section.query.filter_by(course=course).all():
            section.staff = None
        Attendance.query.filter_by(course=course).delete()
        Session.query.filter_by(course=course).delete()

        for user in User.query.filter_by(course=course).all():
            user.sections.clear()

        User.query.filter_by(course=course).delete()
        Section.query.filter_by(course=course).delete()
        db.session.commit()
        return refresh_state()

    @api
    @admin_required
    def fetch_to_drop():
        students = ""
        for student in (
            User.query.filter_by(is_staff=False, course=get_course())
            .filter(any(User.sections))
            .all()
        ):
            n_absent = 0
            attended_first = attended_second = False
            n_first_week_sessions = 0
            for attendance in student.attendances:
                start_time = attendance.session.start_time
                if (
                    start_time >= FIRST_WEEK_START
                    and start_time < FIRST_WEEK_START + ONE_WEEK
                ):
                    n_first_week_sessions += 1
                if attendance.status == AttendanceStatus.absent:
                    n_absent += 1
                else:
                    if (
                        start_time >= FIRST_WEEK_START
                        and start_time < FIRST_WEEK_START + ONE_WEEK
                    ):
                        if not attended_first:
                            attended_first = True
                        else:
                            attended_second = True
            if (
                (not IS_SUMMER and not attended_first and n_first_week_sessions > 0)
                or (
                    (IS_SUMMER and not attended_second and n_first_week_sessions > 1)
                    or (IS_SUMMER and not attended_first and n_first_week_sessions > 0)
                )
                or n_absent > MAX_ABSENCES
            ):
                students += student.email + ", "
        return {
            **refresh_state(),
            "custom": {"students": students[:-2]},
        }
    
    @admin_required
    @api
    def get_student_section_ids(email: str):
        student = User.query.filter_by(
            email= email,
            course=get_course()
        ).one_or_none()
        if (student is None):
            return {email: []}
        section_ids = [section.id for section in student.sections]
        return {email: section_ids}

    #get the student's discussion attendance
    @admin_required
    @api
    def get_student_discussion_attendance(email:str):
        student = User.query.filter_by(
                    email = email,
                    course=get_course()
                ).one_or_none()
        
        discussion_section = None
        if student:
            for section in student.sections:
                if section.name == 'Discussion':
                    discussion_section = section

        discussion_present_days = []
        if discussion_section:
            attendances = (Attendance.query.join(Attendance.session)
            .filter(
                Attendance.student_id == student.id,
                Attendance.status == AttendanceStatus.present,
                Session.section_id == discussion_section.id
            )
            .options(joinedload(Attendance.session))
            .all()
            )
            discussion_present_days = [attendance.session.start_time for attendance in attendances]
        return {"discussion attendance": discussion_present_days}

    #get the student's lab attendance
    @admin_required
    @api
    def get_student_lab_attendance(email:str):
        student = User.query.filter_by(
                    email = email,
                    course=get_course()
                ).one_or_none()
        lab_section = None
        if student:
            for section in student.sections:
                if section.name == 'Lab':
                    lab_section = section
        lab_present_days = []
        if lab_section:
            attendances = (Attendance.query.join(Attendance.session)
            .filter(
                Attendance.student_id == student.id,
                Attendance.status == AttendanceStatus.present,
                Session.section_id == lab_section.id
            )
            .options(joinedload(Attendance.session))
            .all()
            )
            lab_present_days = [attendance.session.start_time for attendance in attendances]
        return {"lab attendance": lab_present_days}
    
    #get the student's tutoring attendance
    @admin_required
    @api
    def get_student_tutoring_attendance(email:str):
        student = User.query.filter_by(
                    email = email,
                    course=get_course()
                ).one_or_none()
        tutoring_section = None
        if student:
            for section in student.sections:
                if section.name == 'Tutoring':
                    tutoring_section = section
        tutoring_present_days = []
        if tutoring_section:
            attendances = (Attendance.query.join(Attendance.session)
            .filter(
                Attendance.student_id == student.id,
                Attendance.status == AttendanceStatus.present,
                Session.section_id == tutoring_section.id
            )
            .options(joinedload(Attendance.session))
            .all()
            )
            tutoring_present_days = [attendance.session.start_time for attendance in attendances]
        return {"tutoring attendance": tutoring_present_days}



