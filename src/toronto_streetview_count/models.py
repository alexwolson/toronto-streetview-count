"""Data models for the Toronto Street View Counter."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Geographic bounding box."""
    min_lon: float = Field(..., description="Minimum longitude (west)")
    min_lat: float = Field(..., description="Minimum latitude (south)")
    max_lon: float = Field(..., description="Maximum longitude (east)")
    max_lat: float = Field(..., description="Maximum latitude (north)")


class SamplePoint(BaseModel):
    """A point along a road for sampling Street View metadata."""
    id: int = Field(..., description="Unique identifier")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    road_id: Optional[str] = Field(None, description="Associated road identifier")
    road_type: Optional[str] = Field(None, description="Type of road")
    status: str = Field("pending", description="Status: pending, queried, failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StreetViewResponse(BaseModel):
    """Response from Google Street View Image Metadata API."""
    sample_id: int = Field(..., description="ID of the sample point")
    status: str = Field(..., description="API response status")
    pano_id: Optional[str] = Field(None, description="Panorama ID if found")
    lat: Optional[float] = Field(None, description="Panorama latitude if found")
    lon: Optional[float] = Field(None, description="Panorama longitude if found")
    date: Optional[str] = Field(None, description="Panorama capture date if available")
    copyright: Optional[str] = Field(None, description="Copyright information")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class Panorama(BaseModel):
    """A unique Street View panorama."""
    pano_id: str = Field(..., description="Unique panorama identifier")
    lat: float = Field(..., description="Panorama latitude")
    lon: float = Field(..., description="Panorama longitude")
    date: Optional[str] = Field(None, description="Capture date")
    copyright: Optional[str] = Field(None, description="Copyright information")
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    sample_count: int = Field(1, description="Number of sample points that found this panorama")


class ProcessingStats(BaseModel):
    """Statistics about the processing pipeline."""
    total_sample_points: int = Field(0, description="Total number of sample points")
    points_queried: int = Field(0, description="Number of points successfully queried")
    points_failed: int = Field(0, description="Number of points that failed")
    unique_panoramas: int = Field(0, description="Number of unique panoramas found")
    start_time: Optional[datetime] = Field(None, description="Processing start time")
    end_time: Optional[datetime] = Field(None, description="Processing end time")
    total_requests: int = Field(0, description="Total API requests made")
    successful_requests: int = Field(0, description="Successful API requests")


# Toronto bounding box
TORONTO_BBOX = BBox(
    min_lon=-79.6393,  # West
    min_lat=43.5810,   # South
    max_lon=-79.1156,  # East
    max_lat=43.8555,   # North
)
