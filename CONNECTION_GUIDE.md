# B&KG — Connect the SLM

This app is under construction. For more complete version of the app pls visit the Dev's GitHub page: [https://github.com/GGadash](https://github.com/GGadash). Optional support: [Ko-fi](https://ko-fi.com/gadash).

## Connect to the current address

1. Connect the PC and SLM to the same network: Wi-Fi, the instrument hotspot, or a supported USB-C/Ethernet network connection.
2. On the SLM open **Menu > System settings > Network settings** and check the active Wi-Fi or Ethernet IP. An IP can change after reconnection.
3. In B&KG choose **Connection**. Type the current IP or hostname, optionally including an HTTP(S) scheme/port. Click **Connect SLM**. Successful connections appear in the Recent connections list; startup never reconnects automatically.
4. If the instrument has a network password, enter it in the masked password field. It stays in memory only and is not saved in preferences/logs. On HTTP networks it is sent using the instrument's documented query-parameter mechanism, so use a trusted local network.
5. Confirm the displayed device identity/firmware. Web-XI's BZ-7400 licence must be installed/enabled for full access.

A local instrument was checked on 2026-09-18. Identity, state, LAF and a display image were read successfully from a 2255 running **1.3.0.478**. This address is a historical observation, not a hard-coded application default or a promise it is still current.

## Find the meter when its IP changes

- **Find SLMs (mDNS)** listens for the manufacturer's `_web-xi._tcp.local.` service, then checks advertised endpoints. This is the preferred method because it does not depend on a remembered IP.
- Select a discovered row to populate the address, then click Connect SLM. Advertised but password-protected/unverified devices are labelled accordingly.
- **Search subnet** is the fallback. Choose one local IPv4 network from the list or type a private subnet. The search is limited to /24 or smaller (at most 254 hosts), with 12 concurrent workers and a Cancel button. It lists Web-XI-identified meters and other responding IPs separately. A ping/HTTP reply alone is never described as an SLM.
- Results are not a complete inventory: offline devices, firewall rules, multicast filtering and guest/AP isolation can prevent replies. mDNS did not return a meter on the tested home connection; the fallback did find it. Manual IP entry remains available.
- Where local DNS resolves it, a stable instrument hostname is another option. A router DHCP reservation can keep an address stable; configure that yourself under the network administrator's policy. B&KG does not rewrite the meter's network settings.

Searches are explicit, never automatic. Discovery currently lists IPv4 endpoints; manual address entry also accepts ordinary IPv6 addresses, but IPv6 discovery/link-local scope IDs are not implemented.

## Screen and instrument controls

Choose **SLM screen**, second after Dashboard. Enable **Web server display** on the physical SLM under Network settings if needed. B&KG reads the PNG route exposed by the connected meter's own /display/ page, once per second while this tab is selected. This route was observed on firmware 1.3.0.478; unsupported firmware displays an explanation. The image itself is view-only. No stream is created and no screen-related setting is written automatically.

The dedicated control panel sits beside the screen, or below it on narrow layouts:

- **Arm SLM controls** for each connection, then deliberately click **SLM Start / Pause**. The backend checks advertised actions and the current state before one request and verifies state afterward.
- **SLM Stop** ends the measurement with one deliberate click while armed; no repeated dialog.
- **Wake / Identify display** uses the advertised Identify action, briefly lighting display and light ring. It requires arming, sends one request and checks reachability afterward; acknowledgement does not prove visible illumination. It is not a power-on command and was not sent during live testing.
- Completed/result-loaded or unknown states do not permit Start/Pause; handle saved/unsaved results on the instrument.
- After an ambiguous action response, B&KG sends no retry and disarms. Inspect the instrument, click **Refresh control state**, then deliberately re-arm before a new action.
- Settings, calibration, reset, deletion and generic menu-key injection remain blocked.

Control code is covered with mock tests. **No real Start/Pause/Stop/Identify commands were sent during development validation.** Broader 2255 acceptance and 2245 validation remain pending.

## Local capture is separate

Controls are under **Data table**. Live monitoring creates neither a table history nor a measurement file. **Start local capture** collects the table/trend; **Start file logging** also starts capture and creates `BnKG-LocalLog-instrument-[optional-project-site]-YYYYMMDDTHHMMSS-microsecondsZ.sqlite` under the app's sessions directory. Each sample has PC UTC receipt time, source, quality, raw values and converted values.

**Stop file logging** leaves capture running. **Stop local capture**, source changes and **Disconnect** stop instrument capture and close its file. Demo Lab has an independent simple CSV log: its Pause/Stop does not affect the instrument connection or logging. These local actions do not stop the actual SLM measurement.

The data table retains only the newest configured 1–999 rows (default 100). Dropping older rows from memory does not delete them from the logged session. Export that session on Sessions & export. Current source exports the active session independently while monitoring/logging continue. Stop logging only when selecting a different export session.

## References

- [HBK Open Interface discovery example](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/tree/master/C%23.Net%20examples/C%23%20Discovery%20Example)
- [Web-XI protocol specification, section 12 Discovery](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf)
- [SLM connectivity checks](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/03-SLM%20WebXi%20connectivity.pdf)
- [2255 instruction manual, Network settings](https://www.bksv.com/downloads/2255/instruction%20manual/be1917.pdf)

A **Connection help** button in Connection and **How to connect an SLM** in the screen panel provide the essential instructions inside BnKG.

## Frozen display, PNG and live measurements

The last received PNG remains visible when disconnected or polling fails. The overlay marks it stale and dims it; Connect opens Connection. Leaving SLM Screen pauses its polling and marks the image accordingly. If successive images stay identical for more than ten PC-monotonic seconds, the message says **Display not updating — image unchanged; display may be off or static**. An unchanging page can also trigger this, so it is not claimed as an authoritative power state. No clock synchronization is required. On 2026-09-19 the user confirmed the physical display was off; repeated PNGs retained the meter's frozen seconds at 54 and the overlay appeared correctly.

**Save original SLM PNG** preserves the exact received bytes/resolution, even for a retained image. It refuses overwrite. Workspace screenshots are separate. MP4/audio are deferred; no FFmpeg is bundled.

Dashboard and Frequency Analysis read enabled Outputs/Sequences/Setup via GET. They show current values and SLM measurement totals, not locally integrated noise metrics. Missing/sentinel results are unavailable. Descriptors determine scaling and band axes; unsupported formats and vector mismatches are withheld. Polling is not an atomic or sample-synchronous stream. Metadata reports overload/underrange and other available device fields; PC receipt time is not instrument acquisition time. See docs/METADATA_CAPABILITIES.md.

Metadata/GPS claims and phone/external-source distinctions: [verified findings](docs/METADATA_GPS_FACT_CHECK.md). Battery/disk status is available as selectable read-only metadata.

Location: Metadata now includes manual coordinates (initially empty; not a fix), copying valid SLM coordinates and a guarded transfer to one enabled Text slot. This does not change native GPS. Two confirmations, arming, idle-state/access checks, read-back and a local audit apply. Automatic PC/phone location is pending. See [location transfer instructions](docs/LOCATION_TRANSFER.md). Live writes were not tested.

## Saved instrument files and app information

Device files → **Load latest records** reads up to 100 saved records by default (adjustable 1–999), optionally between dates. **Browse all folders** and **Browse selected directory** traverse internal memory with 100 displayed entries per page. Explicit GET-only inventory; no native file download/decoding or instrument Open action. See [Device files](docs/DEVICE_FILES.md) in the project documentation (wiki: `../DEVICE_FILES.md`). About is now at the top, before System/Dark/Light, with full B&KG title, **B&KG = BnKG**, creator/AI/tool credits and developer/support links. Repository Discussions will be linked after publication.


## Current source diagnostics — 2026-09-29

Connection shows current state and explicitly labels retained identity when disconnected/stale. Firmware is shown only when supplied. Advertised controls and received field counts are evidence of what was observed, not a universal capability/licence guarantee. Discovery shows activity and cancelled/ended state; selecting a candidate fills the address without connecting. Existing handshake, bounded scan and cancellation rules are unchanged.

Transport errors distinguish timeout, connection failure, TLS verification, access denial and HTTP 404. Check the corresponding network/address/password/access settings; access denial alone does not identify a missing licence. Certificate validation is not bypassed and failures never trigger automatic device actions.

Copy support summary is local and excludes identity/address by default. An explicit checkbox adds the last identity; passwords, raw samples, instrument metadata values, local report drafts and arbitrary error text remain excluded. The recent-state history is bounded to 32 transitions. No automatic diagnostic probe or upload runs.

The SLM is offline for the stage 5–6 development checks. These UI/error paths were exercised with fixtures, not fresh network/hardware validation. Prior Identify/supervised-arrow evidence is historical in `01_PROGRESS.md`; broader control tests remain separately authorized.


Current session-control policy (2026-10-10): successful actions keep controls armed. Start/Pause/Stop and acknowledged measurement-screen arrows do not ask repeatedly. The centre Menu / OK opens only from a measurement view and then locks screen keys. Return on the physical SLM and acknowledge its measurement view again. Settings/metadata retain two confirmations, critical operations stay blocked, and disconnect/uncertain outcomes disarm. See docs/RECORDING_PLAN.md.


Stopped-state update: Start/Pause works from ResultMeasured after Stop using the ordinary advertised action, without ResetStart. Stop on an already stopped meter is a harmless no-op. Short Stopping/RampingDown transitions are read again briefly; no command is automatically resent. If still busy, wait and click deliberately. Measurement controls do not require an illuminated display. Wake / Identify can refresh a sleeping/static display; downloaded PNGs may lag verified measurement state.
