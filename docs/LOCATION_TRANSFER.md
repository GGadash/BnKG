# B&KG — Read SLM location and send location text

Python source 0.3.0a2. **The implemented writer is custom text metadata, not native GPS-coordinate injection.** Its real write/save workflow has not been hardware-tested. Automated tests use mock instruments; live validation used GET only.

## Use the panel

1. Connect explicitly and open **Metadata → Location / transfer**. Latitude/longitude start empty in public builds. Enter a location or copy a valid SLM-reported position; no private location is preset. Check that it describes the meter's position before using it.
2. Type decimal coordinates, or click **Use current SLM coordinates** when valid coordinates are available. An unavailable/sentinel result leaves the manual draft intact. Copied instrument coordinates are labelled SLM-reported with PC receipt time; this is not a verified fix timestamp.
3. On the physical SLM, enable metadata collectively and enable a spare slot. Set its type to **Text** and a meaningful name, such as GPS coordinates. B&KG does not automatically enable, rename or change types. Choose the intended slot in the panel; no slot is automatically reserved or overwritten.
4. Leave the instrument idle with no pending result (`Activated`). Do not interrupt a real measurement simply to test this feature. Arm controls on **SLM Screen**, then return to Metadata and click **Preview location transfer**.
5. B&KG checks the live state, master/slot enable, type, String schema and absence of ReadOnly. A disabled/locked/unknown slot is rejected with instructions. The preview shows device address, slot/name, old text, exact new coordinate text and source.
6. Confirm twice. Cancel sends nothing. The preview expires after 60 seconds. The backend rechecks state/access/name/old value, then sends one JSON-string PUT to the selected `Setup/MetadataNText` and reads the slot back. A changed/expired preview requires a new review.
7. A verified text read-back means the setup slot contains the requested text. **It does not prove persistence in a saved measurement**. Confirm metadata while saving the intended subsequent measurement using the SLM workflow. Hardware acceptance still needs a coordinated write/read-back/save/export test.

Only this one text value is changed. The app does not write Outputs/Latitude, Longitude, Altitude, calibration, GPS service settings, slot names/types/enables, project names or storage filenames. Text does not become a native GPS fix. There is no automatic transmission of the default or copied coordinates.

If an acknowledgement/read-back is ambiguous, the app disarms, sends no retry and reports an uncertain outcome. Inspect the slot, refresh control state and deliberately re-arm/preview before a new attempt. The app cannot make the multi-request REST operation atomic against simultaneous physical-SLM changes.

## Local audit and privacy

Every attempted transfer first appends and flushes an audit record to `audit/BnKG-Location-Writes.jsonl` under the configured application data directory (or `--data-dir`). The record includes PC UTC time, device address, slot/name, source and old/new text, followed by verified/uncertain outcome. Audit creation failure prevents a write. This audit is independent of optional measurement logging and can contain sensitive location/operator text. No password is logged. It is local data, not a public-release asset.

## GPS source distinctions

HBK's [2255 specification](https://www.bksv.com/en/instruments/handheld/sound-level-meters/2255-series) lists integrated GPS. Phone location can annotate data in manufacturer apps; it does not establish a native-coordinate setter. The user's clarified request is to read the SLM when possible and mainly send typed or app-device location; no external receiver connected to B&KG is assumed.

Automatic PC/phone location acquisition is **not yet implemented**. A later provider must handle OS permission, source/fix time, validity/accuracy and whether the app-device location describes the SLM. No external GPS/weather-station connector or automatic map/upload runs now. Coordinate provenance should remain distinct even if several sources are added.

See [verified findings](METADATA_GPS_FACT_CHECK.md) for the claims and limits and [metadata capabilities](METADATA_CAPABILITIES.md) for the available fields. Broader AppData/native GPS injection remains dependent on a verified vendor schema.


Stage 6 adds an explicit OpenStreetMap link and Copy map link for validated draft coordinates. Zero coordinates are valid inputs; invalid coordinates disable the link. A click shares the coordinates with the external provider, with no automatic map load. Manual/SLM-reported draft provenance remains visible; a map does not prove fix validity/accuracy or instrument position. Local report project/site/operator/notes live in a separate tab and never become a device setup payload. The existing transfer backend and its confirmation/read-back/audit rules are unchanged.
