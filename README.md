# 🗺️ Toronto Street View Panorama Counter

Count the total number of Google Street View panoramas available within the City of Toronto boundary, producing a deduplicated set of panorama IDs with coordinates and dates.

## 🎯 **Project Overview**

This project systematically samples Toronto's road network to discover all available Street View panoramas via the Google Street View Image Metadata API. It produces:

- **Complete Coverage**: Samples all roadways in Toronto with configurable density
- **Deduplicated Results**: Identifies unique panoramas using spatial analysis
- **Rich Metadata**: Coordinates, dates, and panorama IDs for each location
- **Reproducible Process**: Automated data acquisition and processing pipeline

## 🚀 **Quick Start**

### Prerequisites
- **Python 3.11+**
- **Google Cloud CLI** installed and authenticated
- **Google Cloud project** with Maps Platform APIs enabled

### 1. Install Dependencies
```bash
# Clone the repository
git clone https://github.com/alexwolson/toronto-streetview-count.git
cd toronto-streetview-count

# Install dependencies
pip install -e .
```

### 2. Set Up Google Cloud Authentication
```bash
# Run the automated setup script (recommended)
./setup_google_cloud.sh

# This will:
# - Enable required APIs
# - Configure IAM permissions
# - Create and restrict API keys
# - Set up environment variables
```

### 3. Quick Test Run
```bash
# Test with a small subset first
toronto-streetview-count subset --spacing 5 --radius 25 --qps 5

# This processes downtown Toronto in minutes
```

### 4. Full Pipeline
```bash
# Download geographic data
toronto-streetview-count download-boundary

# Generate sample points
toronto-streetview-count prepare-points --spacing 10

# Crawl Street View (start small)
toronto-streetview-count crawl --radius 30 --qps 10

# Get results
toronto-streetview-count count
```

## 🔧 **Configuration**

### Key Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--spacing` | 10m | Distance between sample points |
| `--radius` | 30m | Search radius for panoramas |
| `--qps` | 10 | API requests per second |
| `--batch-size` | 100 | Points processed per batch |

### Expected Results
- **Sample Points**: ~1M-2M with 10m spacing
- **Processing Time**: 2-8 hours depending on parameters
- **Unique Panoramas**: Expected 50K-200K+ in Toronto
- **Storage**: ~1-5GB for complete dataset

## 🏗️ **Architecture**

### Data Sources
- **Toronto Open Data Portal**: Official city boundary and Toronto Centreline (TCL) road network
- **Google Street View API**: Panorama metadata (coordinates, dates, IDs)

### Processing Pipeline
1. **Data Acquisition**: Download boundary and TCL data
2. **Road Processing**: Merge networks, clip to boundary, densify to sample points
3. **API Crawling**: Query Street View API for each sample point
4. **Deduplication**: Remove duplicate panoramas using spatial analysis
5. **Results**: Export to Parquet with SQLite progress tracking

## 🚀 **Server Deployment**

For production runs, deploy to a server with the included automation:

### Quick Deployment
```bash
# Clone and deploy
git clone https://github.com/alexwolson/toronto-streetview-count.git
cd toronto-streetview-count
chmod +x deploy_server.sh
./deploy_server.sh
```

### Docker Deployment
```bash
# Using Docker Compose
docker-compose up -d

# Or build manually
docker build -t toronto-streetview-counter .
docker run -d --name toronto-crawler toronto-streetview-counter
```

See [SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md) for detailed deployment instructions.

## 📊 **Output Format**

Results are saved in multiple formats:

- **SQLite Database**: Progress tracking and checkpointing
- **Parquet Files**: Efficient storage of final results
- **Logs**: Detailed processing logs with timestamps
- **Statistics**: Summary reports and progress metrics

## 🔐 **Authentication & Security**

This project uses Google Cloud's recommended authentication:

- **Application Default Credentials (ADC)**: Secure, token-based authentication
- **API Key Restrictions**: Limited to Street View services only
- **IAM Integration**: Fine-grained permission control
- **No Hardcoded Keys**: Environment-based configuration

## 📁 **Project Structure**

```
toronto-streetview-count/
├── src/toronto_streetview_count/     # Main package
│   ├── cli.py                        # Command-line interface
│   ├── data_acquisition.py           # Data download and processing
│   ├── road_processing.py            # Road network processing
│   ├── streetview_client.py          # Google Street View API client
│   └── models.py                     # Data models and types
├── data/                             # Geographic data storage
├── outputs/                          # Results and exports
├── setup_google_cloud.sh            # Google Cloud setup automation
├── deploy_server.sh                  # Server deployment script
├── Dockerfile                        # Container configuration
└── docker-compose.yml                # Docker orchestration
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **City of Toronto Open Data Portal** for official boundary and road network data
 
- **Google Maps Platform** for Street View API access

## 📞 **Support**

For issues and questions:
- Check the [PLAN.md](PLAN.md) for technical details
- Review [SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md) for deployment help
- Open an issue on GitHub for bugs or feature requests
