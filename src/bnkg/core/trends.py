"""Bounded chart values with explicit source, receipt time and discontinuities."""

import math
from dataclasses import dataclass
from datetime import datetime

from bnkg.core.spectrum import finite


@dataclass(frozen=True)
class TrendPoint:
    timestamp: float
    values: tuple
    origin: str
    state: str
    quality: str
    record_id: int | None = None

    @classmethod
    def create(cls, timestamp, values, origin, state, quality, record_id=None):
        try:
            date = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
            if date.tzinfo is None:
                return None  # Do not guess a timezone for an old/foreign log.
            epoch = date.timestamp()
        except (TypeError, ValueError, AttributeError, OverflowError):
            return None
        if not math.isfinite(epoch):
            return None
        return cls(
            epoch,
            tuple((k, float(v) if finite(v) else None) for k, v in values.items()),
            str(origin),
            str(state),
            str(quality),
            record_id,
        )


def series_points(points, key):
    x, y = [], []
    previous = None
    for point in points:
        if previous and (
            point.origin != previous.origin or not 0 < point.timestamp - previous.timestamp <= 3
        ):
            x.append(point.timestamp)
            y.append(float("nan"))
        value = dict(point.values).get(key)
        x.append(point.timestamp)
        y.append(float(value) if finite(value) else float("nan"))
        previous = point
    return x, y
