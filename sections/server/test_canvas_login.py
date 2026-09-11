import time
import unittest
from unittest.mock import patch

from canvasapi.exceptions import InvalidAccessToken
from flask import Flask, session

from login import create_login_client
from models import Section, User, db
from state import create_state_client


class CanvasLoginTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test", TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        create_state_client(self.app)
        with patch("login.create_oauth_client") as oauth:
            create_login_client(self.app)
        self.login_callback = oauth.call_args.kwargs["success_callback"]
        self.assertFalse(oauth.call_args.kwargs["store_canvas_tokens_in_session"])
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        staff = User(email="staff@test", name="Staff", is_staff=True,
                     is_admin=False, course="test")
        known = User(email="known@test", name="Known", is_staff=False,
                     is_admin=False, course="test")
        section = Section(course="test", name="Lab", location="Room")
        db.session.add_all([staff, known, section])
        db.session.commit()
        self.staff_id, self.section_id = staff.id, section.id
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
                self.assertEqual(Section.query.get(self.section_id).students, [])

    def test_fresh_token_is_passed_to_canvas(self):
        self.authorize()
        with patch("state.canvas_service.get_student_from_email", return_value="New") as lookup:
            self.assertTrue(self.add_students("new@test")["success"])
        lookup.assert_called_once_with("new@test", "access")

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
                with patch("login.get_bcourses_id", return_value=1), \
                     patch("login.canvas_service.get_email", return_value="staff@test"), \
                     patch("login.canvas_service.get_name", return_value="Staff"), \
                     patch("login.canvas_service.get_preferred_name", return_value="Staff"), \
                     patch("login.canvas_service.get_user_courses", return_value=[]), \
                     patch("login.canvas_service.get_course"), \
                     patch("login.canvas_service.is_staff", return_value=is_staff), \
                     patch("login.canvas_service.is_admin", return_value=False):
                    self.login_callback({
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


if __name__ == "__main__":
    unittest.main()
