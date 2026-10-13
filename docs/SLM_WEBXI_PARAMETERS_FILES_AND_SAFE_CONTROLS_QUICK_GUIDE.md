# SLM Web-XI: Parameters, Files, Markers and Safe Controls

Brief, language-independent reference • 2026-10-10

Applies to HBK 2255 / B&K 2245 Open Interface concepts. Actual calls below were verified where stated on **2255 firmware 1.3.0.478**; discover capabilities for each model/firmware. Full Web-XI access requires the appropriate instrument licence. This is the SLM Open Interface, not the separate LAN-XI API. [Official documentation](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter).

## 1. Connect and discover

Use the instrument's current IP/hostname on the same network. Prefix paths below with `http://<SLM-IP>` or supported, certificate-verified HTTPS. Follow the instrument's documented authentication method; keep credentials out of logs.

| HTTP request | Purpose |
| --- | --- |
| `GET /webxi` | Discover the root tree. |
| `GET /webxi/device?recursive` | Identify model, firmware and device. |
| `GET /webxi/Applications/SLM?metadata` | Discover supported actions and descriptions. |
| `GET /webxi/Applications/SLM/State` | Read measurement state. |
| `GET /webxi/Applications/SLM/Outputs?recursive` | Read available acoustic values and spectra. |
| `GET /webxi/Sequences?recursive` | Read sequence descriptors, conversion and timing definitions. |
| `GET /webxi/Applications/SLM/Setup?recursive&metadata` | Inspect configuration, types, access flags and allowed values. |

`?metadata` describes a node; `?recursive` traverses descendants. Discover advertised children rather than inventing paths. Read-only access flags and available actions do not authorize arbitrary writes.

## 2. Obtain and label noise parameters

Read available outputs such as LAF, LAeq, LZeq, LCpeak and CPB spectra. Match each value to its descriptor: data type, unit, Scale/Offset, acoustic/time weighting, function, band axis and measurement period. For a supported linear descriptor, `displayed value = raw × Scale + Offset`; do not assume every value uses `/100`. Treat invalid/sentinel results as unavailable, not zero. Preserve raw values, quality flags and instrument timestamps.

| Quantity | Correct meaning |
| --- | --- |
| Whole-measurement LAeq/LZeq | Cumulative or completed measurement equivalent level over its actual integration period; retain measurement identity and elapsed time. |
| Short-term LAeq/LZeq | Equivalent level for an explicitly defined interval. Label “125 ms” only if the instrument's sequence/function and time basis verify that interval. |
| Current LAF/LZF | Fast time-weighted level, not interval Leq or cumulative Leq. |

**Fast's 125 ms time constant is not a 125 ms Leq interval.** Polling rate and output period are also different from integration duration. For example, the observed `CPBLZF250ms` output is a current Fast spectrum; its 250 ms cadence does not make it interval Leq. For high-rate acquisition use a supported instrument stream with its descriptors/timestamps; stream creation can change device resources and must be reviewed separately.

Obtain A/C/Z values and spectra directly from the meter. Leave missing weightings unavailable. If a separate calculation is necessary, label it **Calculated**, identify its inputs/time basis and retain provenance. Label every histogram with quantity, weighting, frequency bands and total/interval/current scope. See [measurement rules](MEASUREMENT_SEMANTICS.md).

## 3. Wake and control the instrument

After verifying the advertised action, a Wake button sends one empty-body request:

```http
PUT /webxi/Applications/SLM?Action=Identify
```

This requests display/light-ring illumination; it does not power on an off instrument or start measurement. Read state afterward. An acknowledgement or PNG alone cannot prove physical illumination.

Observed screen access: `GET /display/tmp/screenDump.png`, with `Setup/NetworkWebserverDisplay` enabled. This is a firmware-observed route, not a universal API guarantee. Images can lag actual state.

Measurement buttons use empty-body `PUT /webxi/Applications/SLM?Action=StartPause` or `Action=Stop`. Verify state before/after. Normal StartPause works after Stop (`ResultMeasured`) on the tested 2255; it is distinct from ResetStart. Brief Stopping/RampingDown states may need bounded read-only settling. Never resend a toggle automatically after an ambiguous response. These actions do not depend on screen illumination.

## 4. Protect settings while offering screen keys

Advertised actions include KeyUp, KeyDown, KeyLeft, KeyRight and KeyMenu, invoked using the same `PUT ...?Action=<name>` pattern. Their effect depends on the displayed page: arrows/menu can edit or apply settings.

Use an action allowlist in the command layer as well as disabled buttons. Arm per connection; acknowledge a fresh measurement view before enabling arrows. A restricted centre Menu button opens the menu once, then locks all remote keys. Return physically to the measurement view before acknowledging again. Disable keys for unknown/stale context and clear authorization on disconnect or uncertain results.

**Measurement State alone does not identify whether a settings menu is open.** Without a verified menu-context API, this approach relies on user acknowledgement; it cannot automatically detect every physical menu entry. Do not claim automatic settings protection from image freshness alone. Keep reset/calibration/service/destructive actions blocked; reviewed settings/metadata edits need previews, two confirmations and read-back.

## 5. Retrieve files and projects from memory

Start with `GET /webxi/Applications/SLM/Data?metadata`. Follow returned children marked Directory; retrieve advertised readable File nodes with GET. Preserve original bytes, names, parent relationships and hashes; verify completion before publishing a local copy. Retain related native/audio/annotation files together. Preserve literal `$` in advertised paths on the tested firmware; encoding it as `%24` previously failed.

Downloading does not require Delete, MarkArchived, Open, or guessed archive actions. Native `.bkc` bytes need a validated format/profile decoder to become engineering values.

A manufacturer **project** is more than a single BKC file: it can group measurements and project metadata. ENP can import projects or build them from instrument measurements. Use advertised storage and verified project schemas, or the manufacturer's import/export workflow. Do not assume a desktop `.enp`/`.np` archive exists at a fixed instrument path. AppData/Attached annotation containers have been observed, but their payload and measurement-association rules remain unverified here. See [file retrieval](DEVICE_FILES.md).

## 6. Add markers / marker flags

Generic app-side method: create a marker category, then store its ID/label, point or start/end interval, measurement ID and instrument-time/sample reference. Toggle a category on/off for a live interval, or mark a selected saved interval. Persist flags in a separate project/annotation record so original readings remain intact. Distinguish event markers, notes and exclusion flags. A flag alone must not silently alter cumulative Leq; any exclusion-based recalculation needs valid interval data and an explicit method.

ENP supports measurement markers, including categorization and exclusions, as documented in its [user guide, Marker settings and Markers in measurements](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf). BnKG's earlier M1/M2/M3/Exclude review flags are local annotations, not verified instrument marker writes.

**Native marker write-back remains unverified:** no confirmed public endpoint/payload was established from the inspected SLM action/setup/output/sequence metadata. Do not invent a Marker PUT or upload arbitrary JSON/XML to AppData. Before implementing write-back, obtain the manufacturer schema or authorized protocol evidence, verify category/time/measurement association, then test one marker and its round-trip persistence. ENP's feature availability alone does not establish the API call.

Protocol reference: [official Web-XI specification, including storage](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf). Instrument-specific observations above are evidence, not guarantees for all firmware.
