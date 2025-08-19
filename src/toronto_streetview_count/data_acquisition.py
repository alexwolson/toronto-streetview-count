"""Data acquisition for Toronto road networks and boundaries."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import httpx
import overpy
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import BBox, TORONTO_BBOX

logger = logging.getLogger(__name__)
console = Console()


class DataAcquisition:
    """Handles downloading and processing of Toronto road network data."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.derived_dir = self.data_dir / "derived"
        
        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)
    
    async def download_toronto_boundary(self) -> Path:
        """Download Toronto city boundary from Open Data Portal."""
        output_path = self.raw_dir / "toronto_boundary.geojson"
        
        if output_path.exists():
            console.print(f"✓ Toronto boundary already exists at {output_path}")
            return output_path
        
        console.print("Downloading Toronto boundary...")
        
        try:
            # Use toronto-open-data package to find and download boundary
            from toronto_open_data import TorontoOpenData
            tod = TorontoOpenData()
            
            # Search for municipal boundary datasets
            boundary_results = tod.search_datasets('municipal boundary')
            
            # Look for the main city boundary
            city_boundary = None
            for _, row in boundary_results.iterrows():
                if 'municipal' in row['title'].lower() and 'boundary' in row['title'].lower():
                    city_boundary = row
                    break
            
            if city_boundary is None:
                # Fallback: create a simple boundary from our bbox
                console.print("⚠️  Could not find city boundary, creating from bbox...")
                from .models import TORONTO_BBOX
                from shapely.geometry import Polygon
                import geopandas as gpd
                
                # Create a simple rectangular boundary
                coords = [
                    (TORONTO_BBOX.min_lon, TORONTO_BBOX.min_lat),
                    (TORONTO_BBOX.max_lon, TORONTO_BBOX.min_lat),
                    (TORONTO_BBOX.max_lon, TORONTO_BBOX.max_lat),
                    (TORONTO_BBOX.min_lon, TORONTO_BBOX.max_lat),
                    (TORONTO_BBOX.min_lon, TORONTO_BBOX.min_lat)
                ]
                
                polygon = Polygon(coords)
                gdf = gpd.GeoDataFrame([{'geometry': polygon}], crs='EPSG:4326')
                gdf.to_file(output_path, driver='GeoJSON')
                
                console.print(f"✓ Created boundary from bbox at {output_path}")
                return output_path
            
            # Download the boundary dataset
            console.print(f"Found boundary dataset: {city_boundary['title']}")
            dataset_id = city_boundary['id']
            
            # Get available resources
            resources = tod.get_datastore_resources(dataset_id)
            if len(resources) > 0:
                # Download the first available resource
                resource_url = resources.iloc[0]['url']
                
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    response = await client.get(resource_url)
                    response.raise_for_status()
                    
                    with open(output_path, 'w') as f:
                        f.write(response.text)
                
                console.print(f"✓ Downloaded Toronto boundary to {output_path}")
                return output_path
            else:
                raise Exception("No resources found for boundary dataset")
                
        except Exception as e:
            console.print(f"❌ Error downloading boundary: {e}")
            # Fallback to bbox method
            console.print("Falling back to bbox boundary...")
            from .models import TORONTO_BBOX
            from shapely.geometry import Polygon
            import geopandas as gpd
            
            coords = [
                (TORONTO_BBOX.min_lon, TORONTO_BBOX.min_lat),
                (TORONTO_BBOX.max_lon, TORONTO_BBOX.min_lat),
                (TORONTO_BBOX.max_lon, TORONTO_BBOX.max_lat),
                (TORONTO_BBOX.min_lon, TORONTO_BBOX.max_lat),
                (TORONTO_BBOX.min_lon, TORONTO_BBOX.min_lat)
            ]
            
            polygon = Polygon(coords)
            gdf = gpd.GeoDataFrame([{'geometry': polygon}], crs='EPSG:4326')
            gdf.to_file(output_path, driver='GeoJSON')
            
            console.print(f"✓ Created boundary from bbox at {output_path}")
            return output_path
    
    async def download_toronto_centreline(self) -> Path:
        """Download Toronto Centreline (TCL) road network from Open Data Portal."""
        output_path = self.raw_dir / "toronto_centreline.csv"
        
        if output_path.exists():
            console.print(f"✓ Toronto Centreline already exists at {output_path}")
            return output_path
        
        console.print("Downloading Toronto Centreline...")
        
        try:
            # Use toronto-open-data package to find and download TCL
            from toronto_open_data import TorontoOpenData
            tod = TorontoOpenData()
            
            # Search for TCL dataset
            tcl_results = tod.search_datasets('Toronto Centreline')
            tcl_dataset = None
            
            for _, row in tcl_results.iterrows():
                if 'Toronto Centreline' in row['title']:
                    tcl_dataset = row
                    break
            
            if tcl_dataset is None:
                raise Exception("Could not find Toronto Centreline dataset")
            
            console.print(f"Found TCL dataset: {tcl_dataset['title']}")
            dataset_id = tcl_dataset['id']
            
            # Get available resources
            resources = tod.get_datastore_resources(dataset_id)
            if len(resources) == 0:
                raise Exception("No resources found for TCL dataset")
            
            # Look for GeoJSON format first, then fallback to others
            resource_url = None
            for _, resource in resources.iterrows():
                if 'geojson' in resource.get('format', '').lower():
                    resource_url = resource['url']
                    break
            
            if resource_url is None:
                # Use the first available resource
                resource_url = resources.iloc[0]['url']
            
            console.print(f"Downloading from: {resource_url}")
            
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(resource_url)
                response.raise_for_status()
                
                with open(output_path, 'w') as f:
                    f.write(response.text)
            
            console.print(f"✓ Downloaded Toronto Centreline to {output_path}")
            
            # Convert CSV to GeoJSON if needed
            if output_path.suffix == '.csv':
                geojson_path = output_path.with_suffix('.geojson')
                console.print(f"Converting CSV to GeoJSON: {geojson_path}")
                
                # Read CSV and convert to GeoJSON
                import pandas as pd
                import json
                
                df = pd.read_csv(output_path)
                
                # Convert geometry column from string to actual GeoJSON
                features = []
                for _, row in df.iterrows():
                    try:
                        if pd.notna(row['geometry']):
                            geom_data = json.loads(row['geometry'])
                            feature = {
                                'type': 'Feature',
                                'properties': {
                                    'centreline_id': row['CENTRELINE_ID'],
                                    'linear_name': row['LINEAR_NAME_FULL'],
                                    'feature_code': row['FEATURE_CODE_DESC'],
                                    'jurisdiction': row['JURISDICTION']
                                },
                                'geometry': geom_data
                            }
                            features.append(feature)
                    except Exception as e:
                        console.print(f"⚠️  Skipping row with invalid geometry: {e}")
                        continue
                
                # Create GeoJSON file
                geojson_data = {
                    'type': 'FeatureCollection',
                    'features': features
                }
                
                with open(geojson_path, 'w') as f:
                    json.dump(geojson_data, f)
                
                console.print(f"✓ Converted to GeoJSON: {geojson_path}")
                return geojson_path
            
            return output_path
            
        except Exception as e:
            console.print(f"❌ Error downloading TCL: {e}")
            raise
    
    async def download_osm_roads(self, bbox: Optional[BBox] = None) -> Path:
        """Download OpenStreetMap road data for Toronto area."""
        if bbox is None:
            bbox = TORONTO_BBOX
        
        output_path = self.raw_dir / "toronto_osm_roads.geojson"
        
        if output_path.exists():
            console.print(f"✓ OpenStreetMap roads already exist at {output_path}")
            return output_path
        
        console.print("Downloading OpenStreetMap road data...")
        
        # Overpass query for roads in Toronto area (more targeted)
        overpass_query = f"""
        [out:json][timeout:60];
        (
          way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service|unclassified"]({bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        # Use overpy to query Overpass API
        api = overpy.Overpass()
        result = api.query(overpass_query)
        
        # Convert to GeoDataFrame
        roads_data = []
        for way in result.ways:
            # Get coordinates for the way
            coords = [(float(node.lat), float(node.lon)) for node in way.get_nodes()]
            
            if len(coords) >= 2:  # Need at least 2 points for a line
                roads_data.append({
                    'osm_id': way.id,
                    'highway': way.tags.get('highway', 'unknown'),
                    'name': way.tags.get('name', ''),
                    'geometry': coords
                })
        
        # Create GeoDataFrame and save
        if roads_data:
            # Convert coordinates to proper LineString geometries
            from shapely.geometry import LineString
            
            processed_roads = []
            for road in roads_data:
                if len(road['geometry']) >= 2:
                    # Create LineString from coordinates
                    line_geometry = LineString(road['geometry'])
                    
                    processed_roads.append({
                        'osm_id': road['osm_id'],
                        'highway': road['highway'],
                        'name': road['name'],
                        'geometry': line_geometry
                    })
            
            if processed_roads:
                gdf = gpd.GeoDataFrame(processed_roads, crs='EPSG:4326')
                gdf.to_file(output_path, driver='GeoJSON')
                console.print(f"✓ Downloaded {len(processed_roads)} OSM roads to {output_path}")
            else:
                console.print("⚠ No valid road geometries found")
        else:
            console.print("⚠ No OSM roads found")
        
        return output_path
    
    async def download_all_data(self) -> dict:
        """Download all required data sources."""
        console.print("🚀 Starting data acquisition...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Downloading data...", total=3)
            
            # Download boundary
            boundary_path = await self.download_toronto_boundary()
            progress.advance(task)
            
            # Download TCL
            tcl_path = await self.download_toronto_centreline()
            progress.advance(task)
            
            # Download OSM (optional)
            osm_path = None
            try:
                osm_path = await self.download_osm_roads()
                console.print("✓ OSM roads downloaded successfully")
            except Exception as e:
                console.print(f"⚠️  OSM download failed (continuing without it): {e}")
            progress.advance(task)
        
        console.print("✅ Data acquisition complete!")
        
        return {
            'boundary': boundary_path,
            'centreline': tcl_path,
            'osm_roads': osm_path
        }
    
    def validate_data(self) -> bool:
        """Validate that all required data files exist and are readable."""
        required_files = [
            self.raw_dir / "toronto_boundary.geojson",
            self.raw_dir / "toronto_centreline.csv"
        ]
        
        # OSM roads are optional
        optional_files = [
            self.raw_dir / "toronto_osm_roads.geojson"
        ]
        
        # Validate required files
        for file_path in required_files:
            if not file_path.exists():
                console.print(f"❌ Missing required file: {file_path}")
                return False
            
            try:
                gpd.read_file(file_path)
                console.print(f"✓ Validated {file_path}")
            except Exception as e:
                console.print(f"❌ Invalid file {file_path}: {e}")
                return False
        
        # Validate optional files if they exist
        for file_path in optional_files:
            if file_path.exists():
                try:
                    gpd.read_file(file_path)
                    console.print(f"✓ Validated optional file {file_path}")
                except Exception as e:
                    console.print(f"⚠️  Invalid optional file {file_path}: {e}")
            else:
                console.print(f"ℹ️  Optional file not present: {file_path}")
        
        return True


async def main():
    """Test data acquisition."""
    data_acq = DataAcquisition("data")
    await data_acq.download_all_data()
    data_acq.validate_data()


if __name__ == "__main__":
    asyncio.run(main())
