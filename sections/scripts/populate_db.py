assert False  # don't run this!

import os
import sys
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

sys.path.append(os.path.abspath("server"))

from common.rpc.auth import read_spreadsheet


from main import app
from models import Section, User, db, user_section

staff_reader = read_spreadsheet(
    url="https://docs.google.com/spreadsheets/d/1kfMxgqN6FNxOaQwdWomjG_2x54Uoz8FnMez_dz8EPrg/",
    sheet_name=f"Sections",
)


def parse_time_string(day, time):
    hour, min, ampm = int(time[0:2]), int(time[3:5]), time[5]

    day_offset = ["M", "T", "W", "Th", "F"].index(day)
    hour_offset = 12 if hour != 12 and ampm == "p" else 0

    return datetime(
        year=2021,
        month=8,
        day=23 + day_offset,
        hour=hour + hour_offset,
        minute=min,
        tzinfo=pst
    ).timestamp()


pst = ZoneInfo("US/Pacific")

lookup = {}

with app.app_context():
    db.drop_all()
    db.create_all()

    users = {}

    for row in staff_reader[1:]:
        (
            email,
            name,
            _,
            lab_id,
            lab_location,
            lab_day,
            lab_start,
            lab_end,
            disc_id,
            disc_location,
            disc_day,
            disc_start,
            disc_end,
            tag,
            _,
        ) = row

        if email not in users:
            users[email] = User(email=email, name=name, is_staff=True)

        lab_section = Section(
            capacity=40,
            can_self_enroll=tag != "Scholars",
            staff=users[email],
            name="Lab",
            location=lab_location,
            start_time=(
                parse_time_string(lab_day, lab_start)
                + timedelta(weeks=1).total_seconds()
            ),
            end_time=(
                parse_time_string(lab_day, lab_end) + timedelta(weeks=1).total_seconds()
            ),
        )

        discussion_section = Section(
            capacity=40,
            can_self_enroll=tag != "Scholars",
            staff=users[email],
            name="Discussion",
            location=disc_location,
            start_time=parse_time_string(disc_day, disc_start),
            end_time=parse_time_string(disc_day, disc_end),
        )

        for s in [lab_section, discussion_section]: 
            s.tags = [tag]
            db.session.add(s)

    db.session.commit()
