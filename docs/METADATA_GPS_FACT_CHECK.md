# B&KG — Metadata and GPS claim check

Checked 2026-09-20 using official HBK references and GET-only inspection of the connected 2255 firmware 1.3.0.478. No settings, measurements, annotations or calibration were written. These observations are specific to that firmware/configuration; private raw captures remain in excluded `.cache/batch5`.

## Findings

| Supplied claim | Finding |
| --- | --- |
| Nine slots, master/individual enable, Text/Picklist/Number | Confirmed by live setup metadata: MetadataAll and MetadataNMetadata use 0/1; Type maps 0 Text, 1 Picklist, 2 Number. |
| Up to 11 picklist entries | Confirmed. REST selection values are **0–10**, while entry keys are Entry1–Entry11. Number domain is 0–999. |
| Names are limited to 32 characters | Not confirmed. The live String metadata supplies no length limit. Do not enforce an invented limit or promise unlimited input. |
| Metadata review before saving | Confirmed by the official guide. Configure master and individual slots before measuring; enabled custom metadata is saved with measurements and can be reviewed before saving. [BN2375, printed p.78](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf#page=78). |
| All metadata text/name registers can be written immediately | Not in the observed state: master and slot 1 are disabled, and Name/Text/Type/Number/Picklist fields advertise ReadOnly. Enabling can change access; B&KG has not tested that transition. Never ignore a current ReadOnly flag. |
| The 2255 has no satellite receiver | **Contradicted by HBK's specification**, which lists integrated GPS for position/time. [Official 2255 product page](https://www.bksv.com/en/instruments/handheld/sound-level-meters/2255-series). |
| Large negative coordinate sentinel proves no receiver | Incorrect inference. Latitude/Longitude/Altitude again returned approximately -1.7976931348623157e308: no usable coordinate value. It does not establish why location is unavailable or prove the hardware design. B&KG displays Unavailable. |
| ServiceGpsLocation=1 means ready to accept external GPS | Incorrect interpretation of the advertised description. It enables registration of location on measurement data; it is not a documented external-coordinate input. Current flag is ReadOnly. |
| Phone GPS can supply annotation location | Confirmed for manufacturer apps: annotation location comes from the mobile device's location services and permissions. That is distinct from replacing the instrument's native GPS outputs. [BN2375, printed p.155](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf#page=155). |
| Weather-station connection necessarily supplies GPS | Not established. HBK documents MM-0316-A for wind and MM-0256-A for wind/ambient weather measurements over supported USB/Bluetooth. Those descriptions do not list GPS. An external receiver or a GPS-equipped weather station needs its exact model/interface checked. [Noise Partner guide, Weather station](https://www.bksv.com/downloads/2245/user%20guide%20-%20noise%20partner/bn2376.pdf). |
| Coordinates in custom text update native GPS | No. Text such as `6.92708, 79.86124` can describe a location in an enabled text slot, but is not a verified update to Outputs/Latitude or Longitude. The proposed numeric metadata type cannot hold decimal coordinates (domain 0–999). |
| Guaranteed permanent embedding in a .bkc binary on eMMC | Too specific/unverified. The guide supports saving custom metadata with measurements; no verified binary schema or tested import/save round trip establishes that exact file/container claim here. Do not reserve/overwrite slots 8/9 without explicit selection and preview. |
| AppData supports annotations | Confirmed: `/webxi/Applications/SLM/AppData` advertises Post/Directory and describes smart-device annotations; Attached also advertises Post/Directory. The payload schema, location fields and measurement association workflow remain unverified. HTTP POST capability alone does not establish a safe upload format. |
| Project/measurement rename equals native file rename | Not established. Manufacturer app measurement display names belong to the project, according to the guide. No verified native project/file-name setter has been identified. [BN2375, printed p.96](https://www.bksv.com/downloads/2245/user%20guide%20-%20enviro%20noise%20partner/bn2375.pdf#page=96). |
| B&KG already adds GPS/map links to CSV/JSON/PDF every second | Incorrect as a description of the current app. JSON/NDJSON and SQLite preserve available instrument raw location/context. Flat CSV/XLSX catalogue exports do not yet add dedicated GPS columns. PDF reports, phone/external-GPS connectors, native GPS injection and map-link generation are not implemented. The new panel accepts manual coordinates and offers a reviewed text-slot transfer; it does not auto-add dedicated location columns to exports. Logging is optional and PC-timed, not guaranteed exactly one record per second. |

## System information: what was actually exposed

Model/serial/firmware/hardware and microphone type/serial were confirmed by read-only identity/output values. The supplied 51.35 mV/Pa is not a reliable constant: current Setup TransducerSensitivity uses **V/Pa** and the output read approximately **0.043406**. The app preserves the instrument value/declared units; it does not alter calibration. Calibrated returned a date, not a demonstrated full timestamp.

Battery and disk status are under **/webxi/device/Battery** and **/webxi/device/Disks**, not necessarily SLM Setup/Outputs. The app now displays advertised read-only status fields with units and enum names, refreshed approximately every five seconds. Examples: charge percentage, charging state, remaining time, battery temperature and available/total disk MB. Battery temperature is not labelled as ambient temperature or an unspecified general internal temperature. No free-RAM field was verified. Weather Outputs/Temperature is a different field, dependent on the measurement/accessory setup.

Current microphone setup fields are selectable too. Their values are read-only in B&KG, even where another setting could be writable. Unknown access metadata now shows **Access unknown; no writes allowed**. Status failure does not replace sound-level data with a failed health result.

## Practical ways to proceed

**Today:** view instrument GPS/metadata/status in B&KG; configure custom Location/Operator/Project or coordinate-text slots on the physical SLM, following its enabled-slot/type workflow. Read-back and save/export acceptance are needed before claiming a remote writer works. Do not confuse text coordinates with native GPS.

**Next connector design:** keep phone, external GPS, GPS-capable weather station, manually entered and SLM-reported coordinates as distinct sources. Preserve source device/model, latitude/longitude datum, fix time, receipt time, accuracy/fix validity and whether the position describes the meter or the phone/PC. A remote PC's location must not silently be assigned to a remote SLM. The user clarified that no external device connection to B&KG is assumed: prioritize reading SLM GPS and sending typed or app-device coordinates. Public builds have no preset personal location. Do not auto-detect or upload location at startup.

**Local export option:** first add explicit validated coordinate entry/connector selection, then optional per-row source/time/accuracy fields and Google Maps/OpenStreetMap links. Keep local location separate from instrument metadata. Maps open only on deliberate click. PDF remains a separate future export feature.

**Implemented text-slot option:** the location panel uses live enabled-slot String access, coordinate validation, preview, two confirmations, arming, one PUT, read-back and a durable audit. It requires idle Activated state and refuses changed/expired previews. Real write/save acceptance is pending; see [LOCATION_TRANSFER.md](LOCATION_TRANSFER.md). Native GPS injection and AppData association need independent vendor/protocol evidence; do not guess a URL or upload XML/JSON merely because the container accepts POST.
