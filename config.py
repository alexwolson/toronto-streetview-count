"""Configuration file for Toronto Street View Counter."""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DERIVED_DATA_DIR = DATA_DIR / "derived"
OUTPUT_DIR = DATA_DIR / "outputs"

# Data source URLs
TORONTO_BOUNDARY_URL = "https://opendata.arcgis.com/datasets/7beabe78f1174c12a46e291dd3a1f307_0.geojson"
TORONTO_CENTRELINE_URL = "https://opendata.arcgis.com/datasets/4f6e6215d4e34d6b97b1d8f6e8e4b6f2_0.geojson"

# Toronto bounding box (WGS84)
TORONTO_BBOX = {
    "min_lon": -79.6393,  # West
    "min_lat": 43.5810,   # South
    "max_lon": -79.1156,  # East
    "max_lat": 43.8555,   # North
}

# Sampling parameters
DEFAULT_SAMPLING_SPACING = 10.0  # meters
MIN_SAMPLING_SPACING = 5.0       # meters
MAX_SAMPLING_SPACING = 50.0      # meters

# API parameters
DEFAULT_SEARCH_RADIUS = 30       # meters
MIN_SEARCH_RADIUS = 1            # meters
MAX_SEARCH_RADIUS = 50000        # meters

DEFAULT_QPS = 10                 # queries per second
MIN_QPS = 1                      # queries per second
MAX_QPS = 100                    # queries per second

# Processing parameters
DEFAULT_BATCH_SIZE = 100         # points per batch
MIN_BATCH_SIZE = 10              # points per batch
MAX_BATCH_SIZE = 1000            # points per batch

# Coordinate reference systems
SOURCE_CRS = "EPSG:4326"        # WGS84 (source data)
PROCESSING_CRS = "EPSG:3161"    # NAD83 / Ontario (for accurate distance calculations)

# File paths
TORONTO_BOUNDARY_FILE = RAW_DATA_DIR / "toronto_boundary.geojson"
TORONTO_CENTRELINE_FILE = RAW_DATA_DIR / "toronto_centreline.geojson"
SAMPLE_POINTS_FILE = DERIVED_DATA_DIR / "sample_points.parquet"
DATABASE_FILE = DATA_DIR / "streetview.db"

# Output files
PANORAMA_OUTPUT_FILE = OUTPUT_DIR / "toronto_pano_ids.parquet"
SAMPLE_POINTS_OUTPUT_FILE = OUTPUT_DIR / "sample_points_with_results.parquet"
FINAL_SUMMARY_FILE = OUTPUT_DIR / "final_summary.json"
SAMPLING_SUMMARY_FILE = OUTPUT_DIR / "sampling_summary.json"

# Road type mappings
TCL_ROAD_TYPES = ['ROAD', 'HIGHWAY', 'EXPRESSWAY', 'COLLECTOR', 'LOCAL']
 

# Validation parameters
BOUNDARY_BUFFER_METERS = 50      # meters to buffer boundary when clipping roads
SIMILARITY_THRESHOLD_METERS = 5  # meters for road deduplication

# Rate limiting and retry parameters
API_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 60         # default retry delay for rate limiting

# Database settings
DATABASE_TIMEOUT = 30.0
DATABASE_CHECK_SAME_THREAD = False

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Progress display
PROGRESS_REFRESH_RATE = 0.1      # seconds between progress updates
