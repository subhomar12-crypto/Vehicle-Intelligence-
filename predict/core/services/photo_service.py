"""
Vehicle photo processing service.

Handles background removal and EXIF stripping for vehicle photos.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def process_vehicle_photo(file_path: str) -> str:
    """
    Process a vehicle photo: remove background, replace with #F5F5F7, strip EXIF.

    Args:
        file_path: Path to the uploaded image file

    Returns:
        Path to the processed image file
    """
    try:
        from PIL import Image

        # Strip EXIF data by re-saving without exif
        img = Image.open(file_path)

        # Convert to RGBA for background removal
        img = img.convert("RGBA")

        try:
            from rembg import remove

            # Remove background
            result = remove(img)

            # Create new image with #F5F5F7 background
            bg = Image.new("RGBA", result.size, (245, 245, 247, 255))
            bg.paste(result, mask=result.split()[3])  # Use alpha channel as mask

            # Convert back to RGB for saving as JPEG
            final = bg.convert("RGB")

        except ImportError:
            logger.warning("rembg not installed - skipping background removal")
            final = img.convert("RGB")

        # Save processed image (overwrite original)
        output_path = file_path
        final.save(output_path, "JPEG", quality=90, optimize=True)

        logger.info(f"Photo processed: {file_path}")
        return output_path

    except ImportError:
        logger.warning("Pillow not installed - skipping photo processing")
        return file_path
    except Exception as e:
        logger.error(f"Photo processing failed: {e}")
        return file_path


async def auto_assign_on_registration(db, profile) -> Optional[str]:
    """
    Check if there's a pre-uploaded photo matching this vehicle.
    Match by VIN first, then by make/model/year/color.

    Returns the image_url if a match was found, None otherwise.
    """
    from sqlalchemy import select
    from predict.core.db.models.vehicle import VehiclePhoto

    try:
        # Try matching by VIN first
        if profile.vin:
            stmt = select(VehiclePhoto).where(
                VehiclePhoto.vin == profile.vin,
                VehiclePhoto.assigned_to_profile_id.is_(None)
            ).limit(1)
            result = await db.execute(stmt)
            photo = result.scalar_one_or_none()

            if photo:
                photo.assigned_to_profile_id = profile.profile_id
                profile.image_url = photo.image_url
                await db.commit()
                logger.info(f"Auto-assigned photo {photo.id} to profile {profile.profile_id} by VIN")
                return photo.image_url

        # Try matching by make/model/year
        if profile.make and profile.model:
            stmt = select(VehiclePhoto).where(
                VehiclePhoto.make == profile.make,
                VehiclePhoto.model == profile.model,
                VehiclePhoto.assigned_to_profile_id.is_(None)
            )
            if profile.year:
                stmt = stmt.where(VehiclePhoto.year == profile.year)
            stmt = stmt.limit(1)

            result = await db.execute(stmt)
            photo = result.scalar_one_or_none()

            if photo:
                photo.assigned_to_profile_id = profile.profile_id
                profile.image_url = photo.image_url
                await db.commit()
                logger.info(f"Auto-assigned photo {photo.id} to profile {profile.profile_id} by make/model")
                return photo.image_url

    except Exception as e:
        logger.error(f"Auto-assign photo failed: {e}")

    return None
