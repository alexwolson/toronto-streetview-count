#!/usr/bin/env python3
"""
Example workflow for Toronto Street View Panorama Counter.

This script demonstrates the complete pipeline from data acquisition
to final panorama counting.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from toronto_streetview_count.data_acquisition import DataAcquisition
from toronto_streetview_count.road_processing import RoadProcessor
from toronto_streetview_count.streetview_client import StreetViewClient
from rich.console import Console

console = Console()


async def run_complete_workflow():
    """Run the complete workflow from start to finish."""
    console.print("🚀 Toronto Street View Panorama Counter - Complete Workflow")
    console.print("=" * 60)
    
    # Check for Google Cloud project
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        console.print("⚠️  No Google Cloud project ID set, will use default from credentials")
        console.print("To set: export GOOGLE_CLOUD_PROJECT='your-project-id'")
    
    # Check for Google Cloud authentication
    try:
        import google.auth
        google.auth.default()
        console.print("✅ Google Cloud authentication configured")
    except Exception as e:
        console.print("❌ Google Cloud authentication not configured!")
        console.print("Please run: gcloud auth application-default login")
        console.print("Or set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        return
    
    data_dir = Path("data")
    
    # Step 1: Download data sources
    console.print("\n📥 Step 1: Downloading data sources...")
    try:
        data_acq = DataAcquisition(data_dir)
        await data_acq.download_all_data()
        
        if not data_acq.validate_data():
            console.print("❌ Data validation failed!")
            return
            
        console.print("✅ Data sources downloaded successfully!")
    except Exception as e:
        console.print(f"❌ Failed to download data: {e}")
        return
    
    # Step 2: Process roads and generate sample points
    console.print("\n🛣️  Step 2: Processing road networks...")
    try:
        processor = RoadProcessor(data_dir)
        sample_points, output_path = processor.process_roads(spacing_m=10.0)
        console.print(f"✅ Generated {len(sample_points)} sample points!")
    except Exception as e:
        console.print(f"❌ Failed to process roads: {e}")
        return
    
    # Step 3: Initialize Street View client
    console.print("\n🔍 Step 3: Initializing Street View client...")
    try:
        client = StreetViewClient(str(data_dir / "streetview.db"), qps=5, project_id=project_id)
        await client.initialize_database()
        await client.insert_sample_points(sample_points)
        console.print("✅ Street View client initialized!")
    except Exception as e:
        console.print(f"❌ Failed to initialize client: {e}")
        return
    
    # Step 4: Process a small subset for testing
    console.print("\n🧪 Step 4: Testing with a small subset...")
    try:
        # Process only first 100 points for testing
        test_points = sample_points[:100]
        console.print(f"Testing with {len(test_points)} points...")
        
        # Update sample points to only include test subset
        await client.insert_sample_points(test_points)
        
        # Process test points
        stats = await client.process_all_points(radius_m=30, batch_size=25)
        client.print_stats()
        
        console.print("✅ Subset test completed!")
    except Exception as e:
        console.print(f"❌ Subset test failed: {e}")
        return
    
    # Step 5: Export results
    console.print("\n📊 Step 5: Exporting results...")
    try:
        output_dir = data_dir / "outputs"
        await client.export_results(str(output_dir))
        console.print("✅ Results exported!")
    except Exception as e:
        console.print(f"❌ Failed to export results: {e}")
        return
    
    console.print("\n🎉 Workflow completed successfully!")
    console.print("\n📖 Next steps:")
    console.print("1. Review results in data/outputs/")
    console.print("2. Run full crawl: toronto-streetview-count crawl")
    console.print("3. Get final count: toronto-streetview-count count")


def main():
    """Main entry point."""
    try:
        asyncio.run(run_complete_workflow())
    except KeyboardInterrupt:
        console.print("\n⚠️  Workflow interrupted by user")
    except Exception as e:
        console.print(f"\n❌ Workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
