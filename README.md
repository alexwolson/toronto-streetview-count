# Toronto Street View Panorama Counter

A comprehensive tool to count all Google Street View panoramas within the City of Toronto boundary using road network sampling and the Google Street View Image Metadata API.

## 🎯 Goal

**Count the total number of Google Street View panoramas available by API within the City of Toronto boundary.** The output is a deduplicated set of panorama IDs (with coordinates and dates) and a reproducible process.

## 🚀 Features

- **Boundary-driven**: Uses official City of Toronto boundary polygon
- **Road-centric sampling**: Densifies Toronto road centerlines and samples points every 5-10m
- **Hybrid data sources**: Combines Toronto Centreline (TCL) with OpenStreetMap for comprehensive coverage
- **Metadata queries**: Calls Street View Image Metadata API around each sample point
- **Deduplication**: Collects unique panorama IDs with coordinates and dates
- **Persistence**: Stores results in SQLite for resumability and audit
- **Rate limiting**: Respects API limits while maximizing throughput
- **Resume capability**: Can continue from where it left off

## 📋 Prerequisites

- Python 3.11+
- Google Cloud CLI installed and authenticated
- Google Cloud project with Maps Platform APIs enabled
- Internet connection for data downloads

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd toronto-streetview-count
   ```

2. **Install dependencies:**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -e .
   ```

3. **Set up Google Cloud authentication:**
   ```bash
   # Option 1: Use the automated setup script (recommended)
   ./setup_google_cloud.sh
   
   # Option 2: Manual setup
   # Install Google Cloud CLI if not already installed
   # https://cloud.google.com/sdk/docs/install
   
   # Authenticate with your Google account
   gcloud auth application-default login
   
   # Optionally set your project ID
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   ```

## 🗺️ Data Sources

- **City of Toronto Boundary**: Official city limits from Toronto Open Data Portal
- **Toronto Centreline (TCL)**: Official road network from Toronto Open Data Portal
- **OpenStreetMap**: Supplementary road data for comprehensive coverage
- **Google Street View Image Metadata API**: Free metadata queries for panorama discovery

## 📖 Usage

The tool provides a command-line interface with several commands:

### 1. Download Data Sources
```bash
toronto-streetview-count download-boundary
```
Downloads Toronto boundary, TCL, and OSM datasets to `data/raw/`.

### 2. Prepare Sample Points
```bash
toronto-streetview-count prepare-points --spacing 10
```
Processes road networks and generates sample points every 10 meters.

### 3. Crawl Street View Metadata
```bash
toronto-streetview-count crawl --radius 30 --qps 10
```
Queries the Street View API for all sample points with rate limiting.

### 4. Count Results
```bash
toronto-streetview-count count
```
Displays final count and exports results to `outputs/`.

### 5. Subset Testing
```bash
toronto-streetview-count subset --spacing 5 --radius 25
```
Runs the pipeline on a small area for validation.

### 6. Check Status
```bash
toronto-streetview-count status
```
Shows current project status and data availability.

## 🔧 Configuration Options

### Sampling Parameters
- `--spacing`: Distance between sample points (default: 10m)
- `--radius`: Search radius for metadata API (default: 30m)

### API Settings
- `--qps`: Queries per second for rate limiting (default: 10)
- `--batch-size`: Points processed per batch (default: 100)

### Data Directories
- `--data-dir`: Directory for data storage (default: `data`)
- `--output-dir`: Directory for output files (default: `outputs`)

## 📊 Output Files

- `toronto_pano_ids.parquet`: Unique panoramas with coordinates and dates
- `sample_points_with_results.parquet`: All sample points with API responses
- `final_summary.json`: Processing statistics and final count
- `sampling_summary.json`: Sample point generation statistics

## 🖥️ Server Deployment

For production deployment on your server:

### Quick Deployment
```bash
git clone https://github.com/yourusername/toronto-streetview-count.git
cd toronto-streetview-count
./deploy_server.sh
```

### Docker Deployment
```bash
# Set environment variables
export GOOGLE_MAPS_API_KEY="your_api_key"
export GOOGLE_CLOUD_PROJECT="your_project_id"

# Start services
docker-compose up -d
```

### Manual Installation
```bash
pip install -r requirements.txt
pip install -e .
```

📖 **See [SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md) for detailed server setup instructions.**

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Road Processing│    │ Street View API │
│                 │    │                 │    │                 │
│ • Toronto TCL   │───▶│ • Merge Networks│───▶│ • Metadata      │
│ • OSM Roads     │    │ • Clip Boundary │    │ • Rate Limiting │
│ • City Boundary │    │ • Densify Roads │    │ • Persistence   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Sample Points   │    │   Results       │
                       │                 │    │                 │
                       │ • Road-aligned  │    │ • Unique Count  │
                       │ • Configurable  │    │ • Coordinates   │
                       │ • Parquet       │    │ • Statistics    │
                       └─────────────────┘    └─────────────────┘
```

## 🔍 How It Works

1. **Data Acquisition**: Downloads official Toronto data and supplements with OSM
2. **Road Processing**: Merges road networks, clips to city boundary, densifies into sample points
3. **API Queries**: Samples each point with Street View Metadata API using configurable radius
4. **Deduplication**: Identifies unique panoramas from overlapping API responses
5. **Persistence**: Stores all data in SQLite for resumability and analysis
6. **Export**: Outputs final count and detailed results in multiple formats

## 📈 Performance

- **Sample Points**: ~1M-2M points with 5-10m spacing
- **API Requests**: Free metadata queries (no billing impact)
- **Rate Limiting**: Configurable QPS (default: 10 requests/second)
- **Processing Time**: Depends on sample density and API rate limits
- **Resume Capability**: Can restart from any point in the pipeline

## 🧪 Testing

Run subset tests on small areas before full city processing:

```bash
# Test downtown Toronto area
toronto-streetview-count subset --bbox "-79.4,43.64,-79.38,43.66" --spacing 5

# Test with custom parameters
toronto-streetview-count subset --spacing 3 --radius 20 --qps 5
```

## 🚨 Important Notes

- **API Quotas**: Respect Google's daily request limits
- **Rate Limiting**: Built-in throttling to be a good API citizen
- **Data Quality**: Toronto has excellent OSM coverage for comprehensive results
- **Resume Capability**: Long runs can be interrupted and resumed
- **Free API**: Metadata requests don't count against billing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- City of Toronto Open Data Portal for official boundary and road data
- OpenStreetMap contributors for comprehensive road coverage
- Google Maps Platform for free Street View metadata API

## 📞 Support

For questions or issues, please open a GitHub issue or contact the maintainers.
