"""Local user-authored report context; never an SLM setup payload."""

import re
import unicodedata
from datetime import UTC, datetime

FIELDS = {"project": 120, "operator": 120, "site": 120, "notes": 2000}


def validate_context(value):
    if not isinstance(value, dict) or set(value) - FIELDS.keys():
        raise ValueError("Local report context contains unknown fields.")
    result = {}
    for key, limit in FIELDS.items():
        text = value.get(key, "")
        if not isinstance(text, str) or len(text) > limit:
            raise ValueError(f"Local {key} must be text of at most {limit} characters.")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError(f"Local {key} contains unsupported control characters.")
        result[key] = text.strip()
    return result


def context_metadata(value):
    fields = validate_context(value)
    return {
        "local_report.source": "User-entered local context; not instrument metadata or a verified location",
        "local_report.captured_utc": datetime.now(UTC).isoformat(),
        **{"local_report." + key: text for key, text in fields.items()},
    }


def log_filename(context, named=False, now=None):
    fields = validate_context(context)
    parts = ["BnKG-LocalLog-instrument"]
    if named:
        for key in ("project", "site"):
            text = unicodedata.normalize("NFKD", fields[key]).encode("ascii", "ignore").decode()
            text = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-_")[:36]
            if text:
                parts.append(text)
    parts.append((now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S-%fZ"))
    return "-".join(parts) + ".sqlite"


def metadata_group(key):
    if key.startswith("Metadata"):
        return "SLM metadata slots"
    if key.startswith("Device."):
        return "Battery and storage"
    if key.startswith(("Transducer", "Sensitiv", "Calibrat")):
        return "Transducer and calibration"
    if key in {
        "Latitude",
        "Longitude",
        "Altitude",
        "LatitudePrecision",
        "LongitudePrecision",
        "AltitudePrecision",
        "ServiceGpsLocation",
    }:
        return "Location"
    if key in {
        "WindDirection",
        "WindSpeed",
        "Temperature",
        "Humidity",
        "Pressure",
        "Rainfall",
        "WeatherStation",
    }:
        return "Weather"
    if key in {"SerialNumber", "HWVersion", "SWVersion"}:
        return "Identity"
    return "Measurement and setup"
