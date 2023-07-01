import logging

from flask_socketio import SocketIO


class WebSocketHandler(logging.Handler):
    def __init__(self, socket_obj: SocketIO, event_name, namespace, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.socket_obj = socket_obj
        self.event_name = event_name
        self.namespace = namespace

    def emit(self, record: logging.LogRecord):
        self.socket_obj.emit(
            event="new_log",
            data={
                "message": self.formatter.format(record),
                "level": record.levelname
            },
            namespace="/logs"
        )


class LogBufferHandler(logging.Handler):
    def __init__(self, buffer_obj, max_size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer_obj = buffer_obj
        self.size = max_size

    def emit(self, record: logging.LogRecord) -> None:
        if len(self.buffer_obj) >= self.size:
            self.buffer_obj.pop(-1)
        self.buffer_obj.append(
            dict(level=record.levelname, message=self.formatter.format(record))
        )
