"""Fail-closed policy. Only explicitly armed and verified measurement controls are implemented."""

from dataclasses import dataclass
from enum import IntEnum


class SafetyLevel(IntEnum):
    READ_ONLY = 0
    ROUTINE = 1
    CONSEQUENTIAL = 2
    HIGH_IMPACT = 3
    BLOCKED = 4


@dataclass(frozen=True)
class Decision:
    level: SafetyLevel
    allowed: bool
    reason: str


def classify(operation: str, *, simulated: bool = False) -> Decision:
    if operation in {"read", "export", "snapshot"}:
        return Decision(SafetyLevel.READ_ONLY, True, "Read-only or local output operation.")
    if simulated and operation == "start_pause":
        return Decision(SafetyLevel.ROUTINE, True, "Changes the simulator only.")
    if operation == "screen_navigation":
        return Decision(
            SafetyLevel.CONSEQUENTIAL,
            True,
            "Single advertised arrow key within an acknowledged measurement-view session; "
            "menu/settings navigation is not authorized by this operation.",
        )
    if operation == "open_screen_menu":
        return Decision(
            SafetyLevel.ROUTINE,
            True,
            "Open menu only from an acknowledged measurement view; lock keypad afterward.",
        )
    if operation == "configure_audio_analysis":
        return Decision(
            SafetyLevel.CONSEQUENTIAL,
            True,
            "Only the reviewed Analysis quality 0/1 setting while idle; explicit preview, confirmations and read-back.",
        )
    if operation == "receive_audio_stream":
        return Decision(
            SafetyLevel.ROUTINE,
            True,
            "One explicitly confirmed FromDevice audio stream; close only the owned connection/resource.",
        )
    if operation == "identify":
        return Decision(
            SafetyLevel.ROUTINE, True, "Explicit display/light-ring identification pulse."
        )
    if operation == "start_pause":
        return Decision(SafetyLevel.ROUTINE, True, "Explicit measurement start/pause only.")
    if operation == "write_location_metadata":
        return Decision(
            SafetyLevel.CONSEQUENTIAL,
            True,
            "One selected enabled text-slot value; preview, two confirmations and read-back required.",
        )
    if operation == "stop_measurement":
        return Decision(
            SafetyLevel.CONSEQUENTIAL,
            True,
            "Deliberate armed measurement Stop; no repeated confirmation.",
        )
    return Decision(
        SafetyLevel.BLOCKED,
        False,
        "This instrument operation is not enabled. Use the physical SLM. "
        "Unknown, calibration and service operations are blocked.",
    )


def require_allowed(operation: str, *, simulated: bool = False) -> None:
    decision = classify(operation, simulated=simulated)
    if not decision.allowed:
        raise PermissionError(decision.reason)
