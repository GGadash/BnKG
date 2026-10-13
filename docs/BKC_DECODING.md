# Native BKC inspection and saved totals

Open **Sessions & export → Native BKC → Open BKC…** and select a local `.bkc` file. Reading runs in a background worker and does not contact the meter or change the source file. Use **Load saved A/Z spectra in Frequency** for supported totals. Live acquisition continues independently; the saved spectrum remains frozen. **Save raw inspection JSON…** preserves raw numbers/bytes, descriptors, part hashes and supported decoded totals in a new file without overwriting an existing file.

## Supported evidence profile

The first decoder supports the observed version-0 BKC container, Storage 2 XML and one-record Int16/Double binary table. Conversion to dB is restricted to the **2255, firmware 1.3.0.478, total-results profile** with verified clock, primary sequence and descriptors. Recognized Int16 acoustic values use 0.01 dB per unit. Supported results include 15 broadband quantities and direct 36-band A/Z Leq spectra (nominal 6.3 Hz–20 kHz). It does not synthesize C bands or derive A from Z.

Whole-measurement totals use the stored elapsed integration time, with wall duration retained separately. They are not current Fast values or 125 ms interval Leq. Negative A-weighted band levels remain negative. The two Int16 endpoints are withheld rather than displayed as extreme levels; broader sentinel and validity semantics remain unverified. Latched quality is retained as a raw flag, not interpreted as certification. Part hashes are checked when supplied; certificate/signature authenticity is not verified.

Two user-supplied ENP/NP projects contained native measurements matching their manufacturer XLSX exports. Comparison covered **174 values: 30 broadband and 144 A/Z band results**, all exactly equal at the stored 0.01 dB precision. The two standalone BKC files supplied alongside the projects were different measurements; they were structurally inspected but were not falsely paired with those exports. Private source files and comparison reports are excluded from Git. This is empirical, versioned format support, not a claim of a complete manufacturer BKC specification.

## Limits and preservation

Unknown firmware/profile/sequence meanings remain raw-only; malformed, oversized, unsupported or inconsistent containers are rejected. Limits include 32 MiB per file, 64 parts, bounded XML and vectors, exact table lengths and no archive extraction paths. No whole ENP/NP project importer, logging/time-series BKC import, native audio decoding from BKC, 2245 support or signature authentication is claimed. Keep the original `.bkc` alongside any exported inspection report.

Implementation: `src/bnkg/core/bkc.py`, `src/bnkg/ui/bkc.py`. Source interpretation follows [standing measurement rules](MEASUREMENT_SEMANTICS.md). For expansion, obtain a matching trusted export and specimen for each new profile before enabling conversion.
