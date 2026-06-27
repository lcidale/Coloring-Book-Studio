#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "⚠️  No .env found — copying .env.example"
  cp .env.example .env
  echo "   Edit .env and add your REPLICATE_API_TOKEN, then re-run."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment…"
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

HOST=$(grep HOST .env | cut -d= -f2 | tr -d ' ' || echo "127.0.0.1")
PORT=$(grep PORT .env | cut -d= -f2 | tr -d ' ' || echo "8000")

echo ""
echo "🎨 Coloring Book Studio"
echo "   http://${HOST}:${PORT}"
echo ""

uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
