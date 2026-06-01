"""
Static file serving configuration.

Mounts for PDF reports, exports, map tiles, and other downloadable content.
"""

from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import logging
import struct

from predict.core.config import get_config
from predict.core.api.deps import get_current_user

logger = logging.getLogger(__name__)

# PMTiles reader — loaded once at startup
_pmtiles_reader = None
_pmtiles_file = None


def setup_static_files(app: FastAPI) -> None:
    """
    Mount static file directories on FastAPI app.
    
    Mounts:
        - /exports: Generated exports (CSV, JSON)
        - /reports: Generated PDF reports
    
    Args:
        app: FastAPI application instance
    """
    config = get_config()
    
    # Ensure directories exist
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Mount exports directory for direct file access
    # Protected by API key middleware at router level
    app.mount(
        "/exports",
        StaticFiles(directory=str(config.EXPORTS_DIR)),
        name="exports"
    )
    
    logger.info(f"Static files mounted: /exports -> {config.EXPORTS_DIR}")

    # Mount uploads directory for vehicle images
    uploads_dir = config.ROOT_DIR / "uploads" / "vehicles"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/uploads/vehicles",
        StaticFiles(directory=str(uploads_dir)),
        name="vehicle_uploads"
    )
    logger.info(f"Static files mounted: /uploads/vehicles -> {uploads_dir}")


def setup_protected_static_routes(app: FastAPI) -> None:
    """
    Add protected routes for serving static files with authentication.
    
    These routes require API key validation unlike the raw /exports mount.
    """
    config = get_config()
    
    @app.get("/reports/download/{report_id}", tags=["reports"])
    async def download_report(
        report_id: str,
        current_user: dict = Depends(get_current_user),
    ):
        """
        Download a generated PDF report.
        
        Args:
            report_id: Report identifier (filename without extension)
        
        Returns:
            PDF file response
        """
        # Security: Validate report_id to prevent path traversal
        safe_report_id = Path(report_id).name
        if safe_report_id != report_id:
            raise HTTPException(status_code=400, detail="Invalid report ID")
        
        # Look for report in exports directory
        report_path = config.EXPORTS_DIR / f"{safe_report_id}.pdf"
        
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=f"{safe_report_id}.pdf"
        )
    
    @app.get("/exports/download/{filename}", tags=["exports"])
    async def download_export(
        filename: str,
        current_user: dict = Depends(get_current_user),
    ):
        """
        Download an export file (CSV, JSON, Parquet).
        
        Args:
            filename: Export filename
        
        Returns:
            File response with appropriate content type
        """
        # Security: Prevent path traversal
        safe_filename = Path(filename).name
        if safe_filename != filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = config.EXPORTS_DIR / safe_filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine content type
        content_type = _get_content_type(file_path.suffix)
        
        return FileResponse(
            path=str(file_path),
            media_type=content_type,
            filename=safe_filename
        )
    
    logger.info("Protected static routes registered")


def _get_content_type(suffix: str) -> str:
    """Get MIME type for file extension."""
    content_types = {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".json": "application/json",
        ".parquet": "application/octet-stream",
        ".zip": "application/zip",
        ".txt": "text/plain",
    }
    return content_types.get(suffix.lower(), "application/octet-stream")


def get_report_url(report_id: str, public_base_url: str) -> str:
    """
    Generate public URL for a report.
    
    Args:
        report_id: Report identifier
        public_base_url: Base URL (e.g., https://api.predict.com)
    
    Returns:
        Full URL to download the report
    """
    return f"{public_base_url}/reports/download/{report_id}"


def get_export_url(filename: str, public_base_url: str) -> str:
    """
    Generate public URL for an export file.

    Args:
        filename: Export filename
        public_base_url: Base URL

    Returns:
        Full URL to download the export
    """
    return f"{public_base_url}/exports/download/{filename}"


def setup_tile_server(app: FastAPI) -> None:
    """
    Set up PMTiles tile serving for MapLibre GL maps.

    Serves vector tiles from a PMTiles file at /tiles/{z}/{x}/{y}.pbf
    and a MapLibre style JSON at /tiles/style.json
    """
    config = get_config()
    tiles_dir = Path(config.ROOT_DIR) / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    # Find PMTiles file
    pmtiles_path = None
    for f in tiles_dir.glob("*.pmtiles"):
        pmtiles_path = f
        break

    if pmtiles_path is None:
        logger.warning(
            f"No .pmtiles file found in {tiles_dir}. "
            "Map tiles will not be served. Place gcc_region.pmtiles in the tiles/ directory."
        )
        return

    logger.info(f"PMTiles tile server: serving {pmtiles_path.name}")

    try:
        global _pmtiles_file
        import warnings
        from pmtiles.reader import Reader, MmapSource
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            _pmtiles_file = open(str(pmtiles_path), "rb")
            reader = Reader(MmapSource(_pmtiles_file))
        logger.info(f"PMTiles reader initialized for {pmtiles_path.name}")
    except ImportError:
        logger.warning("pmtiles package not installed. Run: pip install pmtiles")
        return
    except Exception as e:
        logger.error(f"Failed to open PMTiles file: {e}")
        return

    @app.get("/tiles/{z}/{x}/{y}.pbf", tags=["tiles"])
    async def get_tile(z: int, x: int, y: int):
        """Serve a vector tile from PMTiles."""
        tile_data = reader.get(z, x, y)
        if tile_data is None:
            return Response(status_code=204)
        return Response(
            content=bytes(tile_data),
            media_type="application/vnd.mapbox-vector-tile",
            headers={
                "Content-Encoding": "gzip",
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @app.get("/tiles/style.json", tags=["tiles"])
    async def get_style():
        """MapLibre style JSON pointing to local tile server."""
        return {
            "version": 8,
            "name": "PREDICT Map",
            "sources": {
                "openmaptiles": {
                    "type": "vector",
                    "tiles": ["/tiles/{z}/{x}/{y}.pbf"],
                    "maxzoom": 14,
                }
            },
            "layers": [
                {
                    "id": "background",
                    "type": "background",
                    "paint": {"background-color": "#F5F5F7"},
                },
                {
                    "id": "water",
                    "type": "fill",
                    "source": "openmaptiles",
                    "source-layer": "water",
                    "paint": {"fill-color": "#D4E6F1"},
                },
                {
                    "id": "landcover",
                    "type": "fill",
                    "source": "openmaptiles",
                    "source-layer": "landcover",
                    "paint": {"fill-color": "#E8F5E9", "fill-opacity": 0.5},
                },
                {
                    "id": "roads-highway",
                    "type": "line",
                    "source": "openmaptiles",
                    "source-layer": "transportation",
                    "filter": ["==", "class", "motorway"],
                    "paint": {
                        "line-color": "#FFB74D",
                        "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.5, 14, 4],
                    },
                },
                {
                    "id": "roads-main",
                    "type": "line",
                    "source": "openmaptiles",
                    "source-layer": "transportation",
                    "filter": ["in", "class", "primary", "secondary", "tertiary", "trunk"],
                    "paint": {
                        "line-color": "#FFFFFF",
                        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 14, 3],
                    },
                },
                {
                    "id": "roads-minor",
                    "type": "line",
                    "source": "openmaptiles",
                    "source-layer": "transportation",
                    "filter": ["in", "class", "minor", "service"],
                    "minzoom": 12,
                    "paint": {
                        "line-color": "#E0E0E0",
                        "line-width": 1,
                    },
                },
                {
                    "id": "buildings",
                    "type": "fill",
                    "source": "openmaptiles",
                    "source-layer": "building",
                    "minzoom": 13,
                    "paint": {
                        "fill-color": "#D5D5D5",
                        "fill-opacity": 0.6,
                    },
                },
                {
                    "id": "buildings-3d",
                    "type": "fill-extrusion",
                    "source": "openmaptiles",
                    "source-layer": "building",
                    "minzoom": 14,
                    "paint": {
                        "fill-extrusion-color": "#C8C8C8",
                        "fill-extrusion-height": ["get", "render_height"],
                        "fill-extrusion-base": ["get", "render_min_height"],
                        "fill-extrusion-opacity": 0.7,
                    },
                },
                {
                    "id": "place-labels",
                    "type": "symbol",
                    "source": "openmaptiles",
                    "source-layer": "place",
                    "layout": {
                        "text-field": "{name:latin}",
                        "text-size": ["interpolate", ["linear"], ["zoom"], 6, 10, 14, 16],
                    },
                    "paint": {
                        "text-color": "#666666",
                        "text-halo-color": "#FFFFFF",
                        "text-halo-width": 1.5,
                    },
                },
            ],
        }

    logger.info("Tile server routes registered: /tiles/{z}/{x}/{y}.pbf, /tiles/style.json")
