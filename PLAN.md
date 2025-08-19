## Goal

**Count the total number of Google Street View panoramas available by API within the City of Toronto boundary.** The output should be a deduplicated set of panorama IDs (with coordinates and dates) and a reproducible process.

---

## High-level approach

- **Boundary-driven**: Use the official City of Toronto boundary polygon to constrain the study area.
- **Road-centric sampling**: Densify the Toronto road centerline network and sample points along roads to query the Street View metadata API near where panoramas exist.
- **Metadata queries + deduplication**: Call the Street View Image Metadata endpoint around each sample point, collect `pano_id`s, and deduplicate.
- **Persistence and resumability**: Store results in SQLite/Parquet so we can resume, avoid re-querying, and audit.
- **Validation**: Sanity-check against subsets, visualize coverage, and measure stability vs. sampling parameters.

---

## Key references and APIs

- **City of Toronto Open Data**
  - Boundary polygon: search for "City of Toronto Boundary" on the Open Data Portal ([link](https://open.toronto.ca/)).
  - Road network: "Toronto Centreline (TCL)" dataset ([link](https://open.toronto.ca/)).
- **Google Maps Platform**
  - Street View Image Metadata API (part of Street View Static API): returns status and `pano_id` for nearest panorama to a `location` and `radius` ([docs](https://developers.google.com/maps/documentation/streetview/metadata)).
  - Note: The Street View Publish API requires OAuth and focuses on user-contributed 360 photos; it is not suitable for enumerating Google-owned panoramas.

---

## Constraints, quotas, and costs

- **Quota and pricing**: Metadata requests are billable. Set a budget and throttle QPS. Consider running in batches and caching.
- **Terms of Service**: Ensure usage complies with Google Maps Platform ToS.

---

## Data pipeline plan

1. **Acquire geodata**
   - Download the City of Toronto boundary polygon as GeoJSON or Shapefile.
   - Download Toronto Centreline (TCL) road centerlines.
   - Store under `data/raw/`.

2. **Preprocess**
   - Load with `geopandas`.
   - Reproject to a suitable projected CRS (e.g., EPSG:3857 or EPSG:3161/26917) for accurate distance operations.
   - Clip TCL to the city boundary (buffer a few meters to retain edge segments).
   - Densify each road polyline into points every `d` meters (start with `d = 10–15 m`).
   - Filter points that fall outside the boundary after densification.
   - Save sampled points to `data/derived/sample_points.parquet`.

3. **Sampling parameters**
   - **Step distance `d`**: 10–15 m aims to be smaller than typical pano spacing on roads.
   - **Metadata search radius `r`**: 15–30 m to match the densified points to their nearest panoramas along the road.
   - Tune `d` and `r` to balance completeness vs. cost.

4. **API integration**
   - Use `httpx` or a Python package (e.g., `streetview`) if it adds value. Direct HTTP is sufficient for the Metadata API.
   - Request: `GET https://maps.googleapis.com/maps/api/streetview/metadata?location={lat},{lng}&radius={r}&source=outdoor&key=...`.
   - Response: Check `status == "OK"`; if present, record `pano_id`, `location` (`lat`,`lng`), and `date` if available.
   - Implement retries with exponential backoff on 429/5xx, and respect a configured QPS.

5. **Deduplication and counting**
   - Maintain a persistent set/map of discovered `pano_id -> {lat, lng, date}`.
   - Each successful metadata hit may map multiple sample points to the same `pano_id`.
   - The final count is the cardinality of unique `pano_id`s within the Toronto boundary.

6. **Persistence**
   - Use SQLite for progress tracking: tables for `sample_points` (id, lat, lng, status), `responses` (sample_id, pano_id, status, ts), and `panos` (pano_id PK, lat, lng, date).
   - Also export deduplicated results to Parquet/CSV for analysis.
   - Implement resume capability: skip already-queried points and already-seen `pano_id`s.

7. **Validation**
   - Run the pipeline on small AOIs (e.g., a few neighborhoods) with much denser sampling (e.g., `d = 5 m`, `r = 25 m`) and compare counts to the default settings.
   - Map sampled points vs. pano coordinates to verify association.
   - Track marginal gain of new `pano_id`s as more points are sampled; stop when marginal gain is negligible.

8. **Outputs**
   - `outputs/toronto_pano_ids.parquet` (or `.csv`): `pano_id, lat, lng, date`.
   - `outputs/summary.json`: total count, parameters used, runtime, request stats.
   - Optional: simple map (e.g., `folium`) visualizing pano locations.

---

## CLI design (proposed commands)

- **download-boundary**: Download/verify boundary and TCL datasets into `data/raw/`.
- **prepare-points**: Build densified sample points within boundary; write to `data/derived/`.
- **crawl**: Query metadata for all sample points with concurrency and rate limiting; store in SQLite and Parquet.
- **count**: Emit the deduplicated count and write `outputs/` artifacts.
- **subset**: Run the pipeline on a smaller bbox for quick validation.

Each command should accept parameters (e.g., `--step-m`, `--radius-m`, `--qps`, `--concurrency`, `--resume`).

---

## Implementation details

- **Dependencies**
  - Runtime: `httpx`, `click`, `rich` (progress), `pydantic` (optional, for schemas).
  - Geospatial: `geopandas`, `shapely`, `pyproj`, `pyogrio` (fast I/O). These can be optional extras to avoid heavy installs for non-geo steps.
  - Storage: `pandas`, `sqlite3` (stdlib) or `aiosqlite` for async access.

- **Rate limiting and retries**
  - Use a token bucket or simple sleep to cap QPS.
  - On HTTP 429, honor `Retry-After` if present.
  - Backoff on 5xx with jitter.

- **Robustness**
  - Cache responses for sample points (local SQLite) to avoid re-billing on reruns.
  - Regularly checkpoint deduplicated pano set.
  - Graceful shutdown and resume.

- **Edge cases**
  - Boundary edges and islands (Toronto Islands): ensure they are included by boundary polygon.
  - Private roads or areas without Street View.
  - Panos just outside boundary but matched by radius: after retrieving metadata, filter by pano coordinate being inside the boundary polygon.

---

## Estimating effort and cost

- Point count estimate: Toronto TCL length O(10,000+ km). At 15 m spacing, expect on the order of 600k–1M sample points. With deduplication, each pano will be hit multiple times, so total requests can be reduced by batching and early stopping.
- Consider starting with a coarser pass (e.g., 25 m) to enumerate most `pano_id`s, then run a focused second pass where coverage was sparse.

---

## Next steps

1. Add geospatial dependencies and implement `prepare-points`.
2. Implement persistent storage (SQLite + Parquet) and the `crawl` command with rate limiting.
3. Run a neighborhood subset to validate parameters.
4. Scale to city-wide run; monitor cost and request metrics.
5. Produce final count, artifacts, and a short report.
