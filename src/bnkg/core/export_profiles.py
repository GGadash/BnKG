"""Local export configurations and content descriptions; no file or device access."""

import json
from dataclasses import asdict, dataclass

from bnkg.core.parameters import BY_ID, PARAMETERS

FORMATS = ("csv", "xlsx", "tsv", "txt", "json", "ndjson", "html")
SPECTRAL = {"json", "ndjson", "xlsx", "html"}
RAW = {"json", "ndjson"}
KEY = "export_profiles_v1"
ALL_IDS = tuple(p.id for p in PARAMETERS)


@dataclass(frozen=True)
class ExportProfile:
    format_name: str
    parameter_ids: tuple[str, ...]
    include_spectra: bool = False
    include_raw: bool = False

    def options(self):
        return {
            "parameter_ids": list(self.parameter_ids),
            "include_spectra": self.include_spectra,
            "include_raw": self.include_raw,
        }


def profile(format_name, ids, spectra=False, raw=False):
    if (
        format_name not in FORMATS
        or not isinstance(ids, (list, tuple))
        or not ids
        or len(ids) > len(ALL_IDS)
        or any(not isinstance(key, str) or key not in BY_ID for key in ids)
        or len(set(ids)) != len(ids)
        or type(spectra) is not bool
        or type(raw) is not bool
    ):
        raise ValueError(
            "Choose a supported format and at least one known, unique scalar parameter."
        )
    return ExportProfile(
        format_name,
        tuple(key for key in ALL_IDS if key in ids),
        spectra and format_name in SPECTRAL,
        raw and format_name in RAW,
    )


BUILTINS = {
    "Scalar table": profile("csv", ALL_IDS),
    "Structured spectra": profile("json", ALL_IDS, True),
    "Workbook with spectra": profile("xlsx", ALL_IDS, True),
    "Measurement report": profile("html", ALL_IDS, True),
}


def name_for(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 60
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Use a name of 1–60 characters without control characters.")
    name = value.strip()
    if name.casefold() in {key.casefold() for key in BUILTINS}:
        raise ValueError("Choose a name different from the built-in export presets.")
    return name


def decode_profiles(encoded):
    if not isinstance(encoded, str) or len(encoded) > 32768:
        raise ValueError("Export presets exceed the supported settings size.")
    try:
        data = json.loads(encoded)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid saved export presets; original settings retained.") from exc
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("presets"), list)
        or len(data["presets"]) > 20
    ):
        raise ValueError("Unsupported export presets; original settings retained.")
    result, names = {}, set()
    for entry in data["presets"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "profile"}:
            raise ValueError("Unsupported export preset entry.")
        name = name_for(entry["name"])
        options = entry["profile"]
        if (
            name.casefold() in names
            or not isinstance(options, dict)
            or set(options) != {"format_name", "parameter_ids", "include_spectra", "include_raw"}
        ):
            raise ValueError("Duplicate or unsupported export preset.")
        value = profile(
            options["format_name"],
            options["parameter_ids"],
            options["include_spectra"],
            options["include_raw"],
        )
        if (
            value.include_spectra != options["include_spectra"]
            or value.include_raw != options["include_raw"]
        ):
            raise ValueError("Preset requests content unsupported by its format.")
        result[name] = value
        names.add(name.casefold())
    return result


def encode_profiles(profiles):
    encoded = json.dumps(
        {
            "version": 1,
            "presets": [{"name": key, "profile": asdict(value)} for key, value in profiles.items()],
        },
        ensure_ascii=True,
    )
    decode_profiles(encoded)
    return encoded


def describe(value):
    fmt = value.format_name
    ids = value.parameter_ids
    lines = [
        f"{fmt.upper()} · {len(ids)} selected scalar parameters",
        "Parameters: " + ", ".join(ids),
        "Every sample: PC UTC receipt time, connection elapsed seconds, state, origin and quality.",
    ]
    if fmt in {"csv", "tsv", "txt"}:
        lines.append(
            "Scalar table only. "
            + ("Comma-separated." if fmt == "csv" else "Tab-separated.")
            + " No session metadata, parameter catalogue, events, raw context or band spectra."
        )
        if any(BY_ID[key].formula for key in ids):
            lines.append(
                "Calculated columns: "
                + "; ".join(key + " = " + BY_ID[key].formula for key in ids if BY_ID[key].formula)
                + ". Flat files contain recorded results; formula details are not embedded."
            )
    else:
        lines.append(
            "Includes session metadata (including stored local report details) and the selected parameter catalogue/formulas. Review private metadata before sharing."
        )
        lines.append(
            "Includes the Events sheet."
            if fmt == "xlsx"
            else "Session event records are not included in this format."
        )
        if fmt in RAW and set(ids) == set(ALL_IDS):
            lines.append(
                "All catalogue parameters selected: JSON/NDJSON also preserve any additional stored scalar keys."
            )
        lines.append(
            "Direct spectra: "
            + (
                "requested where retained descriptors allow decoding; includes axes, quantity/weighting/time basis, descriptors, measurement context and matching broadband values. Not limited by scalar selection."
                if value.include_spectra
                else "not included as decoded band series."
            )
        )
        lines.append(
            "Stored raw outputs/context: "
            + (
                "included independently of scalar selection; may contain unselected values, spectra and private metadata."
                if value.include_raw
                else "not included as a raw payload. Session metadata and any requested spectral context still remain."
            )
        )
    lines.append(
        "Local review markers/Exclude labels are not merged or applied. No recalculation, weighting synthesis or inferred integration intervals."
    )
    lines.append(
        "Options preview only; this preview does not inspect source contents or guarantee spectrum availability. Export validates a consistent database snapshot. Later logged rows are excluded; existing destinations are preserved."
    )
    return "\n\n".join(lines)
