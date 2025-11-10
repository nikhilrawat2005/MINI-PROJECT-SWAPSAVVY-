#!/bin/bash
# scripts/setup.sh - Complete Setup Script

echo "🚀 Setting up SwapSavvy Pro..."
echo "================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Setup environment variables
echo "🔐 Setting up environment..."
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your actual credentials"
fi

# Initialize database
echo "🗄️ Initializing database..."
flask db upgrade

# Create upload directories
echo "📁 Creating upload directories..."
mkdir -p static/uploads/avatars
mkdir -p static/uploads/covers
mkdir -p static/uploads/posts
mkdir -p static/uploads/portfolio
mkdir -p static/uploads/documents

# Set proper permissions
echo "🔒 Setting permissions..."
chmod -R 755 static/uploads/

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "🎯 Next steps:"
echo "   1. Update .env file with your email credentials"
echo "   2. Run: source venv/bin/activate"
echo "   3. Run: flask run"
echo "   4. Open http://localhost:5000 in your browser"
echo ""
echo "🚀 To start the application:"
echo "   source venv/bin/activate && flask run"
echo ""