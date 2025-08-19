# Quick Start Guide

Get up and running with the Toronto Street View Panorama Counter in minutes!

## 🚀 Prerequisites

1. **Python 3.11+** installed
2. **Google Cloud CLI** installed and authenticated
3. **Google Cloud project** with Maps Platform APIs enabled
4. **Internet connection** for data downloads

## ⚡ Quick Setup

### 1. Install Dependencies
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Set up Google Cloud Authentication
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

### 3. Test Installation
```bash
python test_installation.py
```

## 🎯 Quick Test Run

Want to test everything quickly? Run this command to process a small area:

```bash
toronto-streetview-count subset --spacing 5 --radius 25 --qps 5
```

This will:
- Generate test points in downtown Toronto
- Query the Street View API for panoramas
- Show results and statistics
- Take only a few minutes to complete

## 📋 Full Workflow

### Step 1: Download Data
```bash
toronto-streetview-count download-boundary
```

### Step 2: Generate Sample Points
```bash
toronto-streetview-count prepare-points --spacing 10
```

### Step 3: Crawl Street View (Start Small)
```bash
# Test with subset first
toronto-streetview-count subset --spacing 5 --radius 25

# Then run full crawl
toronto-streetview-count crawl --radius 30 --qps 10
```

### Step 4: Get Results
```bash
toronto-streetview-count count
```

## 🔧 Common Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--spacing` | 10m | Distance between sample points |
| `--radius` | 30m | Search radius for panoramas |
| `--qps` | 10 | API requests per second |
| `--batch-size` | 100 | Points processed per batch |

## 📊 Expected Results

- **Sample Points**: ~1M-2M with 10m spacing
- **Processing Time**: 2-8 hours depending on parameters
- **Unique Panoramas**: Expected 50K-200K+ in Toronto
- **Storage**: ~1-5GB for complete dataset

## 🚨 Important Notes

- **Free API**: Metadata requests don't cost money
- **Rate Limits**: Respect Google's daily quotas
- **Resume Capability**: Can restart interrupted runs
- **Data Quality**: Toronto has excellent OSM coverage

## 🆘 Troubleshooting

### Common Issues

1. **Import Errors**: Run `python test_installation.py`
2. **Authentication Issues**: Run `gcloud auth application-default login`
3. **Project Issues**: Check `export GOOGLE_CLOUD_PROJECT`
4. **Memory Issues**: Reduce batch size with `--batch-size 50`
5. **Slow Processing**: Reduce QPS with `--qps 5`

### Get Help

- Check project status: `toronto-streetview-count status`
- Review logs in console output
- Check data directory structure

## 🎉 Success!

Once complete, you'll have:
- Complete count of Toronto Street View panoramas
- Detailed coordinates and metadata
- Processing statistics and validation
- Exportable results in multiple formats

Ready to discover how many Street View panoramas Toronto has! 🗺️
