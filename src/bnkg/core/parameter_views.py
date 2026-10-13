"""Local scalar catalogue groups and bounded visibility preset serialization."""

import json

from bnkg.core.parameters import BY_ID, DEFAULT_VISIBLE, PARAMETERS

GROUPS = (
    "Current levels",
    "Measurement equivalents",
    "Peaks and extrema",
    "Percentiles",
    "Exposure",
    "Statistics",
    "Calculated differences",
)
PRESET_KEY = "parameter_visibility_presets_v1"


def group_for(parameter):
    key = parameter.id
    if parameter.formula:
        return GROUPS[6]
    if key in {"LAF", "LCF", "LZF", "LAS", "LCS", "LZS"}:
        return GROUPS[0]
    if key.endswith("eq"):
        return GROUPS[1]
    if key.endswith(("peak", "min", "max")):
        return GROUPS[2]
    if key in {"L10", "L50", "L90"} or key.startswith("LN"):
        return GROUPS[3]
    if key in {"LAE", "LCE", "LZE"}:
        return GROUPS[4]
    return GROUPS[5]


def visible_ids(values):
    """Normalize legacy preferences without substring matching a singleton string."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        values = DEFAULT_VISIBLE
    return tuple(p.id for p in PARAMETERS if not p.formula and p.id in values)


BUILTINS = {
    "Recommended": visible_ids(DEFAULT_VISIBLE),
    "Current A / C / Z": tuple(p.id for p in PARAMETERS if group_for(p) == GROUPS[0]),
    "Measurement equivalents": tuple(p.id for p in PARAMETERS if group_for(p) == GROUPS[1]),
    "Peaks and extrema": tuple(p.id for p in PARAMETERS if group_for(p) == GROUPS[2]),
    "Configured percentiles": tuple(p.id for p in PARAMETERS if group_for(p) == GROUPS[3]),
}


def preset_name(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 60
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Use a preset name of 1–60 characters without control characters.")
    name = value.strip()
    if name.casefold() in {n.casefold() for n in BUILTINS}:
        raise ValueError("Choose a name different from the built-in presets.")
    return name


def read_presets(encoded):
    if not isinstance(encoded, str) or len(encoded) > 32768:
        raise ValueError("Saved visibility presets exceed the supported size.")
    try:
        data = json.loads(encoded)
    except (ValueError, RecursionError) as exc:
        raise ValueError(
            "Saved visibility presets are invalid; original settings retained."
        ) from exc
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("presets"), list)
        or len(data["presets"]) > 20
    ):
        raise ValueError("Unsupported visibility presets; original settings retained.")
    result, names = {}, set()
    for entry in data["presets"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid visibility preset entry.")
        name = preset_name(entry.get("name"))
        ids = entry.get("ids")
        if (
            name.casefold() in names
            or not isinstance(ids, list)
            or len(ids) > len(PARAMETERS)
            or any(
                not isinstance(key, str) or key not in BY_ID or BY_ID[key].formula for key in ids
            )
            or len(set(ids)) != len(ids)
        ):
            raise ValueError(
                "Unsupported or duplicate preset name/parameter; original settings retained."
            )
        names.add(name.casefold())
        result[name] = visible_ids(ids)
    return result


def write_presets(presets):
    encoded = json.dumps(
        {
            "version": 1,
            "presets": [{"name": name, "ids": list(ids)} for name, ids in presets.items()],
        },
        ensure_ascii=True,
    )
    read_presets(encoded)
    return encoded
