#!/bin/bash
echo "Starting AutoReadMe Backend..."
echo "Python version: $(python --version)"
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Starting gunicorn..."
gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT 