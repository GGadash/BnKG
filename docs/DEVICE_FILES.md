# B&KG — saved instrument files and local history

## Local BnKG sessions

Open **Sessions & export → Browse history → Browse local session…** and select a BnKG `.sqlite` log. Reads are local and read-only; no SLM connection is required. Pages contain at most 100 rows. The upper sample boundary stays fixed while paging; Refresh includes newer rows if logging continues. PC receipt times and connection elapsed seconds are not instrument integration periods.

Select a row and **Inspect selected sample** to see its recorded scalar values, origin/quality and spectrum availability. Calculated recorded fields are labelled and are not recomputed. **Load saved spectrum in Frequency** becomes available only for instrument rows with supported raw CPB outputs and retained descriptors. The Saved session source keeps that row's axis, weighting, measurement scope, scalar context and metadata; incoming live data cannot alter it. Return to Live source explicitly. The original database remains unchanged.

Older scalar-only logs remain browsable, but missing spectra/descriptors are not guessed. Simulation/unknown origins stay in the historical browser. Corrupt, oversized, unsupported-schema or changed-identity files produce an explanation. Native `.bkc` files cannot be opened as SQLite logs. Browse and export selection are independent; use the Export tab's existing session selector for export. Exporting the current session runs independently while monitoring and logging continue. Selecting a different export session still requires stopping file logging. Export uses a consistent local snapshot; later recorded samples remain in the original log. The history Chart this page tab plots only the current page of up to 100 rows.

## Instrument inventory and original downloads

Connect explicitly, then choose **Device files**. Nothing loads automatically. **Load latest records** lists 1–999 recent measurement records (default 100), optionally between inclusive dates. Dates/order use advertised SLM folder names and its clock. A measurement directory may contain several files.

**Browse all folders**, **Browse selected directory**, and **Parent folder** navigate only advertised directories. Each result is paged 100 entries at a time. The location label shows the current folder; file tooltips show advertised metadata. Unrecognised date layouts remain manually browsable.

Select an advertised File row and choose **Download selected file…**, then a new local filename. The app streams original bytes into an owned temporary file, checks transfer length where supplied, and publishes only a complete file without overwriting existing content. The selectable completion text shows its path, byte count and SHA-256. Keep originals unchanged for later analysis. **Limited native total decoding is available in Sessions & export → Native BKC; see [supported profiles and limits](BKC_DECODING.md).** This download never invokes instrument Open, GetArchive, Delete, MarkArchived, measurement control or settings changes.

Limits: one file at a time, 256 MiB and 120 seconds, bounded socket reads, cancellation between chunks, no redirects or content encoding. Failed/cancelled transfers remove their owned `.partial` files. Atomic publication uses a local hard link; use a compatible destination such as NTFS. Unsupported filesystems fail without replacing existing files. Live monitoring runs independently. Disconnect cancels active reads and rejects stale inventory results. Inventory is a snapshot, not an atomic continuously updated list.

Directory JSON is limited to 2 MB; searches stop after 200 dated folders or approximately 60 seconds. Narrow the dates/folder if a limit is reached. Original partial files left by an abrupt process/power loss may need manual recovery/cleanup after checking their paths.

## Protocol and acceptance evidence

The [official SLM WebXi protocol specification, section 7.1](https://github.com/hbkworld/Open-Interface-for-Sound-Level-Meter/blob/master/Documentation/SLM%20WebXi%20protocol%20specification.pdf) defines direct GET retrieval of advertised File nodes. Existing 2255 evidence uses `/webxi/Applications/SLM/Data`, dated folders, measurement folders and `.total.bkc` children. No alternate FileSystem path is assumed.

This firmware needs literal `$` delimiters; `%24` previously returned HTTP 500. BnKG preserves `$` and rejects traversal/query/fragment/control characters in directory names. On 2026-09-28, one advertised native file was downloaded read-only and preserved privately with a SHA-256 receipt. Offline tests cover original-byte identity, overwrite races, cancellation, truncation, size limits, redirects, encoded/partial responses and historical source isolation. Linux/2245/other firmware remain unverified. Native total interpretation now has the narrow independent comparison described in [BKC decoding](BKC_DECODING.md).
