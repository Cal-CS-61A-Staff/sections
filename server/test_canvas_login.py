import time
import unittest
from unittest.mock import patch

from canvasapi.exceptions import InvalidAccessToken
from flask import Flask, session

from login import complete_login, create_login_client
from models import Section, User, db
from state import create_state_client


class CanvasLoginTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test", TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            CANVAS_SERVER_URL="https://canvas.test/",
            CANVAS_CLIENT_ID="id", CANVAS_CLIENT_SECRET="secret",
        )
        db.init_app(self.app)
        create_state_client(self.app)
        create_login_client(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        staff = User(email="staff@test", name="Staff", is_staff=True,
                     is_admin=False, course="test")
        known = User(email="known@test", name="Known", is_staff=False,
                     is_admin=False, course="test")
        section = Section(
            course="test",
            name="Lab",
            location="Room",
            description="",
            capacity=30,
            can_self_enroll=True,
            start_time=0,
            end_time=3600,
        )
        db.session.add_all([staff, known, section])
        db.session.commit()
        self.staff_id = staff.id
        self.known_id = known.id
        self.section_id = section.id
        for target in ("login.get_course", "state.get_course"):
            patcher = patch(target, return_value="test")
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = self.app.test_client()
        with self.client.session_transaction() as browser:
            browser["_user_id"] = str(self.staff_id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def add_students(self, emails):
        response = self.client.post("/api/add_students", json={
            "emails": emails, "section_id": str(self.section_id),
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def authorize(self, expires_in=3600):
        with self.client.session_transaction() as browser:
            browser["canvas_access_token"] = "access"
            browser["canvas_token_expires_at"] = time.time() + expires_in

    def test_existing_students_need_no_canvas_token(self):
        with patch("state.canvas_service.get_student_from_email") as lookup:
            self.assertTrue(self.add_students("known@test")["success"])
        lookup.assert_not_called()

    def test_expired_or_missing_token_requests_reauthentication_without_partial_batch(self):
        for expires_in in (None, -1):
            with self.subTest(expires_in=expires_in):
                if expires_in is not None:
                    self.authorize(expires_in)
                with patch("state.canvas_service.get_student_from_email") as lookup:
                    result = self.add_students("known@test,new@test")
                self.assertFalse(result["success"])
                self.assertIn("sign in", result["message"])
                lookup.assert_not_called()
                db.session.remove()
                self.assertEqual(db.session.get(Section, self.section_id).students, [])

    def test_fresh_token_is_passed_to_canvas(self):
        self.authorize()
        with patch("state.canvas_service.get_student_from_email", return_value="New") as lookup:
            self.assertTrue(self.add_students("new@test")["success"])
        lookup.assert_called_once_with("new@test", "access")
        db.session.remove()
        new = User.query.filter_by(email="new@test").one()
        self.assertEqual([s.id for s in new.sections], [self.section_id])

    def test_revoked_token_requests_reauthentication(self):
        self.authorize()
        with patch("state.canvas_service.get_student_from_email", side_effect=InvalidAccessToken("revoked")):
            result = self.add_students("new@test")
        self.assertFalse(result["success"])
        self.assertIn("sign in", result["message"])

    def test_login_retains_only_staff_access_token_and_logout_clears_it(self):
        for is_staff in (True, False):
            with self.subTest(is_staff=is_staff), self.app.test_request_context():
                session["canvas_access_token"] = "previous"
                session["canvas_token_expires_at"] = 123
                with patch("login.canvas_service.get_profile",
                           return_value={"primary_email": "staff@test", "short_name": "Staff"}), \
                     patch("login.canvas_service.get_course_roles", return_value=(is_staff, False)):
                    complete_login({
                        "user": {"id": 123}, "access_token": "access",
                        "refresh_token": "must-not-be-stored", "expires_in": 3600,
                    })
                self.assertEqual(session.get("canvas_access_token"), "access" if is_staff else None)
                self.assertNotIn("refresh_token", session)
                self.assertTrue(session.permanent)
        self.authorize()
        with patch("login.url_for", return_value="/"):
            self.client.get("/oauth/logout")
        with self.client.session_transaction() as browser:
            self.assertNotIn("canvas_access_token", browser)
            self.assertNotIn("canvas_token_expires_at", browser)

    def test_student_refresh_uses_summaries_and_keeps_enrolled_roster(self):
        known = db.session.get(User, self.known_id)
        section = db.session.get(Section, self.section_id)
        peer = User(
            email="peer@test",
            name="Peer",
            is_staff=False,
            is_admin=False,
            course="test",
        )
        unrelated = User(
            email="unrelated@test",
            name="Unrelated",
            is_staff=False,
            is_admin=False,
            course="test",
        )
        other_section = Section(
            course="test",
            name="Discussion",
            location="Other Room",
            description="",
            capacity=25,
            can_self_enroll=True,
            start_time=7200,
            end_time=10800,
        )
        section.students.extend([known, peer])
        other_section.students.append(unrelated)
        db.session.add_all([peer, unrelated, other_section])
        db.session.commit()

        with self.client.session_transaction() as browser:
            browser["_user_id"] = str(self.known_id)
        with patch("state.format_coursecode", return_value="Test"):
            response = self.client.post("/api/refresh_state", json={})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        state = result["data"]
        summaries = {item["id"]: item for item in state["sections"]}

        enrolled_summary = summaries[str(self.section_id)]
        other_summary = summaries[str(other_section.id)]
        self.assertEqual(enrolled_summary["enrollmentCount"], 2)
        self.assertEqual(len(enrolled_summary["students"]), 2)
        self.assertEqual(enrolled_summary["students"], [None, None])
        self.assertEqual(other_summary["enrollmentCount"], 1)
        self.assertEqual(other_summary["students"], [None])

        self.assertEqual(len(state["enrolledSections"]), 1)
        roster = state["enrolledSections"][0]["students"]
        self.assertEqual(
            {student["email"] for student in roster},
            {"known@test", "peer@test"},
        )
        self.assertNotIn("unrelated@test", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
