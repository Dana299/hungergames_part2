#!/bin/sh
set -e

# apply migrations
# export FLASK_APP=main/app
flask db init
flask db migrate -m "Initial migration."
flask db upgrade

# run app
python3 entry.py