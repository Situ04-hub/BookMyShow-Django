#!/usr/bin/env bash
# Exit on error
set -o errexit

python3 -m pip install -r ../requirements.txt --break-system-packages
python3 manage.py collectstatic --no-input
python3 manage.py migrate