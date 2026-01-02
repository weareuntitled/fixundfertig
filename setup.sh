#!/bin/bash
echo "🚀 Installing dependencies..."
pip install -r app/requirements.txt
echo "💻 Starting App..."
python3 app/main.py
