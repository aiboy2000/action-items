#!/bin/bash

echo "Setting up Action Items System..."

# Create necessary directories
mkdir -p data logs uploads processed

# Create .env file from example
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please update with your settings."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Download spaCy Japanese model
echo "Downloading Japanese language model..."
python -m spacy download ja_core_news_sm

# Initialize database
echo "Initializing database..."
python -c "from src.core.database import init_db; init_db()"

echo "Setup complete!"
echo ""
echo "To start the API server:"
echo "  python main.py"
echo ""
echo "To start the web UI:"
echo "  python app.py"
echo ""
echo "API documentation available at: http://localhost:8000/docs"