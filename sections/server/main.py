from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension

from datetime import timedelta
from login import create_login_client
from models import create_models, db
from state import create_state_client

app = Flask(
    __name__, static_url_path="", static_folder="static", template_folder="static"
)
app.url_map.strict_slashes = False


if __name__ == "__main__":
    app.debug = True

create_state_client(app)
create_login_client(app)

create_models(app)
db.init_app(app)

# Signed cookies avoid database session writes on ordinary requests.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

with app.app_context():
    db.create_all(app=app)


if __name__ == "__main__":
    DebugToolbarExtension(app)
    app.run(host="127.0.0.1", port=8000, debug=True)
