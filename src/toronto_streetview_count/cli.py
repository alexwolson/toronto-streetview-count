"""Command-line interface for Toronto Street View Counter."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import click
import pandas as pd
from rich.console import Console
from rich.panel import Panel

from .data_acquisition import DataAcquisition
from .models import TORONTO_BBOX
from .road_processing import RoadProcessor
from .streetview_client import StreetViewClient

console = Console()


@click.group()
@click.version_option()
def cli():
    """Toronto Street View Panorama Counter
    
    Count all Google Street View panoramas within the City of Toronto boundary
    using road network sampling and the Google Street View Image Metadata API.
    """
    pass


@cli.command()
@click.option(
    "--data-dir",
    default="data",
    help="Directory to store downloaded data",
    type=click.Path(file_okay=False, dir_okay=True)
)
def download_boundary(data_dir):
    """Download Toronto boundary, TCL, and OSM datasets."""
    console.print(Panel.fit("🌍 Downloading Toronto Data Sources", style="blue"))
    
    async def run_download():
        data_acq = DataAcquisition(data_dir)
        await data_acq.download_all_data()
        
        # Validate downloaded data
        if data_acq.validate_data():
            console.print("✅ All data sources downloaded and validated successfully!")
        else:
            console.print("❌ Data validation failed!")
            raise click.Abort()
    
    asyncio.run(run_download())


@cli.command()
@click.option(
    "--data-dir",
    default="data",
    help="Directory containing downloaded data",
    type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--spacing",
    default=10.0,
    help="Distance between sample points in meters",
    type=float
)
@click.option(
    "--output-dir",
    default="outputs",
    help="Directory to store output files",
    type=click.Path(file_okay=False, dir_okay=True)
)
def prepare_points(data_dir, spacing, output_dir):
    """Build densified sample points within Toronto boundary."""
    console.print(Panel.fit("🛣️  Processing Road Networks", style="green"))
    
    # Validate spacing
    if spacing <= 0:
        raise click.BadParameter("Spacing must be > 0 meters")
    if spacing > 50:
        console.print("⚠ Warning: spacing >50m may undercount panoramas", style="yellow")
    
    # Process roads
    processor = RoadProcessor(data_dir)
    sample_points, output_path = processor.process_roads(spacing_m=spacing)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save sample points summary
    summary = {
        "total_points": len(sample_points),
        "spacing_meters": spacing,
        "bounding_box": {
            "min_lat": min(p.lat for p in sample_points),
            "max_lat": max(p.lat for p in sample_points),
            "min_lon": min(p.lon for p in sample_points),
            "max_lon": max(p.lon for p in sample_points)
        },
        "road_types": {}
    }
    
    # Count road types
    for point in sample_points:
        road_type = point.road_type or "unknown"
        summary["road_types"][road_type] = summary["road_types"].get(road_type, 0) + 1
    
    # Save summary
    import json
    summary_path = output_path / "sampling_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    console.print(f"✅ Generated {len(sample_points)} sample points")
    console.print(f"📊 Summary saved to {summary_path}")
    console.print(f"📁 Sample points saved to {output_path}")


@cli.command()
@click.option(
    "--project-id",
    envvar="GOOGLE_CLOUD_PROJECT",
    help="Google Cloud project ID (or set GOOGLE_CLOUD_PROJECT)",
)
@click.option(
    "--data-dir",
    default="data",
    help="Directory containing data and database",
    type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--radius",
    default=30,
    help="Search radius in meters for metadata endpoint",
    type=int
)
@click.option(
    "--qps",
    default=10,
    help="Queries per second (rate limiting)",
    type=int
)
@click.option(
    "--batch-size",
    default=100,
    help="Number of points to process in each batch",
    type=int
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from where we left off",
)
def crawl(project_id, data_dir, radius, qps, batch_size, resume):
    """Query metadata for all sample points with rate limiting."""
    console.print(Panel.fit("🕷️  Crawling Street View Metadata", style="red"))
    
    # Validate parameters
    if radius <= 0 or radius > 50000:
        raise click.BadParameter("Radius must be between 1 and 50000 meters")
    if qps <= 0 or qps > 100:
        raise click.BadParameter("QPS must be between 1 and 100")
    
    async def run_crawl():
        # Initialize client
        db_path = Path(data_dir) / "streetview.db"
        import os
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        client = StreetViewClient(str(db_path), qps=qps, project_id=project_id, api_key=api_key)
        
        # Initialize database
        await client.initialize_database()
        
        if not resume:
            # Load sample points from Parquet file
            sample_points_path = Path(data_dir) / "derived" / "sample_points.parquet"
            if not sample_points_path.exists():
                console.print("❌ Sample points not found. Run 'prepare-points' first.")
                raise click.Abort()
            
            # Load and insert sample points
            df = pd.read_parquet(sample_points_path)
            from .models import SamplePoint
            
            sample_points = []
            for _, row in df.iterrows():
                sample_points.append(SamplePoint(
                    id=row['id'],
                    lat=row['lat'],
                    lon=row['lon'],
                    road_id=row.get('road_id'),
                    road_type=row.get('road_type')
                ))
            
            await client.insert_sample_points(sample_points)
            console.print(f"✓ Loaded {len(sample_points)} sample points")
        else:
            console.print("🔄 Resuming from previous state...")
        
        # Process all points
        stats = await client.process_all_points(radius_m=radius, batch_size=batch_size)
        
        # Print statistics
        client.print_stats()
        
        # Export results
        output_dir = Path(data_dir) / "outputs"
        await client.export_results(str(output_dir))
        
        console.print("✅ Crawling complete!")
    
    asyncio.run(run_crawl())


@cli.command()
@click.option(
    "--data-dir",
    default="data",
    help="Directory containing data and database",
    type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--output-dir",
    default="outputs",
    help="Directory to store output files",
    type=click.Path(file_okay=False, dir_okay=True)
)
def count(data_dir, output_dir):
    """Emit the deduplicated count and write output artifacts."""
    console.print(Panel.fit("📊 Counting Unique Panoramas", style="cyan"))
    
    async def run_count():
        # Connect to database
        db_path = Path(data_dir) / "streetview.db"
        if not db_path.exists():
            console.print("❌ Database not found. Run 'crawl' first.")
            raise click.Abort()
        
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            # Get panorama count
            cursor = await db.execute("SELECT COUNT(*) FROM panoramas")
            panorama_count = (await cursor.fetchone())[0]
            
            # Get sample point statistics
            cursor = await db.execute("SELECT COUNT(*) FROM sample_points")
            total_points = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM sample_points WHERE status = 'queried'")
            queried_points = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM sample_points WHERE status = 'failed'")
            failed_points = (await cursor.fetchone())[0]
            
            # Get road type distribution
            cursor = await db.execute("""
                SELECT road_type, COUNT(*) as count 
                FROM sample_points 
                GROUP BY road_type 
                ORDER BY count DESC
            """)
            road_type_stats = await cursor.fetchall()
        
        # Display results
        console.print(f"🎯 **Final Results**")
        console.print(f"📸 Unique Panoramas Found: **{panorama_count:,}**")
        console.print(f"📍 Total Sample Points: {total_points:,}")
        console.print(f"✅ Successfully Queried: {queried_points:,}")
        console.print(f"❌ Failed Queries: {failed_points:,}")
        
        if total_points > 0:
            success_rate = (queried_points / total_points) * 100
            console.print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Road type breakdown
        if road_type_stats:
            console.print(f"\n🛣️  **Road Type Distribution**")
            for road_type, count in road_type_stats:
                road_type_name = road_type or "unknown"
                console.print(f"   {road_type_name}: {count:,} points")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save summary
        summary = {
            "unique_panoramas": panorama_count,
            "total_sample_points": total_points,
            "successfully_queried": queried_points,
            "failed_queries": failed_points,
            "success_rate": (queried_points / total_points * 100) if total_points > 0 else 0,
            "road_type_distribution": {rt: count for rt, count in road_type_stats},
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        import json
        summary_path = output_path / "final_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        console.print(f"\n📁 Summary saved to {summary_path}")
        console.print(f"🎉 **Toronto has {panorama_count:,} unique Street View panoramas!**")
    
    asyncio.run(run_count())


@cli.command()
@click.option(
    "--project-id",
    envvar="GOOGLE_CLOUD_PROJECT",
    help="Google Cloud project ID (or set GOOGLE_CLOUD_PROJECT)",
)
@click.option(
    "--bbox",
    help="Custom bounding box: min_lon,min_lat,max_lon,max_lat",
    type=str
)
@click.option(
    "--spacing",
    default=5.0,
    help="Grid spacing in meters for subset testing",
    type=float
)
@click.option(
    "--radius",
    default=25,
    help="Search radius in meters",
    type=int
)
@click.option(
    "--qps",
    default=5,
    help="Queries per second (rate limiting)",
    type=int
)
def subset(project_id, bbox, spacing, radius, qps):
    """Run the pipeline on a smaller bbox for quick validation."""
    console.print(Panel.fit("🧪 Subset Testing", style="yellow"))
    
    # Parse bounding box
    if bbox:
        try:
            coords = [float(x.strip()) for x in bbox.split(',')]
            if len(coords) != 4:
                raise ValueError("BBox must have 4 coordinates")
            test_bbox = {
                'min_lon': coords[0],
                'min_lat': coords[1],
                'max_lon': coords[2],
                'max_lat': coords[3]
            }
        except ValueError as e:
            raise click.BadParameter(f"Invalid bbox format: {e}")
    else:
        # Use a small subset of downtown Toronto
        test_bbox = {
            'min_lon': -79.4,
            'min_lat': 43.64,
            'max_lon': -79.38,
            'max_lat': 43.66
        }
        console.print(f"Using default test area: {test_bbox}")
    
    # Generate grid points
    from .models import BBox
    
    bbox_obj = BBox(**test_bbox)
    
    # Grid generation for testing using proper geodetic calculations
    import math
    from pyproj import Geod
    
    def generate_test_grid(bbox: BBox, spacing_m: float):
        """Generate a test grid using proper geodetic calculations."""
        # Use WGS84 ellipsoid for accurate distance calculations
        geod = Geod(ellps='WGS84')
        
        # Calculate grid spacing in degrees at the center of the bbox
        center_lat = (bbox.min_lat + bbox.max_lat) / 2.0
        center_lon = (bbox.min_lon + bbox.max_lon) / 2.0
        
        # Calculate the forward azimuth and distance for latitude and longitude steps
        # For latitude: step north/south
        _, _, lat_distance = geod.inv(center_lon, center_lat, center_lon, center_lat + 0.001)
        dlat = spacing_m / (lat_distance * 1000)  # Convert to degrees
        
        # For longitude: step east/west at the center latitude
        _, _, lon_distance = geod.inv(center_lon, center_lat, center_lon + 0.001, center_lat)
        dlon = spacing_m / (lon_distance * 1000)  # Convert to degrees
        
        points = []
        lat = bbox.min_lat
        while lat <= bbox.max_lat:
            lon = bbox.min_lon
            while lon <= bbox.max_lon:
                points.append((lat, lon))
                lon += dlon
            lat += dlat
        
        return points
    
    test_points = generate_test_grid(bbox_obj, spacing)
    console.print(f"Generated {len(test_points)} test points")
    
    async def run_subset_test():
        # Initialize client with test database
        import os
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        client = StreetViewClient("data/subset_test.db", qps=qps, project_id=project_id, api_key=api_key)
        await client.initialize_database()
        
        # Create test sample points
        from .models import SamplePoint
        
        sample_points = []
        for i, (lat, lon) in enumerate(test_points):
            sample_points.append(SamplePoint(
                id=i,
                lat=lat,
                lon=lon,
                road_id=f"test_{i}",
                road_type="test"
            ))
        
        await client.insert_sample_points(sample_points)
        
        # Process points
        stats = await client.process_all_points(radius_m=radius, batch_size=50)
        
        # Print results
        client.print_stats()
        
        # Export results
        await client.export_results("data/subset_outputs")
        
        console.print("✅ Subset test complete!")
    
    asyncio.run(run_subset_test())


@cli.command()
def status():
    """Show current project status and data availability."""
    console.print(Panel.fit("📋 Project Status", style="magenta"))
    
    data_dir = Path("data")
    
    # Check data sources
    console.print("**Data Sources:**")
    
    # Boundary
    boundary_path = data_dir / "raw" / "toronto_boundary.geojson"
    if boundary_path.exists():
        console.print("✅ Toronto boundary")
    else:
        console.print("❌ Toronto boundary")
    
    # TCL
    tcl_path = data_dir / "raw" / "toronto_centreline.geojson"
    if tcl_path.exists():
        console.print("✅ Toronto Centreline (TCL)")
    else:
        console.print("❌ Toronto Centreline (TCL)")
    
    # OSM removed for TCL-only workflow
    
    # Sample points
    sample_path = data_dir / "derived" / "sample_points.parquet"
    if sample_path.exists():
        console.print("✅ Sample points")
    else:
        console.print("❌ Sample points")
    
    # Database
    db_path = data_dir / "streetview.db"
    if db_path.exists():
        console.print("✅ Street View database")
    else:
        console.print("❌ Street View database")
    
    # Outputs
    output_dir = data_dir / "outputs"
    if output_dir.exists():
        console.print("✅ Output files")
    else:
        console.print("❌ Output files")
    
    console.print(f"\n**Next Steps:**")
    if not boundary_path.exists():
        console.print("1. Run 'download-boundary' to get data sources")
    elif not sample_path.exists():
        console.print("2. Run 'prepare-points' to generate sample points")
    elif not db_path.exists():
        console.print("3. Run 'crawl' to query Street View API")
    else:
        console.print("4. Run 'count' to see final results")


if __name__ == "__main__":
    cli()
