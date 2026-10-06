import requests
from flask import current_app

from models import Failure


def post_slack_message(message: str):
    url = current_app.config.get("SLACK_WEBHOOK_URL")
    if not url:
        raise Failure("Slack notifications are not set up for this course.")
    requests.post(url, json={"text": message}, timeout=10).raise_for_status()
