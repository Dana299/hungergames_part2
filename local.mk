run-app:
	python3 entry.py

run-celery-worker:
	celery -A main.make_celery worker -l info

run-celery-beat:
	celery -A main.make_celery beat -l info

run-all:
	$(MAKE) -f local.mk run-app &
	$(MAKE) -f local.mk run-celery-worker &
	$(MAKE) -f local.mk run-celery-beat &

stop-all:
	pkill -f "python3 entry.py" &
	pkill -f "celery -A main.make_celery worker -l info" &
	pkill -f "celery -A main.make_celery beat -l info" &
