# Instrument audio capture

Connect to the SLM, open **SLM Display → Instrument Audio**, then **Inspect audio**. Choose a maximum duration (1–60 minutes), select **Capture FLAC**, review the confirmations, and choose a private local folder. Stop audio ends local capture; it never stops the SLM measurement.

If Analysis quality is Disabled and the meter is idle (Activated), B&KG offers a temporary change to Continuous with two confirmations. This setting also enables instrument-side audio recording during measurement. B&KG does not start a measurement. It restores Disabled when capture ends, provided the state/value still permit the exact approved restoration. A disconnected meter, external setting change or failed read-back produces a visible warning and a manifest requiring attention. Check the instrument's Audio recording → Analysis quality if restoration fails. No routine retry overwrites external changes.

Files in each new `BnKG-Audio-*` folder:

- `audio.flac`: lossless playable audio when the observed format and timing pass checks. Compressed samples are preserved; container/frame numbering/checksums are repackaged.
- `original.webxi`: unchanged received Web-XI binary messages.
- `messages.jsonl`: original message hashes, offsets, raw instrument timestamps and PC receipt times.
- `audio.json`: source descriptor, calculated sample-rate provenance, status and setting/stream cleanup outcome.

Quality is **unknown**, not certified acoustic validity. Do not treat audio playback amplitude as calibrated sound level. Z/C/A and Leq displays continue using their existing SLM data paths. Sample rate is calculated from verified frame sample counts and the meter's time family/timestamp deltas, not from the PC polling period. Gaps or unsupported formats leave original data available without claiming a complete playable result.

## Playback and export

In **SLM Display → Playback and media export**, open audio or another local media file. Playback never starts automatically; volume starts at 25%. Play/Pause/Stop, seek and volume affect local playback only. AAC (`.m4a`) and Opus (`.opus`) exports use the [selected external FFmpeg/ffprobe pair](FFMPEG_SETUP.md), native `aac` or `libopus`, 128 kbit/s and 48 kHz. These are lossy, explicitly resampled copies; original FLAC/raw data remains unchanged. No FDK-AAC is used. Playback uses Qt Multimedia, independently of the optional external export executables.

Select **Record screen video with this audio** before Capture FLAC to create paired recordings in one parent folder. Both captures retain their own manifests and one common process clock/session ID. Stopping either owned paired recorder stops the other; existing unrelated recordings are not adopted. After both finish, **Export paired MP4…** combines H.264 screen video with AAC audio in a new folder. Separate captures without matching clock/session provenance are refused.

Synchronization is **estimated from PC monotonic receipt times**, not hardware-synchronized. Instrument, transport and display latency are unknown; no drift correction is applied. The A/V correction control allows ±30 seconds: positive values delay audio, negative values trim its beginning. Video retains its full duration, with silence outside the overlapping audio period. No overlap is refused. Verify alignment against a recognizable event when precise synchronization matters.

Each new `BnKG-Media-*` export includes `media.json` with input/output hashes, codec/rate, source capture provenance and timing/correction details. Outputs are bounded to 512 MiB and roughly one hour; processing is cancellable with a five-minute encoding limit. Final publication requires a filesystem supporting hard links (for example NTFS). Failed exports retain diagnostics/partials in their new folder without replacing originals.

A verified startup pattern on the 2255 used one absolute timestamp followed by a relative timeline. The playable copy omits only that first frame when this exact narrow pattern is recognized, and reports the omission and first usable receipt time. Every original message remains preserved. Other continuity failures still refuse playable output.

Audio may contain conversations. Keep captures private and inspect them before sharing. Device passwords are not placed in capture manifests. Maximum original data is 192 MiB, 60000 messages or one hour, whichever is reached first; wrapping has a 60-second cap. Close/disconnect waits for worker cleanup. Avoid switching instrument settings or starting a measurement during a temporary setting session.

Verified on 2255 firmware 1.3.0.478; other instruments/firmware may reject capture and retain originals. See [acceptance and remaining limits](RELEASE_NOTES.md).
