"""Road network processing and sample point generation."""

import logging
from pathlib import Path
from typing import List, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .models import BBox, SamplePoint, TORONTO_BBOX

logger = logging.getLogger(__name__)
console = Console()


class RoadProcessor:
    """Processes road networks and generates sample points."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.derived_dir = self.data_dir / "derived"
    
    def load_boundary(self) -> gpd.GeoDataFrame:
        """Load Toronto boundary polygon."""
        boundary_path = self.raw_dir / "toronto_boundary.geojson"
        boundary = gpd.read_file(boundary_path)
        
        # Ensure we have a single polygon
        if len(boundary) > 1:
            boundary = gpd.GeoDataFrame(
                geometry=[unary_union(boundary.geometry)],
                crs=boundary.crs
            )
        
        # Reproject to a suitable projected CRS for accurate distance operations
        # Use EPSG:3161 (NAD83 / Ontario) which is appropriate for Toronto
        boundary_proj = boundary.to_crs(epsg=3161)
        
        return boundary_proj
    
    def load_tcl_roads(self) -> gpd.GeoDataFrame:
        """Load Toronto Centreline (TCL) road network."""
        tcl_csv_path = self.raw_dir / "toronto_centreline.csv"
        tcl_geojson_path = self.raw_dir / "toronto_centreline.geojson"
        
        # Convert CSV to GeoJSON if needed
        if not tcl_geojson_path.exists() and tcl_csv_path.exists():
            console.print("Converting TCL CSV to GeoJSON...")
            import pandas as pd
            import json
            
            df = pd.read_csv(tcl_csv_path)
            
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
                                'jurisdiction': row['JURISDICTION'],
                                'ROADCLASS': row.get('FEATURE_CODE_DESC', 'UNKNOWN')
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
            
            with open(tcl_geojson_path, 'w') as f:
                json.dump(geojson_data, f)
            
            console.print(f"✓ Converted TCL to GeoJSON: {tcl_geojson_path}")
        
        # Load the GeoJSON file
        tcl = gpd.read_file(tcl_geojson_path)
        
        # Reproject to match boundary
        tcl_proj = tcl.to_crs(epsg=3161)
        
        # Filter to only include road features (TCL uses FEATURE_CODE_DESC)
        road_types = ['Major Arterial', 'Minor Arterial', 'Collector', 'Local']
        tcl_roads = tcl_proj[tcl_proj['feature_code'].isin(road_types)]
        
        console.print(f"✓ Loaded {len(tcl_roads)} TCL road segments")
        return tcl_roads
    
    # OSM loading removed for TCL-only workflow
    
    def merge_road_networks(self, tcl_roads: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Return TCL roads as the merged network (OSM removed)."""
        console.print("Using TCL roads only (OSM removed)")
        # Drop exact duplicates by geometry
        tcl_unique = tcl_roads.drop_duplicates(subset=['geometry'])
        console.print(f"✓ {len(tcl_unique)} TCL segments after deduplication")
        return tcl_unique
    
    def clip_to_boundary(self, roads: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Clip roads to Toronto boundary with a small buffer."""
        console.print("Clipping roads to Toronto boundary...")
        
        # Buffer boundary by 50 meters to retain edge segments
        buffered_boundary = boundary.buffer(50)
        
        # Clip roads to boundary
        clipped_roads = gpd.clip(roads, buffered_boundary)
        
        console.print(f"✓ Clipped to {len(clipped_roads)} road segments within boundary")
        return clipped_roads
    
    def densify_roads(self, roads: gpd.GeoDataFrame, spacing_m: float = 10.0) -> List[SamplePoint]:
        """Densify road centerlines into sample points."""
        console.print(f"Generating sample points with {spacing_m}m spacing...")
        
        from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

        sample_points = []
        point_id = 0

        total_roads = len(roads)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Densifying roads...", total=total_roads)
            for idx, road in roads.iterrows():
                geometry = road.geometry

                if geometry.geom_type == 'LineString':
                    # Densify the line
                    coords = list(geometry.coords)
                    densified_coords = self._densify_line(coords, spacing_m)

                    for coord in densified_coords:
                        # Convert back to WGS84 for API calls
                        point = Point(coord)
                        point_gdf = gpd.GeoDataFrame([{'geometry': point}], crs='EPSG:3161')
                        point_wgs84 = point_gdf.to_crs('EPSG:4326')

                        sample_points.append(SamplePoint(
                            id=point_id,
                            lat=point_wgs84.geometry.iloc[0].y,
                            lon=point_wgs84.geometry.iloc[0].x,
                            road_id=str(road.get('centreline_id', f'tcl_{idx}')),
                            road_type=road.get('feature_code', 'unknown')
                        ))
                        point_id += 1
                progress.advance(task)

        console.print(f"✓ Generated {len(sample_points)} sample points")
        return sample_points
    def _densify_line(self, coords: List[Tuple[float, float]], spacing_m: float) -> List[Tuple[float, float]]:
        """Densify a line by adding points at regular intervals."""
        if len(coords) < 2:
            return coords
        
        densified = []
        
        for i in range(len(coords) - 1):
            start = coords[i]
            end = coords[i + 1]
            
            # Add start point
            densified.append(start)
            
            # Calculate distance between points
            distance = Point(start).distance(Point(end))
            
            if distance > spacing_m:
                # Calculate number of intermediate points
                num_points = int(distance / spacing_m)
                
                for j in range(1, num_points + 1):
                    t = j / (num_points + 1)
                    # Linear interpolation
                    lat = start[1] + t * (end[1] - start[1])
                    lon = start[0] + t * (end[0] - start[0])
                    densified.append((lon, lat))
            
            # Add end point (will be start of next segment)
            if i == len(coords) - 2:
                densified.append(end)
        
        return densified
    
    def save_sample_points(self, sample_points: List[SamplePoint]) -> Path:
        """Save sample points to Parquet file."""
        output_path = self.derived_dir / "sample_points.parquet"
        
        # Convert to DataFrame
        df = pd.DataFrame([point.dict() for point in sample_points])
        
        # Save to Parquet
        df.to_parquet(output_path, index=False)
        
        console.print(f"✓ Saved {len(sample_points)} sample points to {output_path}")
        return output_path
    
    def process_roads(self, spacing_m: float = 10.0) -> Tuple[List[SamplePoint], Path]:
        """Main processing pipeline for road networks."""
        console.print("🚀 Starting road processing pipeline...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Load boundary
            task = progress.add_task("Loading boundary...", total=5)
            boundary = self.load_boundary()
            progress.advance(task)
            
            # Load TCL roads
            task = progress.add_task("Loading TCL roads...", total=5)
            tcl_roads = self.load_tcl_roads()
            progress.advance(task)
            
            # Merge networks (TCL only)
            task = progress.add_task("Preparing TCL roads...", total=5)
            merged_roads = self.merge_road_networks(tcl_roads)
            progress.advance(task)
            
            # Clip to boundary
            task = progress.add_task("Clipping to boundary...", total=5)
            clipped_roads = self.clip_to_boundary(merged_roads, boundary)
            progress.advance(task)
        
        # Generate sample points
        sample_points = self.densify_roads(clipped_roads, spacing_m)
        
        # Save results
        output_path = self.save_sample_points(sample_points)
        
        console.print("✅ Road processing complete!")
        return sample_points, output_path


def main():
    """Test road processing."""
    processor = RoadProcessor("data")
    sample_points, output_path = processor.process_roads(spacing_m=10.0)
    console.print(f"Generated {len(sample_points)} sample points")


if __name__ == "__main__":
    main()
