"""Data acquisition for Toronto road networks and boundaries."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import httpx
from rich.console import Console
from rich.traceback import install as rich_traceback_install
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import BBox, TORONTO_BBOX

logger = logging.getLogger(__name__)
console = Console()
rich_traceback_install(show_locals=False, width=120)


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
            
            # Search for municipal boundary datasets - try multiple search terms
            city_boundary = None
            search_terms = ['municipal boundary', 'city boundary', 'regional boundary', 'boundary']
            
            for search_term in search_terms:
                console.print(f"Searching for: {search_term}")
                try:
                    boundary_results = tod.search_datasets(search_term)
                    console.print(f"Search results type: {type(boundary_results)}")
                    console.print(f"Search results: {boundary_results}")
                    
                    if boundary_results is not None and not boundary_results.empty:
                        for _, row in boundary_results.iterrows():
                            try:
                                title_lower = str(row.get('title', '')).lower()
                                if 'boundary' in title_lower and ('municipal' in title_lower or 'city' in title_lower or 'regional' in title_lower):
                                    city_boundary = row
                                    console.print(f"Found boundary dataset: {city_boundary['title']}")
                                    break
                            except Exception as row_error:
                                console.print(f"⚠️  Error processing row: {row_error}")
                                continue
                        
                        if city_boundary is not None:
                            break
                except Exception as search_error:
                    console.print(f"⚠️  Error searching for '{search_term}': {search_error}")
                    continue
            
            if city_boundary is None:
                # Fallback: create a simple boundary from our bbox
                console.print("⚠️  Could not find city boundary, creating from bbox...")
                from .models import TORONTO_BBOX
                from shapely.geometry import Polygon
                
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
            console.print(f"Dataset object: {city_boundary}")
            console.print(f"Dataset columns: {list(city_boundary.index)}")
            
            try:
                dataset_id = city_boundary['id']
                console.print(f"Dataset ID: {dataset_id}")
            except Exception as id_error:
                console.print(f"⚠️  Error getting dataset ID: {id_error}")
                console.print("Falling back to bbox boundary...")
                # Continue to fallback below
                raise Exception(f"Could not get dataset ID: {id_error}")
            
            # Try to get resources - handle different resource types
            try:
                console.print(f"Getting resources for dataset ID: {dataset_id}")
                
                # Try to get resources from the dataset object first
                if 'resources' in city_boundary and city_boundary['resources']:
                    console.print("Found resources in dataset object")
                    resources_data = city_boundary['resources']
                    console.print(f"Resources data: {resources_data}")
                    
                    # Look for a usable resource URL
                    resource_url = None
                    for resource in resources_data:
                        if isinstance(resource, dict) and 'url' in resource:
                            format_type = str(resource.get('format', '')).lower()
                            if 'geojson' in format_type or 'json' in format_type or 'shp' in format_type:
                                resource_url = resource['url']
                                console.print(f"Using resource: {resource.get('name', 'Unknown')} ({format_type})")
                                break
                    
                    if resource_url:
                        console.print(f"Downloading from: {resource_url}")
                        
                        # If this is a shapefile zip, download as binary and convert to GeoJSON
                        if resource_url.lower().endswith('.zip') or (format_type and ('shp' in format_type or 'shapefile' in format_type)):
                            zip_path = self.raw_dir / "toronto_boundary.zip"
                            extract_dir = self.raw_dir / "toronto_boundary_extract"
                            extract_dir.mkdir(parents=True, exist_ok=True)
                            
                            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                                resp = await client.get(resource_url)
                                resp.raise_for_status()
                                zip_path.write_bytes(resp.content)
                            
                            # Extract and load shapefile
                            import zipfile
                            with zipfile.ZipFile(zip_path, 'r') as zf:
                                zf.extractall(extract_dir)
                            
                            # Find a .shp file
                            shp_files = list(extract_dir.rglob('*.shp'))
                            if not shp_files:
                                raise Exception("No .shp file found in the downloaded archive")
                            
                            shp_path = shp_files[0]
                            import geopandas as gpd
                            gdf_boundary = gpd.read_file(shp_path)
                            # Ensure WGS84
                            if gdf_boundary.crs is not None:
                                gdf_boundary = gdf_boundary.to_crs(epsg=4326)
                            
                            gdf_boundary.to_file(output_path, driver='GeoJSON')
                            console.print(f"✓ Downloaded and converted boundary to {output_path}")
                            
                            # Cleanup
                            try:
                                zip_path.unlink(missing_ok=True)  # type: ignore[arg-type]
                            except Exception:
                                pass
                            try:
                                import shutil
                                shutil.rmtree(extract_dir, ignore_errors=True)
                            except Exception:
                                pass
                            
                            return output_path
                        else:
                            # Assume text-based (GeoJSON/JSON)
                            async with httpx.AsyncClient(follow_redirects=True) as client:
                                response = await client.get(resource_url)
                                response.raise_for_status()
                                
                                with open(output_path, 'w') as f:
                                    f.write(response.text)
                            
                            console.print(f"✓ Downloaded Toronto boundary to {output_path}")
                            return output_path
                
                # Fallback to get_datastore_resources method
                console.print("Trying get_datastore_resources method...")
                resources = tod.get_datastore_resources(dataset_id)
                console.print(f"Resources type: {type(resources)}")
                console.print(f"Resources: {resources}")
                
                if resources is None or resources.empty:
                    console.print("No resources found via get_datastore_resources")
                    raise Exception("No resources found for boundary dataset")
                
                console.print(f"Found {len(resources)} resources")
                console.print(f"Resources columns: {list(resources.columns)}")
                if len(resources) > 0:
                    console.print(f"First resource: {resources.iloc[0].to_dict()}")
                
                if len(resources) > 0:
                    # Look for GeoJSON or Shapefile resources first
                    resource_url = None
                    for _, resource in resources.iterrows():
                        try:
                            format_type = str(resource.get('format', '')).lower()
                            if 'geojson' in format_type or 'json' in format_type:
                                resource_url = resource['url']
                                console.print(f"Using GeoJSON resource: {resource.get('name', 'Unknown')}")
                                break
                            elif 'shp' in format_type or 'shapefile' in format_type:
                                resource_url = resource['url']
                                console.print(f"Using Shapefile resource: {resource.get('name', 'Unknown')}")
                                break
                        except Exception as format_error:
                            console.print(f"⚠️  Error processing resource format: {format_error}")
                            continue
                    
                    # Fallback to first available resource
                    if not resource_url and len(resources) > 0 and not resources.empty:
                        resource_url = resources.iloc[0]['url']
                        console.print(f"Using fallback resource: {resources.iloc[0]['name']}")
                    
                    if resource_url is not None:
                        console.print(f"Downloading from: {resource_url}")
                        # Detect shapefile zip and convert
                        fmt_hint = (format_type if 'format_type' in locals() else None)
                        if resource_url.lower().endswith('.zip') or (fmt_hint and ('shp' in fmt_hint or 'shapefile' in fmt_hint)):
                            zip_path = self.raw_dir / "toronto_boundary.zip"
                            extract_dir = self.raw_dir / "toronto_boundary_extract"
                            extract_dir.mkdir(parents=True, exist_ok=True)
                            
                            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                                resp = await client.get(resource_url)
                                resp.raise_for_status()
                                zip_path.write_bytes(resp.content)
                            
                            import zipfile
                            with zipfile.ZipFile(zip_path, 'r') as zf:
                                zf.extractall(extract_dir)
                            
                            shp_files = list(extract_dir.rglob('*.shp'))
                            if not shp_files:
                                raise Exception("No .shp file found in the downloaded archive")
                            shp_path = shp_files[0]
                            import geopandas as gpd
                            gdf_boundary = gpd.read_file(shp_path)
                            if gdf_boundary.crs is not None:
                                gdf_boundary = gdf_boundary.to_crs(epsg=4326)
                            gdf_boundary.to_file(output_path, driver='GeoJSON')
                            console.print(f"✓ Downloaded and converted boundary to {output_path}")
                            try:
                                zip_path.unlink(missing_ok=True)  # type: ignore[arg-type]
                            except Exception:
                                pass
                            try:
                                import shutil
                                shutil.rmtree(extract_dir, ignore_errors=True)
                            except Exception:
                                pass
                            return output_path
                        else:
                            async with httpx.AsyncClient(follow_redirects=True) as client:
                                response = await client.get(resource_url)
                                response.raise_for_status()
                                with open(output_path, 'w') as f:
                                    f.write(response.text)
                            console.print(f"✓ Downloaded Toronto boundary to {output_path}")
                            return output_path
                    else:
                        raise Exception("No usable resources found")
                else:
                    raise Exception("No resources found for boundary dataset")
                    
            except Exception as resource_error:
                console.print(f"⚠️  Error getting resources: {resource_error}")
                console.print("Falling back to bbox boundary...")
                # Continue to fallback below
                
        except Exception as e:
            console.print(f"❌ Error downloading boundary: {e}")
            # Fallback to bbox method
            console.print("Falling back to bbox boundary...")
            from .models import TORONTO_BBOX
            from shapely.geometry import Polygon
            
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
    
    # OSM download removed for TCL-only workflow
    
    async def download_all_data(self) -> dict:
        """Download all required data sources."""
        console.print("🚀 Starting data acquisition...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Downloading data...", total=2)
            
            # Download boundary
            boundary_path = await self.download_toronto_boundary()
            progress.advance(task)
            
            # Download TCL
            tcl_path = await self.download_toronto_centreline()
            progress.advance(task)
            
            # OSM removed for TCL-only workflow
        
        console.print("✅ Data acquisition complete!")
        
        return {
            'boundary': boundary_path,
            'centreline': tcl_path
        }
    
    def validate_data(self) -> bool:
        """Validate that all required data files exist and are readable."""
        required_files = {
            'boundary': self.raw_dir / "toronto_boundary.geojson",
            'tcl_csv': self.raw_dir / "toronto_centreline.csv",
            'tcl_geojson': self.raw_dir / "toronto_centreline.geojson",
        }
        
        # Boundary (GeoJSON required)
        boundary_path = required_files['boundary']
        if not boundary_path.exists():
            console.print(f"❌ Missing required file: {boundary_path}")
            return False
        try:
            gpd.read_file(boundary_path)
            console.print(f"✓ Validated {boundary_path}")
        except Exception as e:
            console.print(f"❌ Invalid file {boundary_path}: {e}")
            return False

        # TCL (either CSV or GeoJSON must exist and be readable)
        import pandas as pd
        tcl_csv = required_files['tcl_csv']
        tcl_geojson = required_files['tcl_geojson']
        if tcl_geojson.exists():
            try:
                gpd.read_file(tcl_geojson)
                console.print(f"✓ Validated {tcl_geojson}")
            except Exception as e:
                console.print(f"❌ Invalid file {tcl_geojson}: {e}")
                return False
        elif tcl_csv.exists():
            try:
                df = pd.read_csv(tcl_csv, nrows=5)
                console.print(f"✓ Validated {tcl_csv}")
            except Exception as e:
                console.print(f"❌ Invalid file {tcl_csv}: {e}")
                return False
        else:
            console.print(f"❌ Missing required TCL file: {tcl_geojson} or {tcl_csv}")
            return False

        # OSM validation removed for TCL-only workflow
        
        return True


async def main():
    """Test data acquisition."""
    data_acq = DataAcquisition("data")
    await data_acq.download_all_data()
    data_acq.validate_data()


if __name__ == "__main__":
    asyncio.run(main())
