# Fixture provenance

No real 2255 or 2245 response fixture has been captured yet. Test payloads are deliberately minimal synthetic protocol shapes, not claims about an actual device tree. Demo data is generated locally and labelled simulation.

When hardware is available, use the read-only probe to capture responses into ignored `local-data/`. Review and sanitize device IP, serial, hostname and any private metadata before adding selected fixtures under `2255/` or `2245/`. Record model, firmware, date and licence/capability context with each set. Do not replace synthetic tests with unsanitized captures.
