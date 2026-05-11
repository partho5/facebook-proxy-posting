#!/bin/bash
set -e

cd "$(dirname "$0")"

git pull

venv/bin/pip install -r requirements.txt --quiet

sudo systemctl restart proxy-facebook-posting

echo "Deployed."
