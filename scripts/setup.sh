#!/usr/bin/env bash
# scripts/setup.sh — One-shot development environment setup
set -e

echo "🔥 BlockShield Setup"
echo "===================="

# ── Backend ───────────────────────────────────────────────────────────────────
echo ""
echo "📦 Setting up Python backend..."
cd backend

if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Install Python 3.11+ first."
  exit 1
fi

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ Created backend/.env (edit with your API keys)"
else
  echo "ℹ️  backend/.env already exists"
fi

# Bootstrap ML model
python3 -c "
from app.ml.model import get_detector
d = get_detector()
print('✅ ML model bootstrapped')
"

cd ..

# ── Frontend ──────────────────────────────────────────────────────────────────
echo ""
echo "📦 Setting up React frontend..."
cd frontend

if ! command -v node &>/dev/null; then
  echo "❌ Node.js not found. Install Node.js 18+ first."
  exit 1
fi

npm install --silent

if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "✅ Created frontend/.env.local"
fi

cd ..

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env  → add ALCHEMY_API_KEY or INFURA_PROJECT_ID"
echo "     (leave blank to run in simulation mode)"
echo ""
echo "  2. Start backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  3. Start frontend: cd frontend && npm run dev"
echo ""
echo "  Or run everything with Docker: docker-compose up --build"
echo ""
echo "  Dashboard: http://localhost:3000"
echo "  API docs:  http://localhost:8000/docs"
