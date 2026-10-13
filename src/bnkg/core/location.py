"""Validated location text; never an implicit native GPS write."""

import math

DEFAULT_LATITUDE = ""
DEFAULT_LONGITUDE = ""


def coordinate_text(latitude, longitude):
    try:
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError
        lat, lon = float(latitude), float(longitude)
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Enter decimal latitude -90 to 90 and longitude -180 to 180.") from None
    return f"{lat:.6f}, {lon:.6f}"
