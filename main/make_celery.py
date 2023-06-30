from celery import Celery
from celery.schedules import crontab
from flask import Flask

from main import create_app
from main.tasks import delete_unavailable_resources, get_response_from_resources

flask_app: Flask = create_app()
celery: Celery = flask_app.extensions["celery"]


@celery.on_after_configure.connect
def setup_periodic_making_requests(sender: Celery, **kwargs):
    """Add periodic task for getting responses from all resources from DB and deleting unavailable ones."""
    sender.add_periodic_task(
        schedule=crontab(
            minute="0",
            hour=flask_app.config["PERIODIC_TASKS"]["GET_RESPONSES_FROM_URLS"]["RUN_SCHEDULE_HOUR"]
        ),
        sig=get_response_from_resources,
        name="get_response_from_resources",
    )

    sender.add_periodic_task(
        schedule=crontab(
            minute="0",
            hour=flask_app.config["PERIODIC_TASKS"]["DELETE_UNAVAILABLE_URLS"]["RUN_SCHEDULE_HOUR"]
        ),
        sig=delete_unavailable_resources,
        name="delete_unavailable",
        kwargs={
            "times_unavailable": flask_app.config["PERIODIC_TASKS"]["DLETE_UNAVAILABLE_URLS"]["MAX_RETRIES"]
        }
    )
