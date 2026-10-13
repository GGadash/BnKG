# Building an SLM GPS and Marker App

Generic implementation guide · 2026-10-12

For mobile or desktop applications working with HBK 2255 / B&K 2245 and their Open Interface / Web-XI. Independent of programming language and UI framework. This is a design reference, not an implemented upload specification or authorization to write to an instrument.

## 1. What is established, and what is not

HBK documents phone location on annotations: with location permission, notes, photos, videos and voice annotations can carry location. Annotations made during measurement upload automatically to the instrument with their measurement association; those made before/after can remain unattached until assigned. The PC app can map imported annotations. [ENP guide, pp. 110–111](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf#page=110)

Measurement locations and annotation locations are distinct. HBK specifies instrument GPS for measurement map positions and phone location services for annotation positions. A mapped annotation does not prove that phone coordinates replaced native measurement GPS. [NP guide, pp. 85–86](https://www.bksv.com/downloads/2245/user%20guide%20-%20noise%20partner/bn2376.pdf#page=85)

ENP mobile provides four customizable markers: Ambient, Residual, Background and Exclude by default. Logging must be enabled. Tap a category to begin/end an interval, or apply it to a selected profile range. Exclusion preserves the original readings. [ENP guide, pp. 86–87 and 99–101](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf#page=99)

These guides document iOS workflows. Android Noise Partner exists, but equivalent annotation/location features were not established here. Check the target app/version rather than assuming parity. [HBK Android listing](https://play.google.com/store/apps/details?id=com.hbk.remotecontrol)

**Unverified:** exact native GPS-annotation and marker payloads, upload destinations, attachment requests, file encoding and persistence rules. No confirmed public native GPS setter or marker-write request has been established in this project. Do not invent one.

## 2. Separate the application into small components

Suggested flow:

`Location provider / marker buttons → local record store → reviewed upload queue → verified device adapter → read-back and PC import check`

- **Location provider:** obtain permission and a location fix from the OS, an external receiver, a nearby phone relay, or manual entry. Keep each source identifiable.
- **Measurement context:** retain meter identity, measurement identity and its actual time basis.
- **Annotation/marker store:** save durable local records independently of connectivity.
- **Device adapter:** discover capabilities and translate records only into a verified manufacturer format.
- **Upload queue:** track attempts, errors, remote identifiers and verification results.
- **UI:** display accuracy, source, selected measurement and upload status; keep network work off the UI thread.

A PC may use an external GNSS receiver or a phone companion. Never silently label network-derived or manual location as GPS. A remote PC's position is not automatically the meter's position.

## 3. Acquire and save GPS/location

Recommended local record fields below are **application design fields, not HBK wire-format keys**:

| Record | Minimum useful information |
| --- | --- |
| Identity | Local unique ID, target meter ID, measurement ID when known |
| Coordinates | Latitude/longitude in decimal degrees; explicit datum, normally WGS 84 |
| Fix quality | Source, fix UTC time, receipt UTC time, horizontal accuracy when available |
| Optional altitude | Value, units and reference, such as ellipsoid or mean sea level |
| Context | Phone/PC/meter position, association method, annotation type and content |
| Transfer | Local revision, status, remote identifier, last verification/error |

Validate coordinate ranges and missing values; zero latitude/longitude is valid. Reject or visibly flag stale fixes and poor/unknown accuracy. Do not fabricate precision or altitude. Ask the operator to confirm that the captured location represents the measurement site when the devices are separated.

Save locally first. Allow review before transfer and preserve the previous value when an edit is made. Store only the location information needed for the task; keep private coordinates out of public samples and logs intended for sharing.

## 4. Save markers correctly

Use a category definition (stable ID, label, colour and function) and a separate marker occurrence (unique ID, measurement ID, category ID, start/end and time basis). Keep point events separate from interval markers; native ENP support for arbitrary point events is not established here.

For a live interval, the first press opens it and the second closes it. For saved data, let the user select a range. Persist changes promptly; make unfinished intervals visible after interruption. At measurement end, explicitly close at a verified endpoint or retain an incomplete status.

Use instrument time or validated sample/profile indices when available. If only app receipt time is available, label timing as estimated and retain its uncertainty. Do not assume wall-clock duration equals active measurement time across pauses. Resolve clock offsets, gaps and pause behavior before native conversion.

A marker flag does not change original acoustic samples or whole-measurement Leq. Any interval/exclusion calculation must use suitable data, preserve its method and be labelled Calculated. Keep cumulative Leq, verified interval Leq and current time-weighted levels distinct. Do not silently derive missing SLM A/C/Z values.

## 5. Discover Web-XI support before uploading

Web-XI uses HTTP over supported Wi-Fi/wired connections; full access requires the appropriate instrument licence. [Official Open Interface repository](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter)

Useful read-only discovery requests, prefixed with the actual instrument address:

```http
GET /webxi/Applications/SLM?metadata
GET /webxi/Applications/SLM/AppData?metadata
GET /webxi/Applications/SLM/Data?metadata
```

Follow advertised children and access metadata for the actual model/firmware. If a node is absent, treat it as unsupported; do not manufacture a path.

Saved BnKG inspection of 2255 firmware 1.3.0.478 found AppData and an Attached container advertising POST/Directory capability, with AppData described as smart-device annotation storage. **This identifies a candidate facility, not a confirmed GPS or marker upload route.** It does not reveal the request body, content type, location encoding or measurement-linking procedure. [Recorded findings](METADATA_GPS_FACT_CHECK.md)

Do not PUT coordinates into Outputs/Latitude or Longitude. Do not treat a GPS enable setting as a coordinate input. Do not assume arbitrary JSON, photo EXIF, a desktop project archive or a modified BKC file will be recognized.

## 6. Establish a compatible upload method

Before implementing native transfer:

1. Obtain HBK documentation/sample code for application annotations, project data and measurement association. If insufficient, arrange authorized observation of a manufacturer-app transfer.
2. Keep a baseline copy of one disposable measurement/project. Add one known geotagged annotation and compare before/after records. Investigate a single known marker separately.
3. Identify the actual endpoint, method, content type, payload, units, coordinate convention, IDs, time origin and attachment operation. Determine whether markers belong to project records, measurement attachments or another container.
4. Implement only the demonstrated profile. Preserve unknown fields and unrelated annotations. Do not rewrite native acoustic binaries to add metadata.
5. Upload once with explicit approval, then read back. After reconnecting, import into ENP/NP PC and check the intended location icon, measurement association, marker category and interval boundaries.

A geotagged annotation icon and a native measurement map icon are separate acceptance outcomes. Do not declare the second complete after verifying only the first.

Show precise states: **Saved locally → Pending upload → Sent, unverified → Verified on SLM → Verified in ENP/NP PC**. An HTTP success alone is insufficient. After a timeout, check remote identity/content before retrying; blindly repeating creation requests can duplicate records. Reconnect must not automatically replay uncertain writes.

## 7. Useful options while the native format is unknown

| Option | What it provides | Limit |
| --- | --- | --- |
| Local project records and maps | Location, markers, review and exports in your own app | No ENP/NP native compatibility claim |
| Manufacturer mobile workflow | Geotagged annotations and supported markers | Requires the relevant supported app/features |
| Coordinates in an enabled text metadata slot | Human-readable coordinates associated through the normal save workflow | Not native GPS; no guaranteed map pin; not a verified edit of past measurements |
| Verified native adapter, developed later | Potential ENP/NP-compatible transfer | Requires schema evidence and round-trip validation |

BnKG currently documents guarded coordinate-text transfer and local review markers. Automatic phone/PC location capture and native GPS/marker write-back are not established features. Even text-slot read-back does not prove persistence in a saved measurement. [Current location-transfer limits](LOCATION_TRANSFER.md)

## 8. Small acceptance check and implementation order

Build local acquisition/storage and marker editing first, then offline export/reopen. Test invalid/stale coordinates, an interrupted marker and a missing measurement association locally. Keep upload disabled until its format is verified.

When separately authorized, use one disposable measurement for a bounded native test: one known location annotation and one marker interval. Verify read-back, reconnect and PC import. Confirm no duplicate creation after an ambiguous-response recovery and no changes to original readings or unrelated records. Keep factory reset, calibration, service and destructive actions outside this feature.

This document records a proposed reusable design. No app implementation or instrument writes were performed to create it. Related reference: [SLM parameters, files and safe controls](SLM_WEBXI_PARAMETERS_FILES_AND_SAFE_CONTROLS_QUICK_GUIDE.md).
