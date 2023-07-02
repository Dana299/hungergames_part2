#!/bin/sh
set -e

# apply migrations
flask db upgrade

# run app
python3 entry.py