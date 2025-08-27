from datetime import datetime, timedelta
from os import getenv
from random import choice

from zoneinfo import ZoneInfo

from main import app
from models import Section, User, db, user_section


def seed():
    if getenv("ENV") == "prod":
        return
    with app.app_context():
        db.create_all()
        pst = ZoneInfo("US/Pacific")
        discussions, labs = [], []
        section_count = 100
        for i in range(section_count):
            t = datetime(year=2020, month=8, day=20, hour=i % 10, minute=0, second=0, tzinfo=pst)

            discussion_section = Section(
                course="cs61a",
                description=f"This is the {section_count + i + 1}th demo section.",
                can_self_enroll=True,
                capacity=5,
                name="Discussion",
                start_time=t.timestamp(),
                end_time=(t + timedelta(minutes=30)).timestamp(),
                location="Wheeler 108",
            )

            lab_section = Section(
                course="cs61a",
                description=f"This is the {i + 1}th demo section.",
                can_self_enroll=True,
                capacity=5,
                name="Lab",
                start_time=t.timestamp(),
                end_time=(t + timedelta(minutes=30)).timestamp(),
                location="Soda 275",
            )

            lab_section.tags = ["NPE"]
            discussion_section.tags = ["NPE"]
            labs.append(lab_section)
            discussions.append(discussion_section)
            db.session.add(lab_section)
            db.session.add(discussion_section)

        users = []

        for i in range(section_count * 2):
            discussion = choice(discussions)
            lab = choice(labs)
            user = User(
                course="cs61a",
                email=f"gobears{i}@berkeley.edu",
                name=f"Oski {i}th of his name",
                is_staff=False,
            )
            user.sections = [discussion, lab]
            users.append(user)

        db.session.commit()


if __name__ == "__main__":
    seed()
