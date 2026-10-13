"""Explicit parameter semantics; no formulas evaluated from input strings."""

import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Parameter:
    id: str
    label: str
    description: str
    source: str = "simulation"
    unit: str = "dB"
    formula: str = ""


PARAMETERS = (
    Parameter("LAeq", "LAeq", "A-weighted equivalent level over the measurement period"),
    Parameter(
        "L10",
        "L10",
        "Instrument configured percentile: level exceeded for 10% of the measurement period",
    ),
    Parameter(
        "L50",
        "L50",
        "Instrument configured percentile: level exceeded for 50% of the measurement period",
    ),
    Parameter(
        "L90",
        "L90",
        "Instrument configured percentile: level exceeded for 90% of the measurement period",
    ),
    Parameter(
        "LCeq_minus_LAeq",
        "LCeq − LAeq",
        "Difference over the same measurement period",
        formula="LCeq - LAeq",
    ),
    Parameter(
        "LAIeq_minus_LAFeq",
        "LAIeq − LAFeq",
        "Difference over the same measurement period",
        formula="LAIeq - LAFeq",
    ),
    Parameter("LAFmax", "LAFmax", "A-weighted Fast maximum; never relabelled as generic LAmax"),
    Parameter("LCpeak", "LCpeak", "C-weighted peak level"),
    Parameter("LAFmin", "LAFmin", "A-weighted Fast minimum; never relabelled as generic LAmin"),
    Parameter("LAF", "LAF", "A-weighted Fast sound level", "/webxi/Applications/SLM/Outputs/LAF"),
    Parameter("LCeq", "LCeq", "C-weighted equivalent level"),
    Parameter("LAIeq", "LAIeq", "A-weighted Impulse equivalent level"),
    Parameter("LAFeq", "LAFeq", "A-weighted Fast equivalent level"),
)
PARAMETERS += tuple(
    Parameter(key, key, "Direct SLM output; available only when configured on the instrument")
    for key in (
        "LCF",
        "LZF",
        "LAS",
        "LCS",
        "LZS",
        "LZeq",
        "LApeak",
        "LZpeak",
        "LASmin",
        "LASmax",
        "LAFTeq",
        "LAE",
        "LCE",
        "LZE",
        "LN1",
        "LN2",
        "LN3",
        "LN4",
        "LN5",
        "StdDev",
    )
)
BY_ID = {item.id: item for item in PARAMETERS}
DEFAULT_VISIBLE = ("LAF",) + tuple(item.id for item in PARAMETERS[:8])


@dataclass(frozen=True)
class Sample:
    timestamp: datetime
    elapsed_s: float
    state: str
    origin: str
    values: dict[str, float | None]
    raw_values: dict[str, float | None]
    quality: str = "valid"
    spectra: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    descriptors: dict = field(default_factory=dict)


def decode_laf(raw: object) -> float:
    """Only the documented LAF hundredths-of-dB conversion is enabled."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise ValueError("LAF response is not a finite numeric value; capture its metadata first.")
    return raw / 100.0


def differences(values: dict[str, float | None]) -> dict[str, float | None]:
    """Caller supplies a single valid, common-period snapshot, never mixed samples."""
    result = dict(values)
    for target, first, second in (
        ("LCeq_minus_LAeq", "LCeq", "LAeq"),
        ("LAIeq_minus_LAFeq", "LAIeq", "LAFeq"),
    ):
        a, b = values.get(first), values.get(second)
        result[target] = (
            a - b
            if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)
            else None
        )
    return result
