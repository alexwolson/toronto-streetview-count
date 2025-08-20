"""Google Street View Image Metadata API client."""

import asyncio
import logging
import time
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional

import aiosqlite
import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table

from .models import Panorama, ProcessingStats, SamplePoint, StreetViewResponse

logger = logging.getLogger(__name__)
console = Console()

# Google Street View Image Metadata API endpoint
GOOGLE_STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"


class StreetViewClient:
    """Client for Google Street View Image Metadata API with rate limiting and persistence."""
    
    def __init__(self, db_path: str, qps: int = 10, project_id: str = None, api_key: str = None):
        self.db_path = db_path
        self.qps = qps  # Queries per second
        self.min_interval = 1.0 / qps  # Minimum time between requests
        self.project_id = project_id
        self.api_key = api_key
        
        # Initialize Google Cloud credentials (for project info, not API calls)
        self._init_google_credentials()
        
        # Rate limiting
        self.last_request_time = 0.0
        self.request_semaphore = asyncio.Semaphore(qps)
        
        # Statistics
        self.stats = ProcessingStats()
    
    def _init_google_credentials(self):
        """Initialize Google Cloud authentication and get API key if needed."""
        try:
            import google.auth
            from google.auth.transport.requests import Request
            from google.auth.exceptions import DefaultCredentialsError
            
            # Try to get default credentials (for project info)
            credentials, project = google.auth.default()
            
            if not self.project_id:
                self.project_id = project
            
            console.print(f"✅ Using Google Cloud project: {self.project_id}")
            
            # If no API key provided, try to get one from the project
            if not self.api_key:
                self.api_key = self._get_project_api_key()
            
            if self.api_key:
                console.print("✅ Street View API key configured")
            else:
                console.print("⚠️  No API key found - this may limit functionality")
            
        except DefaultCredentialsError:
            console.print("❌ No Google Cloud credentials found!")
            console.print("Please run: gcloud auth application-default login")
            console.print("Or set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            if not self.api_key:
                console.print("Or provide an API key directly")
            raise
        except Exception as e:
            console.print(f"❌ Google Cloud authentication failed: {e}")
            if not self.api_key:
                raise
    
    def _get_project_api_key(self):
        """Try to get an API key from the current project."""
        try:
            import subprocess
            import json
            
            # Try to get API keys for the project
            result = subprocess.run([
                'gcloud', 'services', 'api-keys', 'list', 
                '--project', self.project_id,
                '--format', 'json'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                keys = json.loads(result.stdout)
                for key in keys:
                    # Look for keys with Street View restrictions or no restrictions
                    if 'restrictions' not in key or not key['restrictions']:
                        # Unrestricted key - get the key string
                        key_id = key['name'].split('/')[-1]
                        return self._get_api_key_string(key_id)
                    elif 'apiTargets' in key.get('restrictions', {}):
                        # Check if it has Street View access
                        for target in key['restrictions']['apiTargets']:
                            if 'street-view' in target.get('service', ''):
                                key_id = key['name'].split('/')[-1]
                                return self._get_api_key_string(key_id)
            
            return None
            
        except Exception as e:
            console.print(f"⚠️  Could not retrieve API key: {e}")
            return None
    
    def _get_api_key_string(self, key_id):
        """Get the actual API key string from the key ID."""
        try:
            import subprocess
            import json
            
            result = subprocess.run([
                'gcloud', 'services', 'api-keys', 'get-key-string', key_id,
                '--project', self.project_id
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return None
            
        except Exception:
            return None
    
    def _refresh_access_token(self):
        """Refresh the access token when it expires."""
        try:
            import google.auth
            from google.auth.transport.requests import Request
            
            # Get fresh credentials
            credentials, _ = google.auth.default()
            
            # Refresh if needed
            if not credentials.valid:
                credentials.refresh(Request())
            
            self.access_token = credentials.token
            console.print("✅ Access token refreshed successfully")
            
        except Exception as e:
            console.print(f"❌ Failed to refresh access token: {e}")
            raise
    
    async def initialize_database(self):
        """Initialize SQLite database with required tables."""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=10000")
            await db.execute("PRAGMA busy_timeout=30000")
            
            # Sample points table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sample_points (
                    id INTEGER PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    road_id TEXT,
                    road_type TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # API responses table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    pano_id TEXT,
                    lat REAL,
                    lon REAL,
                    date TEXT,
                    copyright TEXT,
                    error_message TEXT,
                    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sample_id) REFERENCES sample_points (id)
                )
            """)
            
            # Panoramas table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS panoramas (
                    pano_id TEXT PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    date TEXT,
                    copyright TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sample_count INTEGER DEFAULT 1
                )
            """)
            
            await db.commit()
    
    async def insert_sample_points(self, sample_points: List[SamplePoint]):
        """Insert sample points into database."""
        async with aiosqlite.connect(self.db_path) as db:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Inserting sample points...", total=len(sample_points))
                
                for point in sample_points:
                    await db.execute("""
                        INSERT OR REPLACE INTO sample_points (id, lat, lon, road_id, road_type, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (point.id, point.lat, point.lon, point.road_id, point.road_type, point.status))
                    
                    progress.advance(task)
            
            await db.commit()
            self.stats.total_sample_points = len(sample_points)
    
    async def get_pending_sample_points(self, limit: Optional[int] = None) -> List[SamplePoint]:
        """Get sample points that haven't been queried yet."""
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT id, lat, lon, road_id, road_type, status FROM sample_points WHERE status = 'pending'"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            
            return [
                SamplePoint(
                    id=row[0], lat=row[1], lon=row[2], 
                    road_id=row[3], road_type=row[4], status=row[5]
                )
                for row in rows
            ]
    
    async def fetch_metadata(self, lat: float, lon: float, radius_m: int) -> Dict:
        """Fetch metadata for a single location with rate limiting."""
        # Rate limiting
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)
        
        async with self.request_semaphore:
            try:
                # Use API key for authentication (recommended for Street View)
                params = {
                    "location": f"{lat},{lon}",
                    "radius": str(radius_m),
                    "source": "outdoor",
                }
                
                # Add API key if available
                if self.api_key:
                    params["key"] = self.api_key
                else:
                    raise ValueError("API key is required for Street View Image Metadata API")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(GOOGLE_STREETVIEW_METADATA_URL, params=params)
                    response.raise_for_status()
                    
                    self.last_request_time = time.time()
                    self.stats.total_requests += 1
                    
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    console.print(f"⚠ Rate limited, waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    return await self.fetch_metadata(lat, lon, radius_m)
                elif e.response.status_code == 400:  # Bad request (possibly invalid API key)
                    logger.error(f"Bad request - check API key and parameters: {e.response.text}")
                    raise
                elif e.response.status_code == 403:  # Forbidden (API key restrictions)
                    logger.error(f"Forbidden - check API key restrictions: {e.response.text}")
                    raise
                else:
                    raise
            except Exception as e:
                logger.error(f"Error fetching metadata for ({lat}, {lon}): {e}")
                raise
    
    async def process_sample_point(self, point: SamplePoint, radius_m: int) -> StreetViewResponse:
        """Process a single sample point and return the response."""
        try:
            data = await self.fetch_metadata(point.lat, point.lon, radius_m)
            
            response = StreetViewResponse(
                sample_id=point.id,
                status=data.get("status", "UNKNOWN"),
                pano_id=data.get("pano_id"),
                lat=data.get("location", {}).get("lat") if data.get("location") else None,
                lon=data.get("location", {}).get("lng") if data.get("location") else None,
                date=data.get("date"),
                copyright=data.get("copyright"),
                queried_at=datetime.utcnow()
            )
            
            # Update sample point status
            await self._update_sample_point_status(point.id, "queried")
            self.stats.points_queried += 1
            self.stats.successful_requests += 1
            
            return response
            
        except Exception as e:
            response = StreetViewResponse(
                sample_id=point.id,
                status="ERROR",
                error_message=str(e),
                queried_at=datetime.utcnow()
            )
            
            # Update sample point status
            await self._update_sample_point_status(point.id, "failed")
            self.stats.points_failed += 1
            
            return response
    
    async def _update_sample_point_status(self, point_id: int, status: str):
        """Update the status of a sample point."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sample_points SET status = ? WHERE id = ?",
                (status, point_id)
            )
            await db.commit()
    
    async def save_response(self, response: StreetViewResponse):
        """Save API response to database."""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=10000")
            await db.execute("PRAGMA busy_timeout=30000")
            
            await db.execute("""
                INSERT INTO responses (sample_id, status, pano_id, lat, lon, date, copyright, error_message, queried_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                response.sample_id, response.status, response.pano_id,
                response.lat, response.lon, response.date, response.copyright,
                response.error_message, response.queried_at
            ))
            
            # If we found a panorama, update the panoramas table
            if response.status == "OK" and response.pano_id:
                await self._update_panorama(response, db)
            
            await db.commit()
    
    async def _update_panorama(self, response: StreetViewResponse, db=None):
        """Update or insert panorama information."""
        if db is None:
            async with aiosqlite.connect(self.db_path) as db:
                await self._update_panorama_internal(response, db)
        else:
            await self._update_panorama_internal(response, db)
    
    async def _update_panorama_internal(self, response: StreetViewResponse, db):
        """Internal method to update panorama information."""
        # Check if panorama already exists
        cursor = await db.execute(
            "SELECT sample_count FROM panoramas WHERE pano_id = ?",
            (response.pano_id,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Update existing panorama
            await db.execute(
                "UPDATE panoramas SET sample_count = sample_count + 1 WHERE pano_id = ?",
                (response.pano_id,)
            )
        else:
            # Insert new panorama
            await db.execute("""
                INSERT INTO panoramas (pano_id, lat, lon, date, copyright, first_seen, sample_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                response.pano_id, response.lat, response.lon,
                response.date, response.copyright, response.queried_at
            ))
            
            self.stats.unique_panoramas += 1
    
    async def process_all_points(self, radius_m: int, batch_size: int = 100) -> ProcessingStats:
        """Process all pending sample points."""
        console.print("🚀 Starting Street View metadata collection...")
        
        # Get all pending points
        pending_points = await self.get_pending_sample_points()
        total_points = len(pending_points)
        
        if total_points == 0:
            console.print("✓ No pending points to process")
            return self.stats
        
        console.print(f"Processing {total_points} sample points in batches of {batch_size}...")
        
        # Calculate total batches
        total_batches = (total_points + batch_size - 1) // batch_size
        
        # Process in batches with enhanced progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("|"),
            TextColumn("Batch {task.fields[current_batch]}/{task.fields[total_batches]}"),
            TextColumn("|"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            # Main progress task for overall points
            main_task = progress.add_task(
                "Processing points...", 
                total=total_points,
                current_batch=1,
                total_batches=total_batches
            )
            
            # Batch progress task
            batch_task = progress.add_task(
                "Current batch...", 
                total=batch_size,
                visible=False
            )
            
            start_time = time.time()
            
            for batch_num in range(total_batches):
                batch_start = batch_num * batch_size
                batch_end = min(batch_start + batch_size, total_points)
                batch = pending_points[batch_start:batch_end]
                current_batch_size = len(batch)
                
                # Update main task with current batch info
                progress.update(
                    main_task, 
                    current_batch=batch_num + 1,
                    total_batches=total_batches
                )
                
                # Show batch progress for current batch
                progress.update(batch_task, total=current_batch_size, completed=0, visible=True)
                progress.update(batch_task, description=f"Batch {batch_num + 1}/{total_batches}")
                
                # Process batch concurrently
                tasks = [
                    self.process_sample_point(point, radius_m) 
                    for point in batch
                ]
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Save responses and update progress
                successful = 0
                failed = 0
                
                for response in responses:
                    if isinstance(response, Exception):
                        logger.error(f"Error processing point: {response}")
                        failed += 1
                    else:
                        await self.save_response(response)
                        successful += 1
                    
                    # Update both progress bars
                    progress.advance(main_task)
                    progress.advance(batch_task)
                
                # Update stats
                self.stats.points_queried += successful
                self.stats.points_failed += failed
                
                # Small delay between batches to be nice to the API
                await asyncio.sleep(0.1)
            
            # Hide batch progress when done
            progress.update(batch_task, visible=False)
        
        # Update final stats
        self.stats.end_time = datetime.utcnow()
        
        console.print("✅ Street View metadata collection complete!")
        return self.stats
    
    def print_stats(self):
        """Print processing statistics."""
        table = Table(title="Processing Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Total Sample Points", str(self.stats.total_sample_points))
        table.add_row("Points Queried", str(self.stats.points_queried))
        table.add_row("Points Failed", str(self.stats.points_failed))
        table.add_row("Unique Panoramas", str(self.stats.unique_panoramas))
        table.add_row("Total API Requests", str(self.stats.total_requests))
        table.add_row("Successful Requests", str(self.stats.successful_requests))
        
        if self.stats.start_time and self.stats.end_time:
            duration = self.stats.end_time - self.stats.start_time
            table.add_row("Duration", str(duration))
        
        console.print(table)
    
    async def export_results(self, output_dir: str) -> str:
        """Export results to Parquet files."""
        from pathlib import Path
        import pandas as pd
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        console.print("📤 Exporting results...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Export panoramas
            cursor = await db.execute("""
                SELECT pano_id, lat, lon, date, copyright, first_seen, sample_count
                FROM panoramas
                ORDER BY first_seen
            """)
            panoramas_data = await cursor.fetchall()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                # Export panoramas
                task = progress.add_task("Exporting panoramas...", total=len(panoramas_data))
                
                panoramas_df = pd.DataFrame(panoramas_data, columns=[
                    'pano_id', 'lat', 'lon', 'date', 'copyright', 'first_seen', 'sample_count'
                ])
                
                panoramas_path = output_path / "toronto_pano_ids.parquet"
                panoramas_df.to_parquet(panoramas_path, index=False)
                progress.advance(task)
                
                # Export sample points with results
                cursor = await db.execute("""
                    SELECT sp.*, r.status as api_status, r.pano_id, r.error_message
                    FROM sample_points sp
                    LEFT JOIN responses r ON sp.id = r.sample_id
                    ORDER BY sp.id
                """)
                sample_data = await cursor.fetchall()
                
                task = progress.add_task("Exporting sample points...", total=len(sample_data))
                
                sample_df = pd.DataFrame(sample_data, columns=[
                    'id', 'lat', 'lon', 'road_id', 'road_type', 'status', 'created_at',
                    'api_status', 'pano_id', 'error_message'
                ])
                
                sample_path = output_path / "sample_points_with_results.parquet"
                sample_df.to_parquet(sample_path, index=False)
                progress.advance(task)
        
        console.print(f"✓ Exported results to {output_path}")
        return str(output_path)


async def main():
    """Test Street View client."""
    import os
    
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        console.print("❌ Please set GOOGLE_MAPS_API_KEY environment variable")
        return
    
    client = StreetViewClient(api_key, "data/streetview.db")
    await client.initialize_database()
    
    # Test with a few sample points
    test_points = [
        SamplePoint(id=1, lat=43.6532, lon=-79.3832, road_id="test1", road_type="highway"),
        SamplePoint(id=2, lat=43.6519, lon=-79.3817, road_id="test2", road_type="residential"),
    ]
    
    await client.insert_sample_points(test_points)
    stats = await client.process_all_points(radius_m=30)
    client.print_stats()


if __name__ == "__main__":
    asyncio.run(main())
