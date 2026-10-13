# B&KG user guide

1. Choose an edition using [the release chooser](../Readme-info-which-relese-to-get.txt). Extract Portable ZIPs completely. Start with the supplied launcher; the app opens disconnected with local capture/logging off.
2. For a safe preview, use **Demo Lab**. Its three scenarios and spectrum are synthetic. Enable demo table capture or simple CSV logging explicitly. Pausing/stopping produces no further samples and never controls the physical SLM.
3. To read a real meter, use **Connection** and its current address, or explicit discovery. See [connection guidance](../CONNECTION_GUIDE.md). Credentials are not saved. Enable Web server display on the physical instrument if screen images are unavailable.
4. **Dashboard**, **Parameters** and **Frequency Analysis** show instrument outputs where supported. Current and cumulative data are different. Unavailable fields are not zero. Some information can be incomplete, delayed or incorrect: double-check on the instrument and in the official documentation.
5. **SLM screen** mirrors native PNGs and retains the last image with status when stale/disconnected. Save original PNG preserves its received dimensions. Wake / Identify is a guarded illumination pulse, not a power-on command. It does not start a measurement. Start/Pause and Stop affect the real measurement; only use deliberately. Arm once per connection; Start/Pause/Stop do not ask repeatedly. Acknowledge the measurement view once for arrows. Menu / OK opens the menu and locks keys; remote settings/menu editing remains protected.
6. **Data table** contains optional local capture/logging. The newest selected records remain in memory; logging retains the complete captured session on disk. Stop logging leaves capture active; Stop capture/Disconnect closes the log. **Sessions & export** browses local saved rows and exports selected sessions. The history browser can load supported descriptor-backed saved spectra into Frequency without stopping monitoring.
7. **Device files** provides an explicit read-only saved-file inventory with count/date filtering and directory paging. It can download an advertised file unchanged with progress/cancel and a SHA-256 result. It does not decode BKC or open a measurement on the instrument. See [saved data guidance](DEVICE_FILES.md).
8. **Metadata** displays available fields and access flags. Location starts empty; a manually entered coordinate is not a GPS fix. The guarded text-slot transfer does not change native GPS and needs deliberate review/two confirmations. Save-persistence acceptance remains pending.
9. **About** includes clickable/copyable project, developer, related HBKG, Discussion and Ko-fi links, credits and limitations. Support is optional.

Portable launchers store user data in the extracted package's `data/` folder. Running the EXE/Python launcher directly uses Windows per-user app-data unless `--data-dir` is supplied. Back up your data before replacing/updating a package. Do not overwrite a running version or delete your only data copy.

Windows x64 builds are unsigned development alphas. Office-PC/clean-Windows and actual-DPI acceptance are still pending. 2255 read-only behavior and supervised Identify/arrows were checked on one firmware; 2245 and other firmware remain unverified. Original-frame recording, FLAC capture, playback, AAC/Opus and estimated paired MP4 export are implemented. Native BKC decoding is limited to the validated 2255 total profile; unsupported layouts remain raw-only. See RELEASE_NOTES.md for validation limits.


## New source-workspace features — 2026-09-28

These capabilities are included in the current source and refreshed release packages.

Use **Display…**, next to the appearance controls, to adjust reading size and Dashboard density, show/hide the LAF bar or mini-spectrum, choose display ranges or reset spectrum colors. These are local preferences. A level-bar range is not a safety/exposure threshold. Dashboard receipt age describes the last sample received by this PC.

In **Frequency Analysis**, choose the source separately from its measurement meaning. **Current time-weighted L** is different from **Whole-measurement Leq** and **Short-interval Leq**. The interval filter remains empty without supported data and verified integration duration; Fast weighting and output cadence do not create 125 ms Leq. Instrument A/C/Z series appear only when provided, with matching axes/time basis for comparison. Turn off Compare for one series, or use weighting checkboxes for visibility. Click a band for exact values; use the table for missing or out-of-range readings. Plot colors and ranges do not change device settings.

**Freeze live source** retains a local immutable snapshot with its scalar/context data. Select Live source to return to incoming readings. A frozen snapshot remains unchanged across live updates/disconnection, but is replaced by the next freeze and lost when the app closes. This is not a saved file: use existing session logging when durable acquisition records are needed. Historical SQLite rows can now be loaded through Sessions & export → Browse history; they appear under a separate Saved session source. Calculated weighting views are not implemented.

In **Demo Lab**, choose a scenario and seed before starting. The same seed gives repeatable readings; **Inject demo event** adds a short scripted transient. Use the Readings & data or Frequency tabs. Paused/stopped readings are retained and labelled. Synthetic band shapes are illustrations rather than a physically consistent acoustic model. Demo CSV remains a simple main-value export, not a spectral dataset.


## Capture charts and exports

In **Data table**, use **Columns…** to choose visible scalar columns, turn off **Auto-scroll** to inspect rows, or **Clear view only** to empty the local table and charts. File logging continues and saved rows are preserved. The **Charts** tab offers up to three quantities, time windows and a click cursor for recorded values/quality. Captions distinguish current Fast levels, whole-measurement Leq, peaks and Calculated values. Times are PC receipt times; missing data, source/clock changes and gaps over three seconds break lines. There is no interpolation or acoustic averaging. **Browse history → Chart this page** applies the same tools to the current page of at most 100 rows.

In **Sessions & export → Export**, choose parameters and a new output filename. CSV, TSV, TXT, JSON, NDJSON and XLSX remain available; **HTML** adds a standalone measurement report for a browser. JSON/NDJSON can include stored raw context. JSON/NDJSON/XLSX/HTML can include supported direct spectra reconstructed from each row's saved descriptors, with axes, nulls, measurement scope and context. Missing spectrum context is never inferred. Flat text formats contain scalar columns; use a structured format or XLSX for band details.

Export progress and cancellation run independently; monitoring and file logging continue. Exporting the current log uses a consistent snapshot and excludes rows added after that snapshot completes. To select a different export log, stop file logging first; historical browsing has a separate selector. Allow disk space for a database copy plus output. Snapshot copying has a two-minute limit. Existing destinations are preserved; publication needs a filesystem supporting local hard links, such as NTFS. Cancellation removes owned partial files, although XLSX packaging may finish before cleanup. HTML is a simple measurement report, not a certification; chart images, PDF and DOCX remain planned.


## SLM display tools and recording

Use Fit (both dimensions), 100%, 200% (default) or 400%. Filters are Pixel — Nearest Neighbor (default), Sharp — Lanczos and Smooth — Bicubic. Fullscreen display opens a separate view; Escape returns. Hide controls maximizes viewing space. Original PNG saving keeps received bytes; processed PNG saving follows the selected display scale and omits the status overlay. Check the retained-image status before exporting.

**Start screen recording…** preserves new original PNGs and receipt/gap metadata in a fresh folder, independently of scalar logging. Recording continues on other pages and shows a workspace status banner. Stop finishes accepted frames; Cancel keeps originals. Optional MP4 needs user-selected external FFmpeg and ffprobe; it is processed lossy video with held frames across gaps, not a native video stream. No external encoder executable is bundled and no automatic wake occurs. Audio uses a separate deliberate capture workflow. See [display and recording guide](RECORDING_PLAN.md) for limits, recovery and pending validation.


## Connection diagnostics and local report details — 2026-09-29

**Connection** distinguishes current state from retained device identity. It shows the last observed firmware when supplied, advertised controls and sample freshness/counts; it does not certify every feature or licence. Timeout, unreachable address, denied access, TLS and missing-endpoint messages offer separate guidance. Discovery remains explicit; an advertisement, ping or HTTP response is a candidate, not proof of usable SLM access.

**Copy support summary** copies a local runtime/state/count summary to the clipboard. Device identity/address is omitted unless you enable its checkbox. Passwords, raw measurement values, metadata values, local notes and arbitrary error messages are excluded. Nothing is uploaded. Review a summary before sharing.

**Metadata → Instrument fields** offers search and groups. Hiding a row with a filter does not uncheck it on the Dashboard or change acquisition/access permissions. **Location / transfer** retains the existing guarded single-text-slot workflow and adds a clickable/copyable map link for the current coordinate draft. Clicking the map shares those coordinates with OpenStreetMap; no map is fetched automatically. A manual default/draft is not an acquired fix.

**Metadata → Local report** holds project, operator, site and notes separately from SLM metadata. **Save local draft** retains the draft on this PC. Starting file logging validates/saves the draft and copies it into that new log; edits during logging affect future logs only. Existing SQLite sessions are never retroactively edited. Project/operator/site are limited to 120 characters each and notes to 2,000. Optional project/site filenames use sanitized fragments and a UTC timestamp; the example previews the pattern. This does not change the instrument's save filename or metadata slots.

Local report context appears as `local_report.*` in JSON/NDJSON metadata, XLSX Summary and HTML reports. CSV/TSV/TXT remain scalar tables. Drafts, filenames and exported context may contain private project/operator/site details; review before sharing. No automatic coordinate acquisition or coordinate-to-site assignment is performed.

Use **Workflow help and current capabilities** in About, or **Connection help**, for offline instructions on measurement meanings, logging/export, display/recording and the three metadata sources. Existing project/support links remain clickable and copyable.


## Saved review and local markers — 2026-09-30

In **Sessions & export → Browse history**, select a row or click a chart point. The selected sample ID links the table, cursor and saved spectrum preview. **Chart this page** shows only the current 100-row page, with the spectrum alongside on wide screens or below in a scrollable view; choose among the row's actual available spectra. **Selected values** contains the recorded values, quality and source explanation. Missing descriptors mean unavailable spectrum. The full **Load saved spectrum in Frequency** action remains explicit and independent of live readings.

**Review markers** provides M1, M2, M3 and Exclude. Select a row and Add marker for a single record. For a range, select its first row, use **Set range start**, select its last row on the same page, then Add marker. The range follows sample-ID order, not elapsed energy or a guessed integration window. **Use single row** clears the range anchor. Add an optional note to explain your classification; the app does not prescribe an acoustic meaning for M1/M2/M3. Marker lanes show the marked points, not continuous coverage through gaps. Duplicate timestamps overlap; Rows is the authoritative way to choose a specific sample.

**Go to marker first row** navigates to its recorded sample, including on other pages of the current snapshot. Remove selected local marker changes only the review draft. **Exclude never removes readings, filters exports or recalculates Leq.** There is no back-erase, live marker capture, inferred interval energy or compliance calculation.

Use **Save review as…** to create a new `.bnkg-review.json` snapshot. Originals and existing snapshots are never overwritten. Save again under a new filename after changing markers. Save on a filesystem supporting hard links (such as NTFS); unsupported publication fails without replacing files. Opening another session, refreshing or closing warns before discarding unsaved marker changes. Drafts are not crash recovery backups. Cancelling a save may leave a fully published snapshot if publication already finished.

To resume, open the corresponding SQLite log, then **Open review…**. The app verifies session identity/origin and every marked row's fingerprint. You may rename/copy the log or add later rows; changed or missing marked rows and other sessions are rejected. A review contains notes and references, not the measurements themselves: keep the original log alongside it. A fingerprint is not a signature or proof of measurement validity. Review notes and identifiers may be private; these files are ignored by Git by default and are not merged into ordinary measurement exports/reports.

Limits: 128 markers per snapshot, up to 100 rows per marker within one page, 1,000 total row references, 500 characters per note and 1 MB per file. Verification stops after four seconds or cancellation. Source logs remain read-only throughout.


## Parameter selection and local presets — 2026-10-01

**Parameters** controls which direct instrument scalar values appear on the Dashboard. Search matches IDs, descriptions, measurement scopes and formulas; multiple words must all match. Use a measurement group or **Selected only** to narrow the list. Filtering does not change any checkbox. The count includes selected parameters hidden by the filter. **Select shown** and **Clear shown** affect only selectable rows matching the filter; **Undo selection change** restores the previous bulk selection. Manual checkbox changes clear that one-step undo.

Each row shows units, measurement scope and source/availability guidance. Current Fast/Slow, whole-measurement equivalent levels, peaks/extrema, exposure and configured percentiles/statistics stay distinct. Selecting a value does not enable an instrument output or change its configured basis. Calculated differences show their formulas and remain separately displayed on the Dashboard; they cannot be included in direct-value presets. Fast weighting never creates an interval Leq.

Choose a built-in or saved preset to **preview** its parameter IDs. Only **Apply preset** replaces the entire Dashboard selection, including hidden rows. **Recommended** restores the existing recommended visibility, and the other built-ins group current levels, measurement equivalents, peaks/extrema or percentiles. These are display choices, not measurement or compliance configurations.

Enter a name and use **Save new preset** to retain the current full selection locally. Names are limited to 60 characters and 20 saved presets; names must be unique, including case differences, and cannot replace a built-in. Save an intentionally empty selection if desired. **Delete saved preset** asks before removing the selected named preset and keeps the current Dashboard unchanged. Presets are stored in `preferences.ini` alongside existing visibility settings; there is no preset import/export or automatic instrument setup. Unsupported/corrupt stored preset data is retained with a message and editing disabled, while built-ins and ordinary selection remain available. Disk-save failures are reported.

Dashboard ordering and LAF-first placement are unchanged. These presets do not alter chart selections, capture, logging, measurement exports or the SLM. Favorites, custom ordering/aliases and per-value precision remain future work.


## Export presets and content preview — 2026-10-01

**Sessions & export → Export** now describes what the current format/options will include. This is an options preview; it does not open or scan a source file, estimate size, count rows or guarantee that spectra exist. Export itself validates a consistent saved-session snapshot. Select at least one scalar parameter, including when exporting spectra. Unsupported raw/spectrum options are inactive for the selected format.

- CSV/TSV/TXT contain scalar columns plus PC receipt time, elapsed connection seconds, state, origin and quality. TXT/TSV use tabs. They omit session metadata, parameter catalogue/formulas, event records and decoded spectra. Calculated columns contain recorded results; consult their formulas in the preview or a richer format.
- JSON/NDJSON, XLSX and HTML include session metadata and the selected parameter catalogue. Metadata may include private local project/operator/site/notes. XLSX alone includes the existing Events sheet; JSON/NDJSON and HTML do not include session event records.
- Decoded direct spectra are optional in JSON/NDJSON/XLSX/HTML, requiring retained descriptors. They carry axes, measurement scope/weighting/period, descriptor/measurement context and matching broadband values. They are not filtered by scalar selection.
- Raw outputs/context are optional in JSON/NDJSON and independent of scalar selection. They may contain unselected readings, original spectra and private metadata. Disabling raw does **not** remove session metadata or requested spectral context. When every catalogue scalar is selected, JSON/NDJSON also preserve additional stored scalar keys for compatibility.

Use **Show export presets** for built-ins and named saved options. Choosing a preset only previews it; **Apply export preset** changes format, scalar selection and raw/spectra options together. It does not start exporting or change Dashboard visibility. **Save new export preset** saves the current options under a unique name; limits are 20 names, 60 characters per name and 32 KiB total settings. Existing names cannot be overwritten. Confirmed deletion removes only that saved preset. Unsupported stored preset data is retained with editing disabled; built-ins and manual options remain usable.

Presets are local in `preferences.ini` and contain no source/destination path or measurement data. They never auto-apply on startup. Export options and the source selector lock while a job is running; the preview then identifies the actual captured source, destination and options. A later logging-session change does not redirect that job. Cancel/shutdown keep the existing cleanup behavior. Local review markers and Exclude labels are never merged into exports or used for recalculation. Original logs remain unchanged, and existing export destinations are preserved.

Optional screen MP4: see [FFmpeg setup](FFMPEG_SETUP.md) for downloads, installation paths, Browse controls and licensing. Original PNG recording does not need FFmpeg; FLAC audio capture uses its separate workflow.

XLSX exports preserve oversized descriptors/context in a **Text chunks** sheet. A cell beginning `Text chunks:` names the reference: sort its parts by Part, JSON-decode each string, then concatenate to recover the original text. Small values remain inline. JSON/NDJSON remain convenient for programmatic provenance.
