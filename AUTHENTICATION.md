# Google Cloud Authentication Guide

This guide explains how to set up authentication for the Toronto Street View Panorama Counter using Google Cloud's recommended authentication methods.

## 🔐 **Why Google Cloud Authentication?**

Instead of using API keys, this project now uses **Application Default Credentials (ADC)** which provides:

- **Better Security**: No hardcoded API keys in code or environment
- **Automatic Token Management**: Handles token refresh automatically
- **IAM Integration**: Uses Google Cloud IAM for fine-grained access control
- **Best Practices**: Follows Google's recommended authentication patterns
- **Audit Trail**: All API calls are logged with your Google Cloud account

## 🚀 **Quick Setup**

### Option 1: Automated Setup (Recommended)

```bash
# Run the automated setup script
./setup_google_cloud.sh
```

This script will:
- Check if Google Cloud CLI is installed
- Guide you through authentication
- Enable required APIs
- Configure IAM permissions
- Set up Application Default Credentials
- Verify the complete setup

### Option 2: Manual Setup

#### 1. Install Google Cloud CLI

**macOS (using Homebrew):**
```bash
brew install google-cloud-sdk
```

**Linux:**
```bash
# Download and install from Google Cloud
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows:**
Download from [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

#### 2. Authenticate with Google Cloud

```bash
# Login with your Google account
gcloud auth login

# Set up Application Default Credentials
gcloud auth application-default login
```

#### 3. Set Your Project ID

```bash
# List available projects
gcloud projects list

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Or set environment variable
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

## 🔧 **Detailed Setup Steps**

### Step 1: Enable Required APIs

Your Google Cloud project needs these APIs enabled:

```bash
# Enable Maps Platform APIs
gcloud services enable maps-backend.googleapis.com
gcloud services enable street-view-static.googleapis.com
gcloud services enable maps.googleapis.com

# Enable other required services
gcloud services enable geocoding-backend.googleapis.com
```

### Step 2: Configure IAM Permissions

Ensure your account has the necessary permissions:

```bash
# Check your current permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID

# Grant yourself the necessary roles (if you're an admin)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/mapsplatform.user"
```

### Step 3: Verify Authentication

Test that authentication is working:

```bash
# Check current credentials
gcloud auth list

# Check application default credentials
gcloud auth application-default print-access-token

# Test with our project
python test_installation.py
```

## 🏗️ **Authentication Methods**

### Method 1: User Credentials (Recommended for Development)

```bash
# Login with your Google account
gcloud auth login

# Set up ADC for local development
gcloud auth application-default login
```

**Best for:** Local development, testing, personal projects

### Method 2: Service Account (Recommended for Production)

```bash
# Create a service account
gcloud iam service-accounts create streetview-counter \
    --description="Service account for Street View counting" \
    --display-name="Street View Counter"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:streetview-counter@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/mapsplatform.user"

# Create and download key
gcloud iam service-accounts keys create ~/streetview-key.json \
    --iam-account=streetview-counter@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/streetview-key.json"
```

**Best for:** Production deployments, CI/CD pipelines, server environments

### Method 3: Workload Identity Federation

For advanced use cases with external identity providers:

```bash
# Configure Workload Identity Federation
gcloud iam workload-identity-pools create "external-pool" \
    --location="global" \
    --display-name="External Identity Pool"

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "external-provider" \
    --workload-identity-pool="external-pool" \
    --issuer-uri="https://your-provider.com" \
    --location="global"
```

## 🔍 **Troubleshooting**

### Common Issues

**1. "No Google Cloud credentials found"**
```bash
# Solution: Set up ADC
gcloud auth application-default login
```

**2. "Access denied" or "Permission denied"**
```bash
# Check your IAM permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID

# Ensure you have the necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/mapsplatform.user"
```

**3. "Project not found"**
```bash
# List available projects
gcloud projects list

# Set correct project
gcloud config set project YOUR_PROJECT_ID
```

**4. "APIs not enabled"**
```bash
# Enable required APIs
gcloud services enable maps-backend.googleapis.com
gcloud services enable street-view-static.googleapis.com
```

### Debug Commands

```bash
# Check current configuration
gcloud config list

# Check authentication status
gcloud auth list

# Check ADC status
gcloud auth application-default print-access-token

# Check project settings
gcloud config get-value project

# Check enabled APIs
gcloud services list --enabled
```

## 🔒 **Security Best Practices**

### 1. **Never Commit Credentials**
```bash
# Add to .gitignore
echo "*.json" >> .gitignore
echo "credentials/" >> .gitignore
```

### 2. **Use Least Privilege**
Only grant the minimum permissions necessary:
- `roles/mapsplatform.user` for basic Maps Platform access
- Avoid `roles/owner` or `roles/editor` unless necessary

### 3. **Rotate Credentials Regularly**
```bash
# For service accounts, create new keys periodically
gcloud iam service-accounts keys create new-key.json \
    --iam-account=streetview-counter@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 4. **Monitor Usage**
```bash
# Check API usage
gcloud services list --enabled --filter="name:maps*"

# Monitor costs in Google Cloud Console
# https://console.cloud.google.com/billing
```

## 📚 **Additional Resources**

- [Google Cloud Authentication Overview](https://cloud.google.com/docs/authentication)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Maps Platform Documentation](https://developers.google.com/maps/documentation)
- [IAM Best Practices](https://cloud.google.com/iam/docs/best-practices)

## ✅ **Verification Checklist**

- [ ] Google Cloud CLI installed
- [ ] Authenticated with `gcloud auth login`
- [ ] ADC configured with `gcloud auth application-default login`
- [ ] Project ID set correctly
- [ ] Required APIs enabled
- [ ] IAM permissions configured
- [ ] Test authentication with `python test_installation.py`
- [ ] Run `toronto-streetview-count status` successfully

Once all items are checked, you're ready to use the Toronto Street View Panorama Counter! 🎉
