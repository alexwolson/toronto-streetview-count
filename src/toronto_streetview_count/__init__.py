import asyncio
import math
import os
from dataclasses import dataclass
from typing import AsyncIterator, Iterable, Tuple

import click
import httpx


GOOGLE_STREETVIEW_METADATA_URL = (
    "https://maps.googleapis.com/maps/api/streetview/metadata"
)


@dataclass(frozen=True)
class BBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


TORONTO_BBOX = BBox(
    min_lon=-79.6393,  # West
    min_lat=43.5810,   # South
    max_lon=-79.1156,  # East
    max_lat=43.8555,   # North
)


def generate_grid_points(
    bbox: BBox, spacing_meters: float
) -> Iterable[Tuple[float, float]]:
    """Generate a lat/lon grid over bbox approximately spaced by meters.

    Uses a simple equirectangular approximation suitable for small bbox extents.
    """
    # meters per degree latitude is ~111_320
    meters_per_degree_lat = 111_320.0
    # meters per degree longitude scales with cos(latitude)
    mean_lat_rad = math.radians((bbox.min_lat + bbox.max_lat) / 2.0)
    meters_per_degree_lon = 111_320.0 * math.cos(mean_lat_rad)

    dlat = spacing_meters / meters_per_degree_lat
    dlon = spacing_meters / meters_per_degree_lon

    lat = bbox.min_lat
    while lat <= bbox.max_lat + 1e-12:
        lon = bbox.min_lon
        while lon <= bbox.max_lon + 1e-12:
            yield (lat, lon)
            lon += dlon
        lat += dlat


async def fetch_metadata(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    api_key: str,
    radius_m: int,
) -> dict:
    params = {
        "location": f"{lat},{lon}",
        "key": api_key,
        "radius": str(radius_m),
        "source": "outdoor",
    }
    r = await client.get(GOOGLE_STREETVIEW_METADATA_URL, params=params, timeout=20.0)
    r.raise_for_status()
    return r.json()


async def count_points(
    points: Iterable[Tuple[float, float]],
    api_key: str,
    radius_m: int,
    concurrency: int,
) -> Tuple[int, int]:
    """Returns (num_points_with_imagery, total_points_queried)."""
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(lat: float, lon: float) -> int:
        async with semaphore:
            try:
                data = await fetch_metadata(client, lat, lon, api_key, radius_m)
                # status OK indicates some pano exists in radius
                return 1 if data.get("status") == "OK" else 0
            except Exception:
                return 0

    async with httpx.AsyncClient() as client:
        tasks = [asyncio.create_task(worker(lat, lon)) for lat, lon in points]
        results = await asyncio.gather(*tasks)
    return sum(results), len(results)


def validate_spacing(_: click.Context, __: click.Parameter, value: float) -> float:
    if value <= 0:
        raise click.BadParameter("Spacing must be > 0 meters")
    if value > 200:
        # Large spacing risks undercount; warn via echo but allow
        click.echo("Warning: spacing >200m may undercount imagery", err=True)
    return value


@click.group()
def cli() -> None:
    """Tools to probe Street View coverage in Toronto."""


@cli.command()
@click.option(
    "--api-key",
    envvar="GOOGLE_MAPS_API_KEY",
    required=True,
    help="Google Maps API key (or set GOOGLE_MAPS_API_KEY)",
)
@click.option(
    "--spacing",
    type=float,
    default=50.0,
    callback=validate_spacing,
    show_default=True,
    help="Grid spacing in meters",
)
@click.option(
    "--radius",
    type=int,
    default=30,
    show_default=True,
    help="Search radius in meters for metadata endpoint",
)
@click.option(
    "--concurrency",
    type=int,
    default=64,
    show_default=True,
    help="Max concurrent metadata requests",
)
def estimate(api_key: str, spacing: float, radius: int, concurrency: int) -> None:
    """Estimate count of locations with Street View within Toronto bbox.

    Note: This samples a grid and counts points with status=OK. It estimates
    coverage, not the exact number of distinct panos.
    """
    points = list(generate_grid_points(TORONTO_BBOX, spacing))
    total_points = len(points)
    click.echo(f"Querying {total_points} grid points (spacing={spacing}m)...")
    ok_points, queried = asyncio.run(
        count_points(points, api_key=api_key, radius_m=radius, concurrency=concurrency)
    )
    pct = (ok_points / queried * 100.0) if queried else 0.0
    click.echo(f"OK at {ok_points}/{queried} points ({pct:.1f}%).")


def main() -> None:
    cli()
