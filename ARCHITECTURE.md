# B&KG — Current Architecture

- BnKG_Run_Python.py: Python 3.12–3.14 source launcher, optional reuse of project .venv, clear dependency errors.
- core/webxi.py: bounded allowlisted JSON/PNG reads, identity/action metadata, optional in-memory password, no redirects/ambient credentials. Only armed and capability-checked StartPause/Stop/Identify writes (measurement actions also state-gated); Stop requires two confirmations; ambiguous outcomes disarm without retry.
- core/discovery.py: explicit mDNS Web-XI browsing and bounded local IPv4 scanning. Maximum /24, 12 concurrent workers, cancellation, separate identification versus merely responding IPs.
- core/device.py: Smooth, Ambient and Events synthetic modes; seeded randomness available to tests.
- core/parameters.py: catalogue, sample provenance, LAF raw/100 conversion and same-snapshot differences. Device sequence conversions are in core/measurements.py.
- core/safety.py: routine measurement toggle/Identify and consequential stop classification; other writes blocked.
- core/sessions.py: worker-owned SQLite session with exclusive timestamped file creation, committed samples/events and closure metadata.
- core/export.py: read-only SQLite backup snapshots and seven export formats including HTML, preserving origin/quality, selected parameters and optional descriptor-backed spectra; formula-safe spreadsheet text.
- ui/worker.py: acquisition/client/SQLite ownership. Live sample updates are distinct from explicit captured samples. Start file logging enables capture; stopping capture closes logging. Pause demo emits no repeated samples. SLM screen reads while its page is selected or explicit local screen recording is active.
- ui/discovery.py: separate cancellable discovery QThread; acquisition remains independent.
- ui/components.py: appearance toggle, inline help and responsive view-only screen widget with bounded PNG dimensions.
- ui/window.py: local controls separate from SLM panel, newest-record table/trend (1–999, default 100), origin labels, themes and asynchronous shutdown of all active workers.

Exports run in an independent worker while acquisition and logging continue. Selecting a different session for export retains the existing stop-logging guard. Standalone/portable builds are authorized but existing assets predate the adaptation; no installer is requested. Broader validated measurement mappings and deeper hardware acceptance remain pending.

## 0.3.0a1 data views

core/measurements.py interprets supported device descriptors, sentinels, CPB axes and configured percentile aliases. WebXiClient remains worker-owned, fixed-read-root and guarded-write only. Samples carry spectra/metadata/descriptors; the raw log retains acquisition context. ui/live_views.py separates instrument Frequency/Metadata from a local DemoPage timer and simple CSV. Instrument receive handlers reject simulation-origin samples. ScreenPane owns only the latest PNG/pixmap and uses PC monotonic time for frozen/stale indicators. About artwork is original inline SVG. Screen recording now has a separate bounded worker/process boundary; see docs/RECORDING_PLAN.md.

## 0.3.0a2 status and location boundary

Battery/Disks reads are fixed verified device roots, refreshed about every five seconds and optional to measurement acquisition. Metadata renders units/enum names. core/location.py validates coordinate drafts; WebXiClient owns single-use expiring previews and the one permitted MetadataNText writer. It rechecks idle state, live access, enabled Text type and unchanged old value/name; two confirmations/arming/read-back and a durable worker-owned JSONL audit are required. No generic settings writer or native GPS injection exists. ui/location.py performs no networking.


## Standing requirements for future measurement views — 2026-09-27

[MEASUREMENT_SEMANTICS.md](docs/MEASUREMENT_SEMANTICS.md) defines the required source/period contract for future acquisition, saved-result, presentation and export changes. Prefer direct SLM Z/C/A values; retain descriptors and raw data. Any necessary calculated weighting remains a distinct, visibly labelled result with its inputs, method and period preserved through exports.

Keep whole-measurement cumulative Leq, short-term interval Leq (125 ms only when actually verified) and current time-weighted LAF/LZF distinct. Model aggregation/time basis independently of Live/Saved source mode, output/polling frequency and UI refresh. In particular, the existing current `CPBLZF250ms` mapping does not establish a 125 ms interval Leq. Chart series, totals, one-third-octave histograms and saved views must retain these semantics. These are design requirements, not a claim that new data modes or labels have been implemented.


## Adaptation presentation boundary — 2026-09-28

`core/spectrum.py` provides frozen `SpectrumFrame` and `SpectrumSeries` values and conservative measurement-scope classification. It does no networking or acoustic weighting synthesis. It retains direct descriptors, axes, nullable values, scalar context, PC receipt time/state/quality and supplied raw measurement identity/time metadata. An output period is separate from an integration interval. Compatible comparison requires the same axes, origin, units and measurement/time basis; unknown classifications are not automatically overlaid.

`ui/frequency.py` owns independent live and frozen references and presentation-only controls. Frozen frames cannot change with subsequent mutable samples. A frozen view is local and transient; it is not a saved-device-file parser or persistent snapshot export. Main Frequency accepts instrument origin only; Demo accepts simulation only. Existing acquisition/session raw descriptor storage and export formats are unchanged.

`ui/presentation.py` shares tiles, a display-only level bar, a mini-spectrum and stable `Page` IDs. `ui/preferences.py` applies local QSettings changes only after acceptance. `window.py` retains worker/safety ownership; rendering does not configure the SLM. Demo uses its own timer/device and bounded table/CSV, repeatable random seed and six-step scripted event. Synthetic bands are illustrative, not an acoustic calculation.

New features require no additional dependencies. Later history/download/export/recording workers must retain independent resource ownership and the measurement rules above.


## Saved-data boundary — stage 3, 2026-09-28

`core/history.py` opens only existing version-1 BnKG SQLite tables via `mode=ro`, query-only/trusted-schema-off settings and a query progress deadline. Keyset pages hold at most 100 summaries and a fixed upper ID until Refresh; full bounded JSON is fetched only for an explicitly inspected row. Session identity is rechecked across requests. It neither migrates nor writes the source. Each request owns/closes its connection and transaction.

`ui/history.py` owns a cancellable `HistoryQuery` thread independently of acquisition and export workers. Generation checks discard late cancelled results; MainWindow waits for it on shutdown. Reconstruction uses saved raw outputs, sequence descriptors and setup only, through the existing decoder. Missing descriptors never borrow current settings. Simulation/unknown origins cannot populate instrument Frequency. `ui/frequency.py` keeps a separate immutable saved-file frame and file/session/row label, distinct from live and transient frozen frames.

`core/device_files.py` registers advertised File children, preserving literal dollar path delimiters. Download is a single GET stream with 256 MiB/120-second limits, identity content encoding, HTTP 200/length checks, cancellation and incremental SHA-256. An exclusive owned partial file is atomically linked to a new local destination only on success. `ui/device_files.py` owns its separate file worker; no Open/GetArchive/Delete action is added. Raw native bytes stay opaque; BKC decoding requires further evidence. No new dependencies or device-write policy changes.


## Charts and export boundary — stage 4, 2026-09-28

`core/trends.py` freezes finite recorded scalar values with source/state/quality and timezone-aware PC receipt timestamps. `ui/charts.py` renders up to three explicit parameter scopes, time-window filters and a nearest-record cursor. Missing values, source changes, non-increasing clocks and gaps over three seconds break lines. No resampling or acoustic averaging is performed. Live charts share the 1–999 capture cap; historical charts show only the current 100-row page. Clear view only never clears the database.

`ui/exporting.py` owns a cancellable ExportJob QThread with copied options and throttled progress. `core/export.py` copies the source via the SQLite backup API in bounded page steps with a 120-second deadline, closes the source connection, then streams the consistent private snapshot. Formatting cannot hold a read transaction on the acquisition database. Copying still competes for disk/brief database access and needs space for the snapshot plus output; it does not promise zero latency. Snapshot scope is recorded in metadata.

Exports preserve the six existing formats and add escaped standalone HTML. Optional spectra decode each row's own retained descriptors/setup, never live settings or calculated weightings; JSON/NDJSON/XLSX/HTML retain band axes, scope, nullable values and context. The existing catalogue identifies calculated scalar fields. Raw JSON/NDJSON context can be omitted explicitly. Each worker owns its connections and temporary files; cancellation/failure discards partial output. Final publication uses an atomic exclusive hard link on a supporting filesystem (e.g. NTFS), so a concurrently created destination is never overwritten. XLSX packaging may finish before cancellation cleanup; shutdown waits. PDF/DOCX, embedded chart images and broad report configuration remain future work. No dependencies changed.


## Display/recording boundary — stage 5, 2026-09-28

`ui/components.py` retains the native PNG/pixmap and status age, with local scale/render controls, processed saving and an independently owned fullscreen dialog. The dialog is retained until Qt destruction (not merely its finished signal) to avoid a close-event lifetime race. Native PNG saving is unchanged. There is no mouse/key forwarding.

`core/recording.py` owns original-frame archive/timing data and external argument-list FFmpeg/ffprobe invocation. `ui/recording.py` owns a QThread, an eight-entry non-blocking queue, stop/cancel events and local controls. Acquisition emits immutable PNG bytes plus PC receipt timestamps directly to the thread-safe enqueue method; no file I/O or widget mutation occurs there. The recorder validates and writes in its own thread, retaining at most 3,600 small ledger rows. Encoding occurs after capture stops. Original frames remain recoverable on cancel/failure. Shutdown waits for both the recorder and child process; subprocesses are hidden on Windows and never use a shell. Limits and timing/publication policy are documented in `docs/RECORDING_PLAN.md`.

`ui/worker.py` maintains independent page-display and recording-display flags. Ending recording restores page-based behavior; disconnect clears recording state. A recording never enables simulation acquisition or automatically reconnects/wakes an SLM. Single advertised arrows reuse the existing safety backend; the worker additionally rejects stale/changed screen context and old confirmations, then disarms. The SLM was offline throughout stage 5; mock checks are not live hardware validation.


## Connection/local-context boundary — stage 6, 2026-09-29

`ui/diagnostics.py` consumes existing identity/status/control/sample signals only; it does not construct network clients. It keeps bounded state transitions and scalar allowlisted identity fields, marks retained evidence and composes a local support summary without measurements, passwords, report drafts or raw errors. Device identity is opt-in for copying. Existing discovery stays on its own worker; only its progress presentation changed. `core/webxi.py` maps specific Requests failures to credential-free guidance and preserves protocol routes/timeouts/write policy.

`core/report_context.py` validates only project/operator/site/notes, adds explicit local-user provenance and produces safe UTC log filenames. `ui/report_context.py` owns a local draft in QSettings. MainWindow sends a fresh copy with log-start; the acquisition worker validates/snapshots it in SessionStore before recording rows. New `local_report.*` metadata keys are additive to SQLite schema v1; no existing session/row or instrument metadata is modified. Existing exporters preserve this context through metadata-bearing formats and apply their existing formula/HTML escaping. Legacy SessionStore/log-start callers without context remain compatible.

Metadata filters change presentation while retaining selected Dashboard keys. Location map links are composed from validated coordinates and opened only by user action; the existing single-slot writer is unchanged. `ui/guidance.py` provides shared offline help through Connection/About. No new Python dependency or external runtime was introduced.


## Local review boundary — stage 7, 2026-09-30

`core/review.py` defines immutable review/marker/row-reference records and bounded version-1 JSON snapshots. Fingerprints cover exact SQLite row fields, including raw context; matching uses session identity, origin and integer sample ID, never timestamp alone. `open_history` provides read-only schema/identity checks. No migration or updates are made to original logs. Four-second verification, size/count limits, cancellation and an exclusive hard-link publication boundary constrain the work. Source relocation and appends preserve association; changed marked rows are rejected. These checks establish association, not authenticity, certification or continuous integration coverage.

`ui/review.py` contains local review controls and a saved-spectrum preview using the existing spectrum renderer. The existing `HistoryQuery` owns reads, marker creation and snapshot import/export. UI selections carry a stable `TrendPoint.record_id`; debouncing coalesces selection reads. Markers draw recorded points in four linked lanes. Data, chart and spectrum stay linked by row ID, while the main Frequency page changes only through explicit Load. Unsaved drafts have discard guards and are not recovery storage. Live buffers, acquisition, device policy and measurement exports are unchanged. No exclusion calculation, interpolation, weighting synthesis or interval-energy inference is performed.


## Parameter visibility boundary — stage 8, 2026-10-01

`core/parameter_views.py` classifies the existing scalar catalogue and validates bounded version-1 visibility presets: 20 named selections, 60-character unique names, 32 KiB JSON, known non-calculated IDs only. A legacy singleton string is treated as one exact ID rather than substring membership. Empty selections remain valid. Invalid/forward-version presets are preserved, not silently rewritten.

`ui/parameters.py` owns search/group/selected filters, explicit bulk changes/undo, preview/apply and local save/delete controls. It emits one selection signal per bulk edit and preserves hidden checkboxes. `MainWindow` retains its existing `checks` mapping, `visible` key, default migration, LAF-first order and Dashboard updates. Named presets use the separate `parameter_visibility_presets_v1` QSettings key and never auto-apply. These components contain no transport, worker commands, acquisition/export changes or acoustic calculations. The catalogue describes supported names and semantics, not fresh instrument availability evidence.


## Export-option boundary — stage 9, 2026-10-01

`core/export_profiles.py` provides immutable normalized export configurations, strict bounded settings serialization and content descriptions matched to current format writers. `ui/export_profiles.py` previews, applies and maintains named options under `export_profiles_v1`, independently of Dashboard presets. Invalid stored schemas/content are preserved rather than silently migrated. No profile contains measurements or paths and no profile auto-applies or starts a job.

MainWindow derives both content preview and job arguments from normalized options, rejecting empty/unknown parameter choices before a save dialog. Unsupported raw/spectrum flags are inactive. During export, option/source controls lock and the preview uses `ExportJob`'s captured options/source/destination, not mutable next-session state. Repeated identical logging updates do not reset preview scroll position. The existing exporter, seven file formats, independent SQLite snapshot, cancellation/shutdown and non-overwriting publication remain unchanged. The preview performs no source I/O and makes no data-availability/count/size claims.
