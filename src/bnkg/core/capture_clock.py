"""Identity of the current process monotonic clock; never reused after restart."""

from uuid import uuid4

CAPTURE_CLOCK_ID = uuid4().hex
