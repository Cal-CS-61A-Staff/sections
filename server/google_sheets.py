import re
from typing import List

import google.auth
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _spreadsheet_id(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise ValueError(f"Not a Google Sheets URL: {url}")
    return m.group(1)


def read_spreadsheet(*, url: str, sheet_name: str) -> List[List[str]]:
    """Read every row of ``sheet_name``, padded to the width of the header row.

    Authenticates with Application Default Credentials: the Cloud Run service
    account in production, or ``gcloud auth application-default login``
    locally. The sheet must be shared with that account.
    """
    credentials, _ = google.auth.default(scopes=SCOPES)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    rows = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=_spreadsheet_id(url), range=sheet_name)
        .execute()
        .get("values", [])
    )
    # The Sheets API drops trailing empty cells, so short rows are padded.
    width = len(rows[0]) if rows else 0
    return [row + [""] * (width - len(row)) for row in rows]
