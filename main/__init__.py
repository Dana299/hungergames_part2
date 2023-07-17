from flask import Blueprint
from flask_socketio import SocketIO

socketio = SocketIO()
log_buffer = list()
bp = Blueprint(
    name='main',
    url_prefix='/api',
    import_name=__name__,
    template_folder='templates',
    static_folder='templates',
)

from .app import create_app

app = create_app()

from main import routes
from main.api import routes as api_routes

app.register_blueprint(blueprint=bp)
socketio.init_app(app)
app.logger.info("app started")
