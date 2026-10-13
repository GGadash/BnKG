"""Explicitly synthetic demo source. No manufacturer response fixtures are invented."""

import math
import random
from datetime import UTC, datetime

from bnkg.core.parameters import Sample, differences
from bnkg.core.safety import require_allowed

DEMO_MODES = ("Smooth", "Ambient", "Events")


class DemoDevice:
    def __init__(self, mode: str = "Smooth", *, seed: int | None = None) -> None:
        if mode not in DEMO_MODES:
            raise ValueError("Unknown demo mode.")
        self.demo_mode = mode
        self.random = random.Random(seed)
        self.ambient = 58.0
        self.elapsed = 0.0
        self.running = True
        self.values: dict[str, float | None] = {}
        self.event_remaining = 0

    def toggle(self) -> None:
        require_allowed("start_pause", simulated=True)
        self.running = not self.running

    def inject_event(self) -> None:
        """A repeatable local illustration, never an instrument command."""
        self.event_remaining = 6

    def read(self) -> Sample:
        if self.running or not self.values:
            self.elapsed += 1.0
            drift = math.sin(self.elapsed / 17.0)
            level = 61.5 + 3.5 * math.sin(self.elapsed / 5.0) + drift
            if self.demo_mode == "Ambient":
                self.ambient += 0.18 * (58.0 - self.ambient) + self.random.gauss(0, 0.9)
                level = self.ambient + self.random.uniform(-0.5, 0.5)
            elif self.demo_mode == "Events":
                phase = self.elapsed % 40
                level = 49 + self.random.uniform(-1, 1) + 26 * math.exp(-(((phase - 15) / 4) ** 2))
            if self.event_remaining:
                level += 18 * self.event_remaining / 6
                self.event_remaining -= 1
            self.values = differences(
                {
                    "LAF": level,
                    "LAeq": 62.4 + drift,
                    "LCeq": 69.6 + drift,
                    "LAIeq": 65.1 + drift,
                    "LAFeq": 62.1 + drift,
                    "L10": 66.8 + drift,
                    "L50": 61.2 + drift,
                    "L90": 54.8 + drift,
                    "LAFmax": 72.6,
                    "LCpeak": 91.3,
                    "LAFmin": 49.7,
                }
            )
        return Sample(
            datetime.now(UTC),
            self.elapsed,
            "Running" if self.running else "Paused",
            "simulation",
            dict(self.values),
            {},
            "synthetic",
        )

    def close(self) -> None:
        pass
