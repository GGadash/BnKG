"""Conservative BKC container/descriptor/raw-row reader for the observed SLM layout.

This module does not invent acoustic scaling, sentinel rules or measurement scope.
Raw decoding is distinct from a validated calibrated measurement import.
"""

import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_FILE = 32 * 1024 * 1024


def xml_root(data):
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("BKC XML exceeds 4 MiB")
    text = data.decode("utf-8-sig", errors="strict")
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("BKC XML entities/DTDs are not allowed")
    root = ET.fromstring(text)
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 32 or count > 12000:
            raise ValueError("BKC XML complexity limit exceeded")
        stack.extend((child, depth + 1) for child in node)
    return root


def read_bkc(path, *, cancelled=lambda: False):
    path = Path(path)
    if not 14 <= path.stat().st_size <= MAX_FILE:
        raise ValueError("BKC must be between 14 bytes and 32 MiB")
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("BKC grew beyond size limit")
    if cancelled():
        raise InterruptedError("BKC inspection cancelled")
    magic, version, count = struct.unpack_from("<III", data)
    if magic != 0x72E176FB or version != 0 or not 1 <= count <= 64:
        raise ValueError("Unsupported BKC container signature/version/part count")
    position = 12
    parts = {}

    def take(size):
        nonlocal position
        if size < 0 or position + size > len(data):
            raise ValueError("Truncated BKC directory")
        value = data[position : position + size]
        position += size
        return value

    for _ in range(count):
        length = struct.unpack("<H", take(2))[0]
        if length > 128:
            raise ValueError("BKC part name too long")
        name = take(length * 2).decode("utf-16-le", errors="strict")
        if name and not re.fullmatch(r"\.Part[0-9]+(?:\.[A-Za-z0-9_-]+)*", name):
            raise ValueError("Unsafe or unsupported BKC part name")
        offset, size = struct.unpack("<QQ", take(16))
        if name in parts or size == 0 or offset + size > len(data):
            raise ValueError("Duplicate or out-of-bounds BKC part")
        parts[name] = {"offset": offset, "bytes": size}
    end = position
    for part in sorted(parts.values(), key=lambda p: p["offset"]):
        if part["offset"] != end:
            raise ValueError("BKC parts overlap or contain an unsupported gap")
        end += part["bytes"]
    if end != len(data) or "" not in parts:
        raise ValueError("BKC root/trailing data mismatch")

    def content(name):
        p = parts[name]
        return data[p["offset"] : p["offset"] + p["bytes"]]

    root = xml_root(content(""))
    if root.tag != "Storage" or root.get("Version") != "2":
        raise ValueError("Unsupported BKC Storage XML version")
    # Hash checks establish consistency, not trust in the embedded certificate/signature.
    hash_checks = []
    for entry in root.findall("Signature/File"):
        name = (entry.text or "").strip()
        if name and name in parts and entry.get("Type") == "SHA256":
            match = (
                hashlib.sha256(content(name)).hexdigest().lower() == entry.get("Value", "").lower()
            )
            if not match:
                raise ValueError("BKC part hash mismatch")
            hash_checks.append(name)
    tables = root.findall("ClockSource/Table")
    if len(tables) != 1:
        raise ValueError("Only the observed single-table BKC layout is supported")
    table = tables[0]
    descriptors = {}
    for node in table.findall("Sequence"):
        sid = int(node.get("Id", "-1"))
        if not 0 < sid < 65536 or sid in descriptors:
            raise ValueError("Invalid/duplicate BKC sequence ID")
        descriptors[sid] = node
    if len(descriptors) > 256:
        raise ValueError("Too many BKC descriptors")
    raw_rows = []
    decoded = set()
    for name in parts:
        if cancelled():
            raise InterruptedError("BKC inspection cancelled")
        if not re.fullmatch(r"\.Part[0-9]+", name):
            continue
        binary = content(name)
        if len(binary) < 32:
            raise ValueError("Truncated BKC table")
        signature, table_version, r1, r2, r3, r4, records, columns = struct.unpack_from(
            "<8I", binary
        )
        if (signature, table_version, r1, r2, r3, r4, records) != (
            0x1A2B3C4D,
            0,
            0,
            0,
            0,
            0,
            1,
        ) or not 1 <= columns <= 256:
            raise ValueError(
                "Unsupported BKC table header (only observed single-record layout supported)"
            )
        header_end = 32 + columns * 20
        if header_end > len(binary):
            raise ValueError("Truncated BKC column directory")
        offset = header_end
        for i in range(columns):
            sid, reserved, width, length = struct.unpack_from("<IQII", binary, 32 + i * 20)
            node = descriptors.get(sid)
            if node is None or sid in decoded or node.findtext("File") != name or reserved != 0:
                raise ValueError("BKC column/descriptor mismatch")
            dtype = node.get("DataType")
            formats = {"Int16": ("h", 2), "Double": ("d", 8)}
            if dtype not in formats or width != formats[dtype][1] or not 1 <= length <= 128:
                raise ValueError("Unsupported BKC column data type/width/length")
            if (
                node.findtext("IndexMapping/Type") != "Explicit"
                or int(node.findtext("DataAxis/Length", "1")) != length
            ):
                raise ValueError("BKC descriptor dimension/index mismatch")
            size = width * length
            if offset + size > len(binary):
                raise ValueError("Truncated BKC values")
            raw = binary[offset : offset + size]
            offset += size
            values = list(struct.unpack("<" + formats[dtype][0] * length, raw))
            values = [v if not isinstance(v, float) or math.isfinite(v) else None for v in values]
            raw_rows.append(
                {
                    "sequence_id": sid,
                    "name": node.get("Name"),
                    "data_type": dtype,
                    "raw_values": values,
                    "raw_hex": raw.hex(),
                    "part": name,
                    "descriptor_xml": ET.tostring(node, encoding="unicode"),
                    "function": node.findtext("General/FunctionType"),
                    "weighting": node.findtext("AcousticalWeighting/AcousticalWeighting"),
                    "time_weighting": node.findtext("Averaging/AveragingMode"),
                    "interpretation": "Raw instrument storage values; scale/units/invalid sentinels and measurement basis not independently validated",
                }
            )
            decoded.add(sid)
        if offset != len(binary):
            raise ValueError("Unsupported extra BKC table data")
    expected = {
        sid for sid, n in descriptors.items() if n.findtext("IndexMapping/Type") == "Explicit"
    }
    if decoded != expected:
        raise ValueError("BKC explicit sequences do not match decoded columns")
    constants = []
    for sid, node in descriptors.items():
        if node.findtext("IndexMapping/Type") == "Constant":
            constants.append(
                {
                    "sequence_id": sid,
                    "name": node.get("Name"),
                    "data_type": node.get("DataType"),
                    "raw_value": node.findtext("IndexMapping/InitialValue"),
                }
            )
    module = root.find("MeasurementChain/Configuration/Frame/Module")
    clock = root.find("ClockSource")
    context = {
        "instrument_type": module.get("Type") if module is not None else None,
        "firmware": module.get("SoftwareVersion") if module is not None else None,
        "time_powers": [
            int(clock.findtext("Family/Power" + str(base), "0")) for base in (2, 3, 5, 7)
        ]
        if clock is not None
        else [],
        "primary_sequence_id": table.findtext("PrimarySequenceId"),
    }
    return {
        "context": context,
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "container_version": version,
        "storage_version": "2",
        "parts": parts,
        "checked_part_hashes": hash_checks,
        "signature_authenticity": "Not verified",
        "status": "raw decoded; calibrated import awaiting independent comparison",
        "raw_rows": raw_rows,
        "constants": constants,
        "start_time_text": table.findtext("StartTime/DateTimeUtc"),
        "validation_needed": "Matching manufacturer CSV/XLSX export plus reliable scale, sentinel, band-axis and measurement-period definitions. No A/C synthesis or dB conversion applied.",
    }


def save_raw_report(result, path):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)


# This narrow profile is supported by two independent ENP/NP XLSX comparisons:
# 15 broadband plus 36 A and 36 Z bands each, all 174 values exact at 0.01 dB.
# Unsupported firmware/types/layouts remain raw-only instead of using this profile.
VALIDATED_NAMES = {
    "LAeq": "BroadbandLeq",
    "LZeq": "BroadbandLeq",
    "LAIeq": "BroadbandLAIeq",
    "LAFmax": "BroadbandLmax",
    "LASmax": "BroadbandLmax",
    "LAFmin": "BroadbandLmin",
    "LASmin": "BroadbandLmin",
    "LCpeak": "BroadbandLpeak",
    "LZeqTaiSIL": "BroadbandLeq",
    "StdDev": "None",
    **{f"LN{i}": "BroadbandLN" for i in range(1, 6)},
    "CPBLZeq": "OctaveLeq",
    "CPBLAeq2nd": "OctaveLeq",
}


def decode_total(result):
    """Decode only the independently compared 2255 total-results profile."""
    from bnkg.core.spectrum import SpectrumFrame, SpectrumMeaning, SpectrumSeries

    context = result.get("context", {})
    if (
        context.get("instrument_type"),
        context.get("firmware"),
        context.get("time_powers"),
        context.get("primary_sequence_id"),
    ) != ("2255", "1.3.0.478", [32, 0, 0, 0], "140"):
        return None
    constants = {r["name"]: r for r in result["constants"]}
    if not {"ElapsedTime", "StopTime", "LatchedOverload"} <= constants.keys():
        return None
    if any(constants[k]["data_type"] != "BKTimeSpan" for k in ("ElapsedTime", "StopTime")):
        return None
    elapsed = int(constants["ElapsedTime"]["raw_value"]) / (2**32)
    wall = int(constants["StopTime"]["raw_value"]) / (2**32)
    if not 0 < elapsed <= wall or not math.isfinite(wall):
        return None
    scalar = {}
    series = []
    rows = []
    for raw in result["raw_rows"]:
        name = raw["name"]
        node = ET.fromstring(raw["descriptor_xml"])
        if (
            name not in VALIDATED_NAMES
            or raw["data_type"] != "Int16"
            or raw["function"] != VALIDATED_NAMES[name]
        ):
            continue
        # Reserved end points are withheld, not presented as enormous dB values.
        values = [v / 100 if -32768 < v < 32767 else None for v in raw["raw_values"]]
        description = node.findtext("General/Description", name)
        descriptor = {
            "Name": name,
            "LocalName": description,
            "DataType": "Int16",
            "Scale": 0.01,
            "Offset": 0,
            "Unit": "dB",
            "FunctionType": raw["function"],
            "AcousticalWeighting": raw["weighting"],
            "AveragingMode": raw["time_weighting"],
            "raw_values": raw["raw_values"],
            "source": "BKC instrument-stored values",
            "measurement_elapsed_s": elapsed,
            "conversion_basis": "2255 FW 1.3.0.478 total profile; 174 exact ENP/NP XLSX comparison values",
            "original_descriptor_xml": raw["descriptor_xml"],
        }
        if name.startswith("CPB"):
            axis = node.find("DataAxis")
            if axis is None or (
                axis.findtext("Type"),
                axis.findtext("Length"),
                axis.findtext("CpbFirstBand"),
                axis.findtext("CpbNumberFractions"),
                len(values),
            ) != ("Cpb", "36", "8", "3", 36):
                continue
            weight = "A" if name == "CPBLAeq2nd" else "Z"
            if raw["weighting"] != weight:
                continue
            descriptor.update(
                DataAxisCpbNumberFractions=3,
                DataAxisCpbFirstBand=8,
                DataAxisCpbBaseSystem=10,
                DataAxisType="CPB",
                VectorLength=36,
            )
            series.append(
                SpectrumSeries(
                    name,
                    tuple(10 ** (0.1 * (8 + i)) for i in range(36)),
                    tuple(values),
                    SpectrumMeaning(
                        "total", f"L{weight}eq", weight, basis="BKC stored measurement total"
                    ),
                    "instrument",
                    json.dumps(descriptor),
                )
            )
        elif len(values) == 1:
            scalar[name] = values[0]
            descriptor["Percentile"] = node.findtext("Percentile/Percentile")
        else:
            continue
        rows.append(
            {
                "name": name,
                "description": description,
                "values": values,
                "unit": "dB",
                "descriptor": descriptor,
            }
        )
    if not series and not scalar:
        return None
    quality = f"Stored latched quality raw {constants['LatchedOverload']['raw_value']}; signature authenticity not verified"
    provenance = {
        "bkc_sha256": result["sha256"],
        "source_file": result["file"],
        "origin": "instrument",
        "measurement_elapsed_s": elapsed,
        "wall_duration_s": wall,
        "scope": "whole measurement total",
        "validation_profile": "2255-1.3.0.478-total-v1",
        "unsupported_sequences": "Remain raw-only",
        "comparison": "Two manufacturer ENP/NP XLSX exports; 174 matching values; no weighting synthesis",
        "quality": quality,
    }
    frame = SpectrumFrame(
        tuple(series),
        tuple(scalar.items()),
        result["start_time_text"] or "",
        "Saved measurement total",
        quality,
        json.dumps(provenance),
    )
    return {"rows": rows, "frame": frame, "provenance": provenance, "elapsed_s": elapsed}
