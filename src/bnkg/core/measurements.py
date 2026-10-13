"""Decode device descriptors without deriving replacement measurement values."""

import math
import re

METADATA_FIELDS = {
    "Latitude",
    "Longitude",
    "Altitude",
    "LatitudePrecision",
    "LongitudePrecision",
    "AltitudePrecision",
    "SerialNumber",
    "HWVersion",
    "SWVersion",
    "TimeZone",
    "Transducer",
    "Sensitivity",
    "Calibrated",
    "ElapsedTime",
    "StartTime",
    "StopTime",
    "SLMTime",
    "MeasurementCounter",
    "Overload",
    "LatchedOverload",
    "Underrange",
    "WindDirection",
    "WindSpeed",
    "Temperature",
    "Humidity",
    "Pressure",
    "Rainfall",
}
SETUP_FIELDS = re.compile(
    r"(?:Metadata(?:All|[1-9](?:Metadata|Name|Text|Type|Number|Picklist(?:Entry(?:[1-9]|1[01]))?)?)|StatisticsPercentile[1-5]|BBStatisticsBasedOn|FrequencyCPBBandwidth(?:2nd)?|FrequencyRange|ServiceGpsLocation|WeatherStation|Transducer(?:Sensitivity|NomSensitivity|Type|Serialno|PreampType|PreampSerialNo))$"
)


def sequence_index(tree):
    result = {}

    def visit(node):
        if not isinstance(node, dict):
            return
        if isinstance(node.get("Name"), str) and "DataType" in node:
            result[node["Name"]] = node
        else:
            for child in node.values():
                visit(child)

    visit(tree)
    return result


def level(raw, descriptor):
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return None
    # The tested Int16 interface uses its minimum value to indicate no result.
    if descriptor.get("DataType") != "Int16" or not -32768 < raw <= 32767:
        return None
    scale = descriptor.get("Scale")
    offset = descriptor.get("Offset", 0)
    if not isinstance(scale, (int, float)) or not isinstance(offset, (int, float)):
        return None
    if descriptor.get("IsPower", False) or not str(descriptor.get("Unit", "")).startswith("dB"):
        return None
    value = raw * scale + offset
    return value if math.isfinite(value) else None


def band_centres(descriptor):
    # Base-10 CPB axis: band index advances by 3 / octave fractions.
    # Matches HBK's normal-range example, extended using advertised first band.
    count = descriptor.get("VectorLength")
    first = descriptor.get("DataAxisCpbFirstBand")
    fractions = descriptor.get("DataAxisCpbNumberFractions")
    if (
        descriptor.get("DataAxisType") != "CPB"
        or descriptor.get("DataAxisCpbBaseSystem") != 10
        or fractions not in (1, 3)
        or not isinstance(first, int)
        or not isinstance(count, int)
        or not 1 <= count <= 128
        or not -30 <= first <= 60
    ):
        return []
    return [10 ** (0.1 * (first + i * 3 / fractions)) for i in range(count)]


def decode_outputs(outputs, sequences, setup):
    values, spectra = {}, {}
    for key, raw in outputs.items():
        descriptor = sequences.get(key)
        # REST exposes the 250 ms current CPB outputs with a suffix.
        if descriptor is None and key.endswith("250ms"):
            candidate = sequences.get(key[:-5], {})
            if candidate.get("PeriodTime") == 1073741824:
                descriptor = candidate
        if not descriptor:
            continue
        if isinstance(raw, list):
            frequencies = band_centres(descriptor)
            if frequencies and len(frequencies) == len(raw):
                spectra[key] = {
                    "frequencies": frequencies,
                    "values": [level(v, descriptor) for v in raw],
                    "descriptor": descriptor,
                    "origin": "instrument",
                }
        elif str(descriptor.get("Unit", "")).startswith("dB"):
            values[key] = level(raw, descriptor)
    # Only name an LN slot by the device's configured percentile; retain its basis.
    for slot in range(1, 6):
        percentile = setup.get(f"StatisticsPercentile{slot}")
        if percentile in (10, 50, 90):
            values[f"L{int(percentile)}"] = values.get(f"LN{slot}")
    return values, spectra


def metadata_snapshot(outputs, setup, setup_metadata):
    fields = {}
    for key in sorted(METADATA_FIELDS & outputs.keys()):
        raw = outputs[key]
        invalid = isinstance(raw, (int, float)) and (not math.isfinite(raw) or abs(raw) > 1e300)
        fields[key] = {
            "value": None if invalid else raw,
            "raw": raw,
            "access": "Read-only output",
            "description": "SLM output; original units/format (elapsed time is raw device ticks).",
        }
    for key, raw in setup.items():
        if SETUP_FIELDS.fullmatch(key):
            meta = setup_metadata.get(key, {}).get("Metadata", {})
            fields[key] = {
                "value": raw,
                "raw": raw,
                "access": "Read-only on device"
                if "ReadOnly" in meta.get("Flags", "")
                else (
                    "Device advertises writable; use physical SLM"
                    if "DataType" in meta and "Flags" in meta
                    else "Access unknown; no writes allowed"
                ),
                "description": meta.get("Description", ""),
                "domain": meta.get("Domain"),
                "unit": meta.get("DisplayHint", ""),
            }
    return fields


def device_health_fields(values, definitions, group, observed_utc):
    """Only the verified, read-only Battery/Disks trees; never broad identity data."""
    if group not in {"Battery", "Disks"}:
        raise ValueError("Unknown device health group")
    result = {}
    if not isinstance(values, dict) or not isinstance(definitions, dict):
        return result
    for key, raw in values.items():
        meta = definitions.get(key, {}).get("Metadata", {})
        if "ReadOnly" not in meta.get("Flags", "") or isinstance(raw, (dict, list)):
            continue
        result[f"Device.{group}.{key}"] = {
            "value": raw,
            "raw": raw,
            "access": "Read-only device status",
            "description": meta.get("Description", "")
            + f" Last read (PC UTC): {observed_utc}. Refreshed about every 5 s.",
            "domain": meta.get("Domain"),
            "unit": meta.get("DisplayHint", ""),
            "observed_utc": observed_utc,
        }
    return result


def metadata_text(field):
    value = field.get("value")
    if value is None:
        return "Unavailable"
    domain = (field.get("domain") or {}).get("List", {})
    values, names = domain.get("Values", []), domain.get("Names", [])
    if value in values and values.index(value) < len(names):
        text = f"{value} ({names[values.index(value)]})"
    else:
        text = str(value)
    unit = field.get("unit", "")
    return f"{text} {unit}" if unit else text
