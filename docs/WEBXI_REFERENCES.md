# Web-XI implementation evidence

Reviewed 2026-09-17. HBK examples are references only; their implementation source is not copied into BnKG.

- [Official Open Interface repository](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter): device family, HTTP transport, full functionality dependent on an instrument licence.
- [Getting device information](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Python%20examples/01%20-%20Getting%20device%20information.py): GET `/webxi`, `/webxi/device`, path-based tree traversal, `?recursive` queries.
- [Metadata](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Python%20examples/02%20-%20Metadata.py): `?metadata` query flag.
- Project brief sections 3, 4 and 5: observed SLM State and LAF routes, LAF raw/100 conversion, Setup/Outputs tree areas. These are user-supplied observations, not current hardware validation.
- [Qt/PyInstaller guidance](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html): deployment reference; exact local packaging is validated separately.

The current client is deliberately limited to a fixed set of GET routes. Discovery preserves raw JSON without assuming model-specific schema. Live adapter exposes LAF only and labels hardware validation pending. Further parameter mappings, stream framing, stream creation/deletion, settings and storage access require additional protocol review and actual-device fixtures.

## 2026-09-18 update

- [Official SLM mDNS example](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/tree/master/C%23.Net%20examples/C%23%20Discovery%20Example) and [protocol specification section 12](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf): _web-xi._tcp.local service, optional name/version TXT records. Implemented independently with [python-zeroconf](https://python-zeroconf.readthedocs.io/en/latest/api.html).
- [Connectivity guide](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/03-SLM%20WebXi%20connectivity.pdf): current IP location, licence checks and documented password query parameter.
- [2255 instruction manual](https://www.bksv.com/downloads/2255/instruction%20manual/be1917.pdf), displayed page 14 and Network settings: restrained green/grey/orange visual reference and Web server display. No manufacturer artwork or source was copied into the UI.
- Live read-only evidence: firmware 1.3.0.478 /display/ HTML uses /display/tmp/screenDump.png and Setup/NetworkWebserverDisplay. GETs confirmed enabled display and PNG bytes. This firmware-observed route is a separate view-only fallback to the ScreenImage stream; no stream setup or automatic setting writes are used.
- GET /webxi/Applications/SLM?metadata advertised StartPause and Stop with descriptions. The backend permits these exact actions only after explicit arming, verifies state, refuses unknown/result states and reads state afterward. Generic key/menu actions remain blocked because they can reach consequential settings without an adequate preview.
- Native app testing obtained a screen and LAF without arming controls. mDNS returned no results on this network; a narrow subnet search identified the meter. Real writes remain untested. See artifacts/python-update for local private evidence (not tracked).

The earlier read-only-alpha paragraph above describes 0.1.0a1; 0.2.0a1 adds only the guarded actions and observed screen route described here.

## 2026-09-19 update

0.3.0a1 expands the adapter to descriptor-based scalar/CPB output trees, read-only metadata, native PNG saving and guarded Identify. See [METADATA_CAPABILITIES.md](METADATA_CAPABILITIES.md) for exact observed paths, conversion/axis evidence, GPS and write limits. Metadata and sequence reads use fixed verified roots, no stream setup. User-confirmed display-off testing yielded identical PNG hashes with the clock frozen at seconds 54; PC-monotonic unchanged-image detection was verified without a device write. No authoritative physical display power state was exposed by the inspected UI metadata.

## 2026-09-20 saved directory inventory

[Protocol section 7](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf) defines GET directory traversal and File/Directory flags. Verified 2255 Data → dated directory → measurement directory → .total.bkc. Preserve literal `$` delimiters on this firmware (percent-encoded `%24` returns unknown node). Read-only inventory, no Open/GetArchive or other action. See DEVICE_FILES.md.
