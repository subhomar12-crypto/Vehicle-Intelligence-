"""
Static file serving configuration.

Mounts for PDF reports, exports, and other downloadable content.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import logging

from predict.core.config import get_config
from predict.core.api.deps import get_current_user

logger = logging.getLogger(__name__)


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
