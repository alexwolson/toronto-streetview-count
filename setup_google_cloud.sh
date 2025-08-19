#!/bin/bash

# Toronto Street View Panorama Counter - Google Cloud Setup Script
# This script sets up all necessary Google Cloud APIs, IAM permissions, and authentication

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if user is authenticated
check_auth() {
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        return 1
    fi
    return 0
}

# Function to get current project
get_current_project() {
    gcloud config get-value project 2>/dev/null || echo ""
}

# Function to list available projects
list_projects() {
    echo "Available projects:"
    gcloud projects list --format="table(projectId,name,projectNumber)" | head -20
    echo ""
}

# Function to enable required APIs
enable_apis() {
    local project_id="$1"
    
    print_status "Enabling required Google Cloud APIs for project: $project_id"
    
    # Try to enable Maps Platform APIs
    print_status "Attempting to enable Maps Platform APIs..."
    
    local api_enabled_count=0
    local total_apis=5
    
    # Maps Platform APIs
    if gcloud services enable maps-backend.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ maps-backend.googleapis.com enabled"
        ((api_enabled_count++))
    else
        print_warning "⚠ maps-backend.googleapis.com not available or permission denied"
    fi
    
    if gcloud services enable street-view-image-backend.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ street-view-image-backend.googleapis.com enabled"
        ((api_enabled_count++))
    else
        print_warning "⚠ street-view-image-backend.googleapis.com not available or permission denied"
    fi
    
    if gcloud services enable maps-embed-backend.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ maps-embed-backend.googleapis.com enabled"
        ((api_enabled_count++))
    else
        print_warning "⚠ maps-embed-backend.googleapis.com not available or permission denied"
    fi
    
    # Geocoding and other services
    print_status "Attempting to enable additional services..."
    
    if gcloud services enable geocoding-backend.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ geocoding-backend.googleapis.com enabled"
        ((api_enabled_count++))
    else
        print_warning "⚠ geocoding-backend.googleapis.com not available or permission denied"
    fi
    
    if gcloud services enable places-backend.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ places-backend.googleapis.com enabled"
        ((api_enabled_count++))
    else
        print_warning "⚠ places-backend.googleapis.com not available or permission denied"
    fi
    
    # Enable billing API (required for some services)
    if gcloud services enable cloudbilling.googleapis.com --project="$project_id" --quiet 2>/dev/null; then
        print_success "✓ cloudbilling.googleapis.com enabled"
    else
        print_warning "⚠ cloudbilling.googleapis.com not available or permission denied"
    fi
    
    if [ $api_enabled_count -eq 0 ]; then
        print_error "❌ No Maps Platform APIs could be enabled!"
        echo ""
        echo "This could be due to:"
        echo "1. Project restrictions or organization policies"
        echo "2. Maps Platform APIs not being available in this project"
        echo "3. Insufficient permissions"
        echo ""
        echo "Alternative solutions:"
        echo "1. Use a different Google Cloud project"
        echo "2. Enable APIs through Google Cloud Console:"
        echo "   https://console.cloud.google.com/apis/library?project=$project_id"
        echo "3. Contact your Google Cloud administrator"
        echo ""
        echo "For now, we'll continue with basic authentication setup..."
        return 1
    elif [ $api_enabled_count -lt $total_apis ]; then
        print_warning "⚠ Only $api_enabled_count out of $total_apis Maps Platform APIs were enabled"
        echo "Some features may not work properly"
    else
        print_success "All required APIs enabled successfully!"
    fi
    
    return 0
}

# Function to configure IAM permissions
configure_iam() {
    local project_id="$1"
    local user_email="$2"
    
    print_status "Configuring IAM permissions for user: $user_email"
    
    # Try to grant Maps Platform user role (may not be available)
    print_status "Attempting to grant Maps Platform user role..."
    if gcloud projects add-iam-policy-binding "$project_id" \
        --member="user:$user_email" \
        --role="roles/mapsplatform.user" \
        --quiet 2>/dev/null; then
        print_success "✓ Maps Platform user role granted"
    else
        print_warning "⚠ Maps Platform user role not available, trying alternative roles..."
        
        # Try alternative roles that might work
        if gcloud projects add-iam-policy-binding "$project_id" \
            --member="user:$user_email" \
            --role="roles/serviceusage.serviceUsageViewer" \
            --quiet 2>/dev/null; then
            print_success "✓ Service Usage Viewer role granted"
        else
            print_warning "⚠ Service Usage Viewer role not available"
        fi
    fi
    
    # Grant basic viewer role for project access
    print_status "Granting project viewer role..."
    if gcloud projects add-iam-policy-binding "$project_id" \
        --member="user:$user_email" \
        --role="roles/viewer" \
        --quiet 2>/dev/null; then
        print_success "✓ Project viewer role granted"
    else
        print_warning "⚠ Project viewer role not available"
    fi
    
    print_success "IAM permissions configured successfully!"
}

# Function to create service account (optional)
create_service_account() {
    local project_id="$1"
    local sa_name="streetview-counter"
    local sa_email="$sa_name@$project_id.iam.gserviceaccount.com"
    
    print_status "Creating service account for production use..."
    
    # Check if service account already exists
    if gcloud iam service-accounts describe "$sa_email" --project="$project_id" >/dev/null 2>&1; then
        print_warning "Service account $sa_email already exists"
        return 0
    fi
    
    # Create service account
    gcloud iam service-accounts create "$sa_name" \
        --description="Service account for Toronto Street View Panorama Counter" \
        --display-name="Street View Counter" \
        --project="$project_id" \
        --quiet
    
    # Grant necessary permissions (try Maps Platform role first, fall back to alternatives)
    if gcloud projects add-iam-policy-binding "$project_id" \
        --member="serviceAccount:$sa_email" \
        --role="roles/mapsplatform.user" \
        --quiet 2>/dev/null; then
        print_success "✓ Maps Platform user role granted to service account"
    else
        print_warning "⚠ Maps Platform user role not available for service account"
        
        # Grant alternative roles that should work
        if gcloud projects add-iam-policy-binding "$project_id" \
            --member="serviceAccount:$sa_email" \
            --role="roles/serviceusage.serviceUsageViewer" \
            --quiet 2>/dev/null; then
            print_success "✓ Service Usage Viewer role granted to service account"
        fi
        
        if gcloud projects add-iam-policy-binding "$project_id" \
            --member="serviceAccount:$sa_email" \
            --role="roles/viewer" \
            --quiet 2>/dev/null; then
            print_success "✓ Project viewer role granted to service account"
        fi
    fi
    
    print_success "Service account created: $sa_email"
    print_status "To use this service account, download a key file:"
    echo "  gcloud iam service-accounts keys create ~/streetview-key.json \\"
    echo "    --iam-account=$sa_email"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=\"\$HOME/streetview-key.json\""
}

# Function to create and configure API key
create_api_key() {
    local project_id="$1"
    
    print_status "Creating and configuring Street View API key..."
    
    # Check if we already have a suitable API key
    local existing_key=$(gcloud services api-keys list --project="$project_id" --format="value(name)" --filter="displayName:Toronto Street View Counter" 2>/dev/null | head -1)
    
    if [ -n "$existing_key" ]; then
        local key_id=$(basename "$existing_key")
        print_warning "API key already exists: $key_id"
        
        # Get the key string
        local key_string=$(gcloud services api-keys get-key-string "$key_id" --project="$project_id" 2>/dev/null)
        if [ -n "$key_string" ]; then
            print_success "✓ API key retrieved: ${key_string:0:20}..."
            
            # Export as environment variable
            export GOOGLE_MAPS_API_KEY="$key_string"
            echo "export GOOGLE_MAPS_API_KEY=\"$key_string\"" >> ~/.bashrc 2>/dev/null || true
            echo "export GOOGLE_MAPS_API_KEY=\"$key_string\"" >> ~/.zshrc 2>/dev/null || true
            
            print_success "✓ API key exported to environment"
        fi
        
        return 0
    fi
    
    # Create new API key
    print_status "Creating new API key..."
    local create_result
    create_result=$(gcloud services api-keys create --project="$project_id" --display-name="Toronto Street View Counter" --format="value(name)" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$create_result" ]; then
        local key_id=$(basename "$create_result")
        print_success "✓ API key created: $key_id"
        
        # Restrict the API key to Street View services
        print_status "Restricting API key to Street View services..."
        if gcloud services api-keys update "$key_id" --project="$project_id" \
            --api-target=service=street-view-image-backend.googleapis.com \
            --api-target=service=maps-backend.googleapis.com \
            --api-target=service=geocoding-backend.googleapis.com \
            --quiet 2>/dev/null; then
            print_success "✓ API key restrictions applied"
        else
            print_warning "⚠ Could not apply API key restrictions"
        fi
        
        # Get the key string
        local key_string=$(gcloud services api-keys get-key-string "$key_id" --project="$project_id" 2>/dev/null)
        if [ -n "$key_string" ]; then
            print_success "✓ API key string retrieved: ${key_string:0:20}..."
            
            # Export as environment variable
            export GOOGLE_MAPS_API_KEY="$key_string"
            echo "export GOOGLE_MAPS_API_KEY=\"$key_string\"" >> ~/.bashrc 2>/dev/null || true
            echo "export GOOGLE_MAPS_API_KEY=\"$key_string\"" >> ~/.zshrc 2>/dev/null || true
            
            print_success "✓ API key exported to environment"
        else
            print_warning "⚠ Could not retrieve API key string"
        fi
    else
        print_warning "⚠ Could not create API key"
    fi
}

# Function to set up Application Default Credentials
setup_adc() {
    print_status "Setting up Application Default Credentials..."
    
    if gcloud auth application-default print-access-token >/dev/null 2>&1; then
        print_warning "Application Default Credentials already configured"
        return 0
    fi
    
    # Set up ADC
    gcloud auth application-default login --no-launch-browser
    
    print_success "Application Default Credentials configured successfully!"
}

# Function to verify setup
verify_setup() {
    local project_id="$1"
    
    print_status "Verifying Google Cloud setup..."
    
    # Check if APIs are enabled
    local required_apis=(
        "maps-backend.googleapis.com"
        "street-view-image-backend.googleapis.com"
        "maps-embed-backend.googleapis.com"
        "geocoding-backend.googleapis.com"
    )
    
    local enabled_apis=0
    local total_apis=${#required_apis[@]}
    
    for api in "${required_apis[@]}"; do
        if gcloud services list --enabled --filter="name:$api" --project="$project_id" | grep -q "$api"; then
            print_success "✓ $api is enabled"
            ((enabled_apis++))
        else
            print_warning "⚠ $api is not enabled"
        fi
    done
    
    # Check authentication
    if check_auth; then
        print_success "✓ User authentication is active"
    else
        print_error "✗ User authentication is not active"
        return 1
    fi
    
    # Check ADC
    if gcloud auth application-default print-access-token >/dev/null 2>&1; then
        print_success "✓ Application Default Credentials are configured"
    else
        print_error "✗ Application Default Credentials are not configured"
        return 1
    fi
    
    if [ $enabled_apis -eq 0 ]; then
        print_warning "⚠ No Maps Platform APIs are enabled"
        echo "The project may not have access to Maps Platform services"
        echo "You may need to use a different project or contact your administrator"
        return 1
    elif [ $enabled_apis -lt $total_apis ]; then
        print_warning "⚠ Partial API availability: $enabled_apis/$total_apis APIs enabled"
        echo "Some features may not work properly"
        return 0
    else
        print_success "✓ All required APIs are enabled"
        return 0
    fi
}

# Function to display next steps
show_next_steps() {
    local project_id="$1"
    
    echo ""
    echo "🎉 Google Cloud setup completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Test the setup:"
    echo "   python test_installation.py"
    echo ""
    echo "2. Check project status:"
    echo "   toronto-streetview-count status"
    echo ""
    echo "3. Start using the tool:"
    echo "   toronto-streetview-count download-boundary"
    echo ""
    echo "🔧 Useful commands:"
    echo "   gcloud config list                    # View current configuration"
    echo "   gcloud auth list                      # View active accounts"
    echo "   gcloud services list --enabled        # View enabled APIs"
    echo ""
    echo "📚 Documentation:"
    echo "   See AUTHENTICATION.md for detailed information"
    echo "   See README.md for usage instructions"
    echo ""
    echo "🌐 Google Cloud Console:"
    echo "   https://console.cloud.google.com/home/dashboard?project=$project_id"
}

# Main setup function
main() {
    echo "🚀 Toronto Street View Panorama Counter - Google Cloud Setup"
    echo "=================================================================="
    echo ""
    
    # Check if gcloud CLI is installed
    if ! command_exists gcloud; then
        print_error "Google Cloud CLI (gcloud) is not installed!"
        echo "Please install it first:"
        echo "  macOS: brew install google-cloud-sdk"
        echo "  Linux: curl https://sdk.cloud.google.com | bash"
        echo "  Windows: Download from https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    print_success "Google Cloud CLI is installed"
    
    # Check if user is authenticated
    if ! check_auth; then
        print_warning "You are not authenticated with Google Cloud"
        echo "Please run: gcloud auth login"
        exit 1
    fi
    
    # Get current user email
    local user_email
    user_email=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
    print_success "Authenticated as: $user_email"
    
    # Get or set project
    local project_id
    project_id=$(get_current_project)
    
    if [ -z "$project_id" ]; then
        print_warning "No project is currently set"
        list_projects
        
        echo "Please select a project ID from the list above or enter one manually:"
        read -p "Project ID: " project_id
        
        if [ -z "$project_id" ]; then
            print_error "No project ID provided. Exiting."
            exit 1
        fi
        
        # Set the project
        gcloud config set project "$project_id"
        print_success "Project set to: $project_id"
    else
        print_success "Using project: $project_id"
    fi
    
    # Confirm project selection
    echo ""
    echo "Current configuration:"
    echo "  Project ID: $project_id"
    echo "  User: $user_email"
    echo ""
    read -p "Continue with this configuration? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Setup cancelled by user"
        exit 0
    fi
    
    # Enable required APIs
    enable_apis "$project_id"
    
    # Configure IAM permissions
    configure_iam "$project_id" "$user_email"
    
    # Create service account (optional)
    echo ""
    read -p "Create a service account for production use? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_service_account "$project_id"
    fi
    
    # Set up Application Default Credentials
    setup_adc
    
    # Create and configure API key
    create_api_key "$project_id"
    
    # Verify the setup
    if verify_setup "$project_id"; then
        show_next_steps "$project_id"
    else
        print_error "Setup verification failed. Please check the errors above."
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --verify       Only verify the current setup"
        echo "  --project ID   Use specific project ID"
        echo ""
        echo "This script sets up Google Cloud APIs, IAM permissions, and"
        echo "authentication for the Toronto Street View Panorama Counter."
        exit 0
        ;;
    --verify)
        project_id=$(get_current_project)
        if [ -z "$project_id" ]; then
            print_error "No project is set. Please run the full setup first."
            exit 1
        fi
        verify_setup "$project_id"
        exit $?
        ;;
    --project)
        if [ -z "$2" ]; then
            print_error "Project ID is required with --project option"
            exit 1
        fi
        gcloud config set project "$2"
        print_success "Project set to: $2"
        main
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
