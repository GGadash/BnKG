# Changelog

## 2026-10-10 — Restart after Stop fix (source)

- Normal Start/Pause now accepts ResultMeasured after Stop. Already-stopped Stop is a harmless no-op. Brief transitional states receive bounded GET-only settling; toggles are never retried.
- Live start/pause/resume/stop/restart and Stop-from-Paused passed with persistent arming; Wake/Identify acknowledged. No reset used.

## 2026-10-10 — Screen sizing and session controls (source)

- Fit now uses the visible width and height with independently scrolling controls; defaults are 200% and Pixel. Added 400%, real Lanczos and Bicubic filters; originals stay unchanged.
- Large full-area Arm control with visible armed/off states. Successful routine actions retain arming; measurement controls and acknowledged arrows no longer ask repeatedly.
- Centre Menu / OK opens once from an acknowledged measurement view, then locks keypad navigation. Settings retain confirmations and critical operations remain blocked.


## 2026-10-10 — Media playback/export and native totals (source)

- Added local Qt Multimedia playback, native AAC/Opus copies and paired H.264/AAC export with receipt-time alignment, explicit uncertainty and manual offset. Original captures remain unchanged.
- Added bounded native BKC inspection and limited 2255 firmware 1.3.0.478 totals: 174 values match independent ENP/NP XLSX exports; direct A/Z spectra load into saved Frequency. Other profiles stay raw-only.
- Handled a verified startup timestamp reset by explicitly omitting one uncertain frame only from playable audio; raw bytes remain intact.
- Updated dependency notices for Qt Multimedia and its shared FFmpeg libraries. No new EXE/Portable builds.

## 2026-10-02 — Instrument audio and recording acceptance (source)

- Added explicit background FLAC capture, original-stream/hash/timing archives, safe temporary Analysis quality restoration and visible unknown-quality/calculated-rate provenance. Bounded websockets dependency and licence notices added.
- Hardened Wake/Start-Pause confirmations and disarming; critical controls visibly disabled and backend-blocked. No real measurement control tested.
- Ten-minute screen recording, interrupted-archive recovery and short real app-audio capture passed. Physical wake confirmed; return-to-sleep observation remains pending. See docs/RELEASE_NOTES.md.

## 2026-10-01 — Live acceptance and optional FFmpeg setup (source)

- Added local/saved/PATH FFmpeg pair discovery, missing-tool guidance, download/copy links and Browse controls; optional binaries excluded from Git, packages and transfer exports. Native AAC selected instead of FDK; no app audio feature added.
- Fixed stale current-sample retention on disconnect, losslessly preserved oversized XLSX context in referenced text chunks, and corrected sparse MP4 duration with B-frame reordering disabled.
- Bounded live 2255 acquisition/recording/reconnect/review/export/download and real encoder checks passed. See the dated acceptance report for remaining hardware/platform limits; packaged builds remain historical.

## Unreleased — HBKG adaptation, through 2026-09-29

- Stage 9: explicit local export presets, accurate per-format content/privacy previews and immutable running-job presentation. Preserved all seven export formats, original sessions and independent acquisition; no new dependencies.
- Stage 8: searchable/grouped parameter catalogue with scope/unit/formula details, filtered Dashboard selection and one-step bulk undo. Explicit preset preview/apply, bounded named local visibility presets and preserved legacy choices; no device configuration or acquisition changes.
- Stage 7: exact-row saved-history/chart/spectrum selection and a scrollable synchronized review view, retaining per-row descriptors and current/total/interval meaning.
- Local M1/M2/M3/Exclude review markers, point ribbons, cross-page marker navigation and separate verified JSON snapshots. Source logs/exports are unchanged; Exclude does not recalculate Leq. Bounded worker I/O, no-overwrite saves and unsaved-change guards; no new dependencies or hardware actions.
- Stage 6: clearer connection/retained-identity/access diagnostics, explicit discovery status and locally assembled support summaries with identity omitted by default.
- Searchable/grouped instrument metadata, separate local report drafts snapshotted into new logs, safe project/site filename option and explicit coordinate-map links. Existing guarded device-write policy preserved.
- Shared offline workflow help and current capability/availability descriptions; no new dependencies or hardware access.

- Stage 5: local fit/native/zoom and Smooth/Pixel display controls, fullscreen/hide-controls, distinct original/processed PNG saving, and supervised advertised arrows through existing safety checks.
- Bounded independent original-screen recording with timing/gap/hash ledger, stop/cancel/recovery and recording across pages; optional external FFmpeg/ffprobe MP4 pipeline with profile/CRF and validation. No bundled encoder/audio; live and real-encoder acceptance pending (SLM offline).

- Bounded multi-series capture/history charts with receipt-time windows, quantity/scope captions, gap handling and recorded-value cursor; selectable table columns, pause auto-scroll and clear-view-only controls.
- Independent cancellable exports from private SQLite snapshots while monitoring/logging continue; preserved six formats, parameter selection, optional descriptor-backed spectra/raw context and a standalone escaped HTML report. No additional dependencies.

- Read-only paged SQLite history with row inspection and descriptor-backed saved Frequency source; monitoring continues independently, legacy scalar logs stay readable and saved source data remains immutable.
- Advertised native-file GET downloads with cancellation, bounds, SHA-256 and no-overwrite publication; parent-folder navigation and metadata tooltips. BKC analysis remains deferred.

- Dashboard measurement-scope captions, sample freshness, optional current level/spectrum previews and persistent local Display preferences; existing B&KG theme retained.
- Direct compatible A/C/Z Frequency comparisons, distinct current/cumulative/verified-interval filters, immutable in-memory snapshots, cursor/table details and local scales/colors. Missing weightings remain unavailable; no weighting synthesis or new interval acquisition.
- Seeded isolated Demo with injected events, shared tiles and separate readings/frequency tabs; clear retained-data status and corrected text encoding.
- Conservative spectrum data model and focused acceptance coverage. Existing release binaries are unchanged; native decoding remains gated; stage 5 recording validation limits are listed above.

## 0.4.0a1 — 2026-09-20

- Standalone Windows EXE plus executable and Python Portable release tooling, curated docs/licences/source, checksums and corrected disconnected-startup verification.
- Clearer construction/accuracy warning; clickable/copyable developer, BnKG, HBKG, Discussions and both Ko-fi links. Scrollable About content and accurate source/executable build label.
- Guarded single advertised screen-arrow backend for supervised preview capture; no menu/repeat/automatic retry and no generic keyboard controls exposed. Identify/Up/Down observed on the 2255 with measurement state remaining Paused.
- Ten PNG previews, user/release-choice/content/contribution guides and maintained Wiki sources. Recoverable archive for historical material; old build/cache files removed and archive/release outputs excluded from Git/migration.
- 136 offline tests passed; final package validation and publication state are recorded in release notes/progress.


## Folder rename verification — 2026-09-20

Verified the BnKG folder and rebuilt runtime environment, source/CMD launchers and disconnected GUI startup/shutdown. Refreshed progress, start/roadmap guidance and office acceptance steps for the current isolated Demo Lab, instrument logging, guarded metadata and saved-file inventory. No application behavior or dependency changes.

## Setup helper follow-up — 2026-09-20

Added checked Windows rename/setup launchers, unique environment backups, failure/recovery logs, pinned installation and isolated GUI startup verification. Parent-folder copies can rename HBKG to BnKG and resume setup after a failure. Plain-text instructions included; Codex reopening remains manual.

## 0.3.0a3 — 2026-09-20

- Rename visible text to B&KG and technical/package names to BnKG/bnkg; retain graphic artwork and stored raw-context compatibility. New BnKG_Run_Python.py / Launch-BnKG.cmd.
- Explicit read-only internal saved-record inventory, latest-count/date filter, paged directory traversal, cancellation and connection-lifecycle handling.
- About before appearance controls; full Home title, B&KG = BnKG, requested creator/AI/tool credits, new-version/discussion guidance and preserved clickable/copyable links.
- Folder-move and source transfer instructions; Python-only scope. Native file download/decoding still deferred.

## 0.3.0a2 — 2026-09-20 — Metadata verification and status

- Finish the interrupted octave-bandwidth selector label fix, including independent demo labelling.
- Add read-only battery/disk and microphone setup metadata, units and enum descriptions; unavailable status does not interrupt measurement reads.
- Treat absent access metadata as unknown, never writable.
- Verify/correct GPS, custom metadata, annotation, storage and local-export claims in docs/METADATA_GPS_FACT_CHECK.md.
- Add the user-provided manual coordinate default, valid SLM coordinate copy and guarded single text-slot transfer with server-held expiring preview, arming, two confirmations, state/access/change checks, no retry, read-back and durable local audit. Mock-tested; no real device writes performed. Automatic PC/phone acquisition/native GPS injection remain pending.

## 0.3.0a1 — 2026-09-19 — Instrument data and display update

- Descriptor-scaled real levels, configured percentiles, current/total CPB spectrum bars/table and selectable instrument metadata; reject sentinels and axis mismatches.
- Separate Demo Lab and simple CSV; optional instrument logging controls moved to Data table.
- Preserve/dim stale/disconnected/frozen SLM image, Connect shortcut, native PNG save and guarded Identify action (mock-tested only). Actual display-off freeze verified read-only.
- About GitHub/Ko-fi links and copy feedback, original SVG artwork, construction banner and light/theme/icon fixes.
- Metadata/GPS editing possibilities and limitations documented, with local Wiki source. MP4 deferred to next round as allowed; audio later; no binaries built.

## 0.2.0a1 — 2026-09-18 — Python app update

- Source-first Python launcher and explicit Python 3.12 minimum/setup guide; EXE/portable packaging deferred.
- Fix repeated demo logging: monitoring, local capture and file logging are distinct; pause/off creates no duplicate samples. Timestamped logs retain all captured file rows while UI keeps the newest 1–999 (default 100).
- Three synthetic scenarios: Smooth, Ambient, Events.
- Editable/recent IP or hostname, optional unsaved password, mDNS and cancellable bounded subnet discovery, in-app connection help.
- Read-only 2255 identity/LAF/PNG screen validation; SLM Screen moved second with responsive dedicated controls.
- Guarded StartPause/Stop implementation with arming, capability/state checks, Stop confirmations and no ambiguous retries. Real device actions were not exercised.
- System/Dark/Light toggle and BnKG/Colorful/Blue/Red/Green color themes; refined instrument-oriented typography and layout.


## 0.1.0a1 — 2026-09-17 — Local development alpha

- Approved local-development and durable-progress workflow.
- Qt desktop shell with demo data, parameter visibility, LAF trend, recent samples, themes and screenshots.
- SQLite logging and CSV/XLSX/TSV/TXT/JSON/NDJSON exports.
- Read-only Web-XI adapter and capture CLI; no hardware validation yet.
- Backend blocks all real instrument writes.
- Tests, locked environment and Windows one-folder build tooling.
- Project handoffs include progress, Git history when present and integrity verification.

Pending: real capabilities, integrated screen, full parameter semantics, device files, safe settings, installer, clean-PC acceptance and 2245 validation. See current docs/RELEASE_NOTES.md for validation limits.

## 2026-09-18 — Packaging validation

- Fixed frozen QtCore startup failure caused by an unrelated Poppler ICU DLL on the build PATH.
- Isolated the build dependency search and added diagnostic/clean build options.
- Verified the windowed portable ZIP after extraction into a path containing spaces with a Windows-only PATH.
- Added repeatable portable verification and refreshed migration instructions.
