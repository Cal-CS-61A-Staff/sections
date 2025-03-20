from enum import Enum
from random import randrange
from typing import List
from urllib.parse import quote

import flask
from flask_login import UserMixin, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload

from common.course_config import get_course_id, is_admin
from common.db import database_url


def create_models(app: flask.Flask):
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy()

# Association Table for User - Section Pairs because each user can have multiple sections
user_section = db.Table('user_section',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('section_id', db.Integer, db.ForeignKey('section.id'), primary_key=True)
)


class Section(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    course: str = db.Column(db.String(255), index=True)
    description: str = db.Column(db.String(255))
    capacity: int = db.Column(db.Integer)
    can_self_enroll: bool = db.Column(db.Boolean)
    enrollment_code: str = db.Column(db.String(255), nullable=True)
    staff_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    staff: "User" = db.relationship(
        "User",
        backref=db.backref("sections_taught", lazy="joined"),
        lazy="joined",
        foreign_keys=[staff_id],
    )
    tag_string: str = db.Column(
        db.String(255), nullable=False, default=""
    )  # comma separated list of tags
    students: List["User"] = db.relationship('User', secondary=user_section, back_populates='sections', lazy='joined')
    # moved attributes from slots to section for decoupling
    name: str = db.Column(db.String(255)) # indicates section type e.g. lab or discussion
    start_time: int = db.Column(db.Integer)
    end_time: int = db.Column(db.Integer)
    location: str = db.Column(db.String(255), nullable=False)
    call_link: str = db.Column(db.String(255), nullable=True)
    sessions: List["Session"]

    @property
    def tags(self):
        return self.tag_string.split(",")

    @tags.setter
    def tags(self, tags: List[str]):
        self.tag_string = ",".join(tags)

    @property
    def needs_enrollment_code(self):
        return self.enrollment_code not in ["", None]

    @property
    def json(self):
        return {
            "id": str(self.id),
            "staff": self.staff.json if self.staff is not None else None,
            "students": [
                student.json
                for student in sorted(self.students, key=lambda student: student.name)
            ],
            "description": self.description,
            "capacity": self.capacity,
            "canSelfEnroll": self.can_self_enroll,
            "needsEnrollmentCode": self.needs_enrollment_code,
            "tags": self.tags,
            "enrollmentCode": self.enrollment_code if current_user.is_staff else None,

            # transfered attributes from slots for decoupling
            "name": self.name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "location": self.location,
            "callLink": self.call_link,
        }

    @property
    def full_json(self):
        return {
            **self.json,
            "sessions": [
                session.full_json
                for session in sorted(
                    self.sessions, key=lambda session: session.start_time
                )
            ],
        }


class Session(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    course: str = db.Column(db.String(255), index=True)
    start_time: int = db.Column(db.Integer)
    section_id: int = db.Column(db.Integer, db.ForeignKey("section.id"), index=True) 
    section: Section = db.relationship("Section", backref=db.backref("sessions"), lazy="joined")
    attendances: List["Attendance"]

    @property
    def json(self):
        return {"id": self.id, "startTime": self.start_time}

    @property
    def full_json(self):
        return {
            **self.json,
            "attendances": [
                attendance.json
                for attendance in sorted(
                    self.attendances, key=lambda attendance: attendance.student.name
                )
            ],
        }


# note that the *keys* are persisted to the db, not the values
class AttendanceStatus(Enum):
    present = 1
    excused = 2
    absent = 3


class Attendance(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    course: str = db.Column(db.String(255), index=True)
    status: AttendanceStatus = db.Column(db.Enum(AttendanceStatus))
    session_id: int = db.Column(db.Integer, db.ForeignKey("session.id"), index=True)
    session: Session = db.relationship(
        "Session",
        backref=db.backref("attendances", lazy="joined"),
        lazy="joined",
        innerjoin=True,
    )
    student_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    student: "User" = db.relationship(
        "User", backref=db.backref("attendances"), lazy="joined", innerjoin=True
    )

    @property
    def json(self):
        if not current_user.is_staff and self.student_id != current_user.id:
            raise Failure("Attendance data of other users is staff-only")
        return {"student": self.student.json, "status": self.status.name}

    @property
    def full_json(self):
        return {
            **self.json,
            "session": self.session.json,
            "section": self.session.section.json if self.session.section else None
        }


class User(db.Model, UserMixin):
    # just here to make PyCharm stop complaining
    def __init__(self, email: str, name: str, is_staff: bool, course: str):
        # noinspection PyArgumentList
        super().__init__(email=email, name=name, is_staff=is_staff, course=course)

    id: int = db.Column(db.Integer, primary_key=True)
    course: str = db.Column(db.String(255), index=True)
    email: str = db.Column(db.String(255), index=True)
    name: str = db.Column(db.String(255))
    is_staff: bool = db.Column(db.Boolean)

    sections: List["Section"] = db.relationship(
        'Section', secondary=user_section, back_populates='students', lazy='joined'
    )
    attendances: List["Attendance"]

    @property
    def json(self):
        can_see = (
            current_user.is_staff
            or self.is_staff
            or self.id == current_user.id
            or any([s in self.sections for s in current_user.sections])
        )
        if can_see:
            return {
                "id": self.id,
                "name": self.name,
                "email": self.email,
                "isStaff": self.is_staff,
                "backupURL": f"https://okpy.org/admin/course/{get_course_id()}/{quote(self.email)}",
            }
        else:
            return {
                "id": randrange(10**6),
                "name": "Anon Student",
                "email": "",
                "isStaff": False,
                "backupURL": "",
            }

    @property
    def full_json(self):
        attendances = (
            Attendance.query.filter_by(student_id=self.id)
            .options(
                joinedload(Attendance.session, innerjoin=True)
                .joinedload(Session.section)
                .joinedload(Section.staff)
            )
            .all()
        )
        return {
            **self.json,
            "isAdmin": is_admin(self.email),
            "attendanceHistory": [
                attendance.full_json
                for attendance in sorted(
                    attendances, key=lambda attendance: attendance.session.start_time
                )
            ],
        }


class CourseConfig(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    course: str = db.Column(db.String(255), index=True)

    can_students_join_lab =  db.Column(db.Boolean, default=True)
    can_students_change_lab = db.Column(db.Boolean, default=True)
    can_tutors_change_lab = db.Column(db.Boolean, default=True)
    can_tutors_reassign_lab = db.Column(db.Boolean, default=True)
    can_students_join_disc = db.Column(db.Boolean, default=True)
    can_students_change_disc = db.Column(db.Boolean, default=True)
    can_tutors_change_disc = db.Column(db.Boolean, default=True)
    can_tutors_reassign_disc = db.Column(db.Boolean, default=True)
    can_students_join_tutoring = db.Column(db.Boolean, default=True)
    can_students_change_tutoring = db.Column(db.Boolean, default=True)
    can_tutors_change_tutoring = db.Column(db.Boolean, default=True)
    can_tutors_reassign_tutoring = db.Column(db.Boolean, default=True)

    message: str = db.Column(db.String(1024), default="")

    @property
    def json(self):
        return {
            "canStudentsJoinLab": self.can_students_join_lab, 
            "canStudentsChangeLab": self.can_students_change_lab,
            "canTutorsChangeLab": self.can_tutors_change_lab,
            "canTutorsReassignLab": self.can_tutors_reassign_lab,
            "canStudentsJoinDiscussion": self.can_students_join_disc,
            "canStudentsChangeDiscussion": self.can_students_change_disc,
            "canTutorsChangeDiscussion": self.can_tutors_change_disc,
            "canTutorsReassignDiscussion": self.can_tutors_reassign_disc,
            "canStudentsJoinTutoring": self.can_students_join_tutoring,
            "canStudentsChangeTutoring": self.can_students_change_tutoring,
            "canTutorsChangeTutoring": self.can_tutors_change_tutoring,
            "canTutorsReassignTutoring": self.can_tutors_reassign_tutoring,
            "message": self.message,
        }


class Failure(Exception):
    pass
