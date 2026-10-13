# B&KG — Instrument data and metadata capabilities

Verified read-only on 2026-09-19: HBK 2255, firmware 1.3.0.478, Web-XI licensed. This is evidence for that device/configuration, not a claim of identical 2245 or other-firmware support. All URLs use the address selected after connection; historical IP examples are not defaults.

## 2026-09-20 verification update

See [claim-by-claim findings](METADATA_GPS_FACT_CHECK.md). HBK specifies integrated GPS for the 2255; a no-value sentinel does not imply absent GPS hardware. Phone annotation location is separate. Connected GPS/weather-station support depends on the exact model/interface. Battery/disk status and microphone setup fields are now selectable with units and enum labels; a narrowly scoped reviewed location-text writer is now available (mock-tested only); native GPS injection remains unverified. See [location transfer](LOCATION_TRANSFER.md).

## What you can see

Open **Metadata**, select/deselect fields in Show, and view selected values on Dashboard. The table shows actual values, descriptions/domains in tooltips, and device access flags. Selection persists locally. Acquisition refreshes values while connected; setup access metadata refreshes approximately every 30 seconds. No metadata writes run automatically. Location transfer is an explicit exception to the otherwise read-only metadata view.

| Data | Observed availability | How to view/edit |
| --- | --- | --- |
| Latitude, longitude, altitude and precision | Read-only Outputs; no-fix double sentinel was returned during testing | Display in Metadata. Use the instrument's own GPS and appropriate reception. B&KG shows the sentinel as Unavailable. No verified API for injecting PC/app coordinates was found. |
| Serial/hardware/software, timezone, transducer, sensitivity/calibration, overload/underrange, measurement counter and times | Read-only output fields when exposed | Select in Metadata. Values retain device format; ElapsedTime is labelled raw device ticks, not assumed seconds. Never use this page to recalibrate. |
| User metadata | MetadataAll plus Metadata1…Metadata9 slots | Configure on the physical SLM. Enable user-defined metadata and slots, then set names/types/values. Consult the device manual for its metadata setup/review screens. |
| Slot name, text, number, picklist entries/type | Text / Picklist / Number types advertised. Names/text/types/values were ReadOnly while all slots were disabled; slot-enable and MetadataAll advertised writable | B&KG displays current flags and values. Do not assume disabling/enabling automatically proves fields writable. Reconnect/allow refresh after changing device setup. General metadata editing is not implemented; the location panel can replace one already-enabled writable Text-slot value after explicit review. |
| Location name, operator, project label | No dedicated fields found in the tested setup; generic metadata slots can hold these labels if configured on the instrument | Name slots Location, Operator or Project on the SLM. This annotates measurements and is **not** a change to device storage filenames/projects. |
| Project name / saved measurement filename | No verified setter found | Use supported physical-SLM/manufacturer workflows. B&KG does not rename files, rewrite folders or treat the network nickname as a project name. Local B&KG log filenames are independent timestamped names. |
| Weather | Read-only fields such as wind/temperature/humidity/pressure/rainfall if exposed | Actual validity/connected accessory support must be checked on the SLM. Merely exposing a field does not prove the accessory is attached. |

`ServiceGpsLocation` was read-only and enabled; it is not a latitude/longitude setter. `/Configuration/Settings/metadataSetup0.xml` and `defaultmetadataSetup0.xml` advertised file resources, and `LoadMetadataSetup` referenced a downloaded XML setup. No verified schema/import workflow was established; B&KG does not upload guessed XML. `AppData` advertises annotation storage, which alone does not prove GPS injection or project naming. `Data` and `CurrentMeasurement` describe measurement storage/read-only directories, without a verified name setter. Settings writes and annotation uploads remain outside this implementation.

## Real levels and spectra

- GET `/webxi/Applications/SLM/Outputs?recursive` returns measured values. The root describes total measurement outputs, not a historical logging series. Instantaneous Fast outputs are also present.
- GET `/webxi/Sequences?recursive` supplies scale, units, averaging mode, vector length and CPB axis metadata. GET `/webxi/Applications/SLM/Setup?recursive` supplies current percentile slots and range. `?recursive&metadata` supplies access/schema information, **not** the current value tree.
- B&KG scales supported Int16 dB values with the device's Scale/Offset. Int16 minimum -32768 and unsupported/missing values become unavailable, never fictitious negative levels. IsPower/unsupported units/types are withheld. Raw values/descriptors remain in logs.
- Current REST `CPBLZF250ms` and equivalent weighted outputs map to the corresponding 250 ms sequence only when its PeriodTime matches. CPB vectors must match the advertised length. Base-10 1/3 and 1/1 octave axes are supported; other axes are withheld. Exact centres follow `10 ** (0.1 * (first_band + i * 3 / fractions))`; the table includes exact centres and conventional nominal band labels. This extends the official normal-range example using the device's first-band descriptor; extended 36-band data were read on the instrument.
- L10/L50/L90 labels are used only when matching configured StatisticsPercentile slots are present. **BBStatisticsBasedOn** in Metadata identifies their actual basis. LN1…LN5 are also available as direct slot outputs; never assume a fixed percentile from a slot number.
- Current readings work while the measurement is stopped; total LAeq/CPB equivalents can be unavailable then. Enable the wanted measurements on the physical SLM. B&KG does not enable weights/sequences automatically, unlike some example scripts.
- SLM values are not computed locally. The explicitly labelled local LCeq−LAeq difference is separate and uses the latest polled inputs; the REST snapshot is not atomic. No locally calculated value replaces a missing SLM result.

## Time, quality and saving

PC UTC receipt timestamps and PC connection elapsed seconds are not SLM acquisition timestamps. Output time strings/raw ticks are retained separately. Overload/underrange flags are visible in Metadata; this alpha does not claim full sequence-quality decoding or metrology acceptance. Polling reads setup before/after acquisition and rejects changed band/percentile setup, but cannot guarantee an atomic instrument snapshot.

Optional local logging keeps raw Outputs and per-snapshot sequence/setup/metadata context in SQLite. JSON/NDJSON exports retain that nested context, including spectra. Flat CSV/TSV/TXT and the XLSX Time Series use the parameter catalogue; use JSON/NDJSON for complete raw data. Metadata may include location/operator details; review before sharing.

## Primary references

- [HBK Open Interface repository](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter)
- [Web-XI protocol specification](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf), sequence descriptors and metadata
- [Official metadata example](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Python%20examples/02%20-%20Metadata.py)
- [Official CPB plotting example](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Python%20examples/08%20-%20CPB%20streaming%20Plot.py) and its declared slm-open-api-package 0.2.5 helper: bar spectrum, normal-range base-10 band calculation. Independently implemented; source not copied into BnKG.
- [2255 instruction manual](https://www.bksv.com/downloads/2255/instruction%20manual/be1917.pdf), device setup, metadata and GPS workflow
- [Cirrus NoiseTools octave/third-octave analysis overview](https://cirrusresearch.com/product/octave-third-octave-band-ln-calculation-module-for-noisetools/), product reference for band-oriented analysis

Private raw device captures live under excluded `.cache/batch4`; no credential/network settings dump is committed. Sanitized synthetic test fixtures verify decoder behaviour. The UI does not depend on online documentation or an OpenAI account.
