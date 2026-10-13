# B&KG — Security and Device Safety

Early alpha; hardware compatibility and release requirements remain under validation.

Only StartPause and Stop are implemented as real measurement writes: explicit per-connection arming, action metadata checks, allowed-state checks, one PUT and read-back. Stop additionally requires two confirmations. Uncertain outcomes disarm and block another action until deliberate state refresh; no automatic retry. Unknown endpoints/actions remain blocked. Critical calibration/service operations will remain blocked in normal releases. Future settings require classification, confirmation and read-back. An ambiguous Start/Pause toggle must never be automatically retried.

Tests use synthetic data and must not write to hardware automatically. Do not put credentials or private captures in Git. A contact/repository channel will be supplied during GitHub setup.

Current controls: address validation, GET allowlist and two fixed guarded measurement actions, no redirects, timeouts, bounded response size, no untrusted plugins, fixed formulas, parameterized SQLite, preserved source files and spreadsheet formula-injection handling.
