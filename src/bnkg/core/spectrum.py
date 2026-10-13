"""Immutable display snapshots and conservative spectrum semantics; no acoustic synthesis."""

import json
import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SpectrumMeaning:
    kind: str
    quantity: str
    weighting: str
    period_ms: float | None = None
    output_ms: float | None = None
    basis: str = ""

    @property
    def label(self):
        if self.kind == "total":
            return f"{self.quantity} · whole-measurement Leq"
        if self.kind == "current":
            pacing = f" · {self.output_ms:g} ms output" if self.output_ms else ""
            return f"{self.quantity} · current time-weighted{pacing}"
        if self.kind == "interval":
            return f"{self.quantity} · {self.period_ms:g} ms interval Leq"
        return f"{self.quantity} · period/type unverified"


def spectrum_meaning(key, spectrum):
    d = spectrum.get("descriptor", {})
    quantity = str(d.get("LocalName") or key.removeprefix("CPB").removesuffix("250ms"))
    weight = str(d.get("AcousticalWeighting", ""))
    match = re.fullmatch(r"CPBL([ACZ])(eq|F|S|I)(?:2nd)?(250ms)?", key)
    if match and weight and weight != match[1]:
        return SpectrumMeaning("unknown", quantity, weight)
    if not weight and match:
        weight = match[1]
    # Explicit application-normalized interval metadata is separate from output PeriodTime.
    # Future adapters must provide verified integration duration and its evidence basis.
    interval = spectrum.get("integration_interval_ms")
    basis = spectrum.get("integration_basis", "")
    if (
        d.get("FunctionType") == "OctaveLeq"
        and isinstance(interval, (int, float))
        and not isinstance(interval, bool)
        and math.isfinite(interval)
        and interval > 0
        and isinstance(basis, str)
        and basis
    ):
        return SpectrumMeaning("interval", quantity, weight, float(interval), basis=basis)
    if match and match[2] == "eq" and not match[3] and d.get("FunctionType") == "OctaveLeq":
        return SpectrumMeaning("total", quantity, weight, basis="SLM cumulative Outputs node")
    if (
        match
        and match[2] in {"F", "S", "I"}
        and d.get("FunctionType") == "OctaveL"
        and d.get("AveragingMode") == {"F": "Fast", "S": "Slow", "I": "Impulse"}[match[2]]
    ):
        output_ms = 250.0 if match[3] and d.get("PeriodTime") == 1073741824 else None
        return SpectrumMeaning(
            "current",
            quantity,
            weight,
            output_ms=output_ms,
            basis="SLM time-weighted Outputs node; not interval Leq",
        )
    return SpectrumMeaning("unknown", quantity, weight)


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class SpectrumSeries:
    key: str
    frequencies: tuple[float, ...]
    values: tuple[float | None, ...]
    meaning: SpectrumMeaning
    origin: str
    descriptor_json: str
    calculation: str = ""

    @property
    def descriptor(self):
        return json.loads(self.descriptor_json)

    @property
    def label(self):
        origin = {"instrument": "SLM", "simulation": "Synthetic", "calculated": "Calculated"}.get(
            self.origin, "Unverified source"
        )
        fractions = self.descriptor.get("DataAxisCpbNumberFractions", "?")
        return f"{origin} · {self.meaning.label} · 1/{fractions} octave · {self.key}"

    def compatible(self, other):
        return (
            self.meaning.kind != "unknown"
            and self.meaning.kind == other.meaning.kind
            and self.meaning.period_ms == other.meaning.period_ms
            and self.meaning.output_ms == other.meaning.output_ms
            and self.meaning.basis == other.meaning.basis
            and self.frequencies == other.frequencies
            and self.origin == other.origin
            and self.descriptor.get("PeriodTime") == other.descriptor.get("PeriodTime")
            and self.descriptor.get("Unit") == other.descriptor.get("Unit")
            and self.descriptor.get("FunctionType") == other.descriptor.get("FunctionType")
            and self.descriptor.get("AveragingMode") == other.descriptor.get("AveragingMode")
        )

    def as_dict(self):
        return {
            "frequencies": list(self.frequencies),
            "values": list(self.values),
            "descriptor": self.descriptor,
            "origin": self.origin,
            "calculation": self.calculation,
            "integration_interval_ms": self.meaning.period_ms,
            "integration_basis": self.meaning.basis if self.meaning.kind == "interval" else "",
        }


@dataclass(frozen=True)
class SpectrumFrame:
    series: tuple[SpectrumSeries, ...] = ()
    broadband: tuple[tuple[str, float | None], ...] = ()
    timestamp: str = ""
    state: str = ""
    quality: str = ""
    # Internal JSON copies retain even invalid raw metadata; display values are sanitized separately.
    measurement_json: str = "{}"

    @classmethod
    def capture(
        cls, spectra, *, broadband=None, timestamp="", state="", quality="", measurement=None
    ):
        result = []
        for key, item in sorted(spectra.items()):
            f, v = item.get("frequencies", []), item.get("values", [])
            if (
                not 1 <= len(f) <= 128
                or len(f) != len(v)
                or not all(finite(x) and x > 0 for x in f)
                or not all(a < b for a, b in zip(f, f[1:], strict=False))
            ):
                continue
            result.append(
                SpectrumSeries(
                    str(key),
                    tuple(f),
                    tuple(float(x) if finite(x) else None for x in v),
                    spectrum_meaning(key, item),
                    str(item.get("origin", "unknown")),
                    json.dumps(item.get("descriptor", {})),
                    str(item.get("calculation", "")),
                )
            )
        return cls(
            tuple(result),
            tuple((k, float(v) if finite(v) else None) for k, v in (broadband or {}).items()),
            str(timestamp),
            str(state),
            str(quality),
            json.dumps(measurement or {}),
        )
