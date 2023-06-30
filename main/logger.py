import logging

from flask_socketio import SocketIO


class WebSocketHandler(logging.Handler):
    def __init__(self, socket_obj: SocketIO, event_name, namespace, *args, **kwargs):
        self.socket_obj = socket_obj
        self.event_name = event_name
        self.namespace = namespace
        super().__init__(*args, **kwargs)

    def emit(self, record: logging.LogRecord):
        self.socket_obj.emit(
            event="new_log",
            data={
                "message": self.formatter.format(record),
                "level": record.levelname
            },
            namespace="/logs"
        )
