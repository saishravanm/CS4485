#!/bin/bash
# Quick setup script for data ingestion pipeline

echo "=========================================="
echo "Data Ingestion Pipeline Setup"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "config.py" ]; then
    echo "Error: Please run this script from the data-ingestion directory"
    exit 1
fi

# Install dependencies
echo "1. Installing Python dependencies..."
pip install googlemaps openai beautifulsoup4 lxml python-dotenv requests 2>&1 | tail -5
echo "   ✓ Dependencies installed"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "2. Creating .env file..."
    cat > .env << 'EOF'
# Google Places API Key
# Get from: https://console.cloud.google.com/apis/credentials
GOOGLE_PLACES_API_KEY=your_google_api_key_here

# OpenAI API Key
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Override defaults
# OPENAI_MODEL=gpt-4o-mini
# MAX_HTML_LENGTH=50000
# REQUEST_TIMEOUT=10
# RATE_LIMIT_DELAY=1.0
EOF
    echo "   ✓ Created .env file"
    echo ""
    echo "   ⚠️  IMPORTANT: Edit .env and add your API keys!"
    echo "   Run: nano .env (or use your favorite editor)"
else
    echo "2. .env file already exists"
fi
echo ""

# Make scripts executable
echo "3. Making scripts executable..."
chmod +x run_pipeline.py merge_csvs.py scripts/*.py
echo "   ✓ Scripts are executable"
echo ""

# Test configuration
echo "4. Testing configuration..."
echo ""
python config.py
echo ""

echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Test with: python scripts/1_discover_organizations.py"
echo "  3. Or run full pipeline: python run_pipeline.py"
echo ""
echo "See QUICKSTART.md for detailed instructions"
echo ""

