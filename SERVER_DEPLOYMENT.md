# 🚀 Server Deployment Guide

This guide will help you deploy the Toronto Street View Counter to your server for production use.

## 📋 Prerequisites

- **Server**: Linux/macOS with Python 3.8+
- **Memory**: Minimum 4GB RAM (8GB+ recommended for large datasets)
- **Storage**: At least 10GB free space
- **Network**: Stable internet connection for API calls

## 🎯 Quick Start (Recommended)

### 1. Clone and Deploy
```bash
# Clone the repository
git clone https://github.com/yourusername/toronto-streetview-count.git
cd toronto-streetview-count

# Run the deployment script
chmod +x deploy_server.sh
./deploy_server.sh
```

### 2. Configure Environment
```bash
# Copy and edit environment file
cp .env.template .env
nano .env

# Fill in your values:
GOOGLE_MAPS_API_KEY=your_actual_api_key_here
GOOGLE_CLOUD_PROJECT=your_project_id_here
```

### 3. Start Crawling
```bash
# Activate environment and start
source venv/bin/activate
./start_crawl.sh
```

## 🐳 Docker Deployment (Alternative)

### 1. Build and Run
```bash
# Build the image
docker build -t toronto-streetview-counter .

# Run with environment variables
docker run -d \
  --name toronto-streetview \
  -e GOOGLE_MAPS_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/outputs:/app/outputs \
  toronto-streetview-counter
```

### 2. Docker Compose (Recommended)
```bash
# Set environment variables
export GOOGLE_MAPS_API_KEY=your_key
export GOOGLE_CLOUD_PROJECT=your_project_id

# Start services
docker-compose up -d

# View logs
docker-compose logs -f toronto-streetview
```

## 🔧 Manual Installation

### 1. System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip gdal-bin libgdal-dev

# CentOS/RHEL
sudo yum install -y python3 python3-pip gdal-devel

# macOS
brew install python3 gdal
```

### 2. Python Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 3. Directory Structure
```bash
mkdir -p data/raw data/derived outputs logs
```

## 📊 Production Configuration

### 1. Environment Variables
```bash
# Required
GOOGLE_MAPS_API_KEY=your_api_key
GOOGLE_CLOUD_PROJECT=your_project_id

# Optional
DATA_DIR=data
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
QPS_LIMIT=10
BATCH_SIZE=1000
```

### 2. Systemd Service (Linux)
```bash
# Copy service file
sudo cp toronto-streetview.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable toronto-streetview
sudo systemctl start toronto-streetview

# Check status
sudo systemctl status toronto-streetview
```

### 3. Monitoring
```bash
# Check status
./monitor.sh

# View logs
tail -f logs/crawl.log

# Database stats
sqlite3 data/streetview.db "SELECT COUNT(*) as total, COUNT(CASE WHEN status='queried' THEN 1 END) as queried FROM sample_points;"
```

## 🔍 Performance Tuning

### 1. Memory Optimization
```bash
# For large datasets, increase Python memory limit
export PYTHONOPTIMIZE=1
export PYTHONUNBUFFERED=1
```

### 2. Rate Limiting
```bash
# Conservative settings for production
toronto-streetview-count crawl \
  --radius 30 \
  --qps 5 \
  --batch-size 500 \
  --data-dir data
```

### 3. Database Optimization
```bash
# SQLite optimizations (already included in code)
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Memory Errors
```bash
# Check available memory
free -h

# Reduce batch size
--batch-size 100
```

#### 2. API Rate Limits
```bash
# Reduce QPS
--qps 2

# Add delays between batches
--batch-delay 1
```

#### 3. Database Locks
```bash
# Check for other processes
lsof data/streetview.db

# Restart service
sudo systemctl restart toronto-streetview
```

### Logs and Debugging
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check system resources
htop
iotop
df -h
```

## 📈 Scaling Considerations

### 1. Multiple Instances
```bash
# Run multiple crawlers on different areas
toronto-streetview-count crawl --bbox "43.6,-79.5,43.8,-79.3" --qps 5
toronto-streetview-count crawl --bbox "43.8,-79.5,44.0,-79.3" --qps 5
```

### 2. Load Balancing
```bash
# Use different API keys for different instances
GOOGLE_MAPS_API_KEY_1=key1
GOOGLE_MAPS_API_KEY_2=key2
```

### 3. Data Partitioning
```bash
# Process data in chunks
toronto-streetview-count crawl --limit 10000 --offset 0
toronto-streetview-count crawl --limit 10000 --offset 10000
```

## 🔐 Security Considerations

### 1. API Key Protection
```bash
# Never commit API keys to git
echo "*.env" >> .gitignore
echo "data/" >> .gitignore
echo "outputs/" >> .gitignore
```

### 2. Network Security
```bash
# Use firewall rules
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw enable
```

### 3. User Permissions
```bash
# Run as non-root user
sudo useradd -m -s /bin/bash toronto-user
sudo chown -R toronto-user:toronto-user /path/to/app
```

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: README.md, QUICKSTART.md
- **Configuration**: Check config.py for all options

## 🎯 Next Steps

1. **Test**: Run with small dataset first
2. **Monitor**: Use monitoring scripts
3. **Scale**: Increase parameters gradually
4. **Optimize**: Tune based on server performance

---

**Happy crawling! 🚀**
