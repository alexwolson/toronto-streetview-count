#!/bin/bash

# Toronto Street View Counter - Server Deployment Script
# This script sets up the environment on a fresh server

set -e  # Exit on any error

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "🚀 Deploying Toronto Street View Counter to server..."

# Check if we're on a supported system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✅ Linux detected"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "✅ macOS detected"
else
    echo "⚠️  Unsupported OS: $OSTYPE"
    echo "This script is designed for Linux/macOS servers"
    echo "Continuing anyway..."
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
echo "🔍 Detected Python version: $python_version"

# Simple version comparison (major.minor format)
major_version=$(echo $python_version | cut -d. -f1)
minor_version=$(echo $python_version | cut -d. -f2)

if [[ "$major_version" -gt 3 ]] || [[ "$major_version" -eq 3 && "$minor_version" -ge 8 ]]; then
    echo "✅ Python $python_version detected (3.8+ required)"
else
    echo "❌ Python 3.8+ required, found $python_version"
    echo "Please upgrade Python and try again"
    exit 1
fi

# Check for required commands
echo "🔍 Checking required commands..."
if ! command_exists python3; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

if ! command_exists pip; then
    echo "❌ pip not found. Please install pip"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Install the package in development mode
echo "🔧 Installing package..."
pip install -e .

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/raw data/derived outputs logs

# Set up Google Cloud (if gcloud is available)
if command -v gcloud &> /dev/null; then
    echo "☁️  Google Cloud CLI detected"
    echo "To set up Google Cloud authentication, run:"
    echo "  ./setup_google_cloud.sh"
else
    echo "⚠️  Google Cloud CLI not found"
    echo "Install with: https://cloud.google.com/sdk/docs/install"
    echo "Or manually set up authentication"
fi

# Create environment file template
echo "📝 Creating environment template..."
cat > .env.template << EOF
# Copy this to .env and fill in your values
GOOGLE_MAPS_API_KEY=your_api_key_here
GOOGLE_CLOUD_PROJECT=your_project_id_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# Optional: Customize paths
DATA_DIR=data
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
EOF

# Create a simple start script
echo "📜 Creating start script..."
cat > start_crawl.sh << 'EOF'
#!/bin/bash

# Start script for Toronto Street View crawling
set -e

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activate virtual environment
source venv/bin/activate

# Check if API key is set
if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo "❌ GOOGLE_MAPS_API_KEY not set"
    echo "Please set it in .env file or export it"
    exit 1
fi

echo "🚀 Starting Toronto Street View crawl..."

# Download data if not present
if [ ! -f "data/raw/toronto_boundary.geojson" ]; then
    echo "📥 Downloading data sources..."
    toronto-streetview-count download-boundary
fi

# Prepare sample points if not present
if [ ! -f "data/derived/sample_points.parquet" ]; then
    echo "🛣️  Preparing sample points..."
    toronto-streetview-count prepare-points --spacing 50
fi

# Start crawling (customize parameters as needed)
echo "🔍 Starting Street View crawl..."
toronto-streetview-count crawl \
    --radius 30 \
    --qps 10 \
    --batch-size 1000 \
    --data-dir data

echo "✅ Crawl complete!"
EOF

chmod +x start_crawl.sh

# Create systemd service file (for Linux servers)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🔧 Creating systemd service file..."
    cat > toronto-streetview.service << EOF
[Unit]
Description=Toronto Street View Counter
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python -m toronto_streetview_count.cli crawl --radius 30 --qps 10 --batch-size 1000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo "📋 To install as a system service:"
    echo "  sudo cp toronto-streetview.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable toronto-streetview"
    echo "  sudo systemctl start toronto-streetview"
fi

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > monitor.sh << 'EOF'
#!/bin/bash

# Monitoring script for Toronto Street View counter
echo "📊 Toronto Street View Counter Status"
echo "====================================="

# Check if virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not active"
    echo "Run: source venv/bin/activate"
    exit 1
fi

# Check database status
if [ -f "data/streetview.db" ]; then
    echo "✅ Database exists"
    # Get basic stats
    sqlite3 data/streetview.db "SELECT COUNT(*) as total_points, COUNT(CASE WHEN status='queried' THEN 1 END) as queried, COUNT(CASE WHEN status='pending' THEN 1 END) as pending FROM sample_points;" 2>/dev/null || echo "⚠️  Could not query database"
else
    echo "❌ Database not found"
fi

# Check data files
echo ""
echo "📁 Data Files:"
[ -f "data/raw/toronto_boundary.geojson" ] && echo "✅ Boundary data" || echo "❌ Boundary data"
[ -f "data/raw/toronto_centreline.csv" ] && echo "✅ TCL roads" || echo "❌ TCL roads"
[ -f "data/derived/sample_points.parquet" ] && echo "✅ Sample points" || echo "❌ Sample points"

# Check outputs
echo ""
echo "📊 Outputs:"
[ -f "outputs/sampling_summary.json" ] && echo "✅ Sampling summary" || echo "❌ Sampling summary"
[ -f "outputs/toronto_pano_ids.parquet" ] && echo "✅ Panorama IDs" || echo "❌ Panorama IDs"

# Check environment
echo ""
echo "🔑 Environment:"
[ -n "$GOOGLE_MAPS_API_KEY" ] && echo "✅ API key set" || echo "❌ API key not set"
[ -n "$GOOGLE_CLOUD_PROJECT" ] && echo "✅ Project ID set" || echo "❌ Project ID not set"
EOF

chmod +x monitor.sh

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Copy .env.template to .env and fill in your API key"
echo "2. Set up Google Cloud authentication (if needed)"
echo "3. Run: ./start_crawl.sh"
echo "4. Monitor with: ./monitor.sh"
echo ""
echo "📚 For more information, see README.md and QUICKSTART.md"
echo ""
echo "🚀 Ready to count Toronto Street View panoramas!"
