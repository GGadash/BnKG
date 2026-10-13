# B&KG — Display and recording guide

Stage 5 source implementation, 2026-09-28. Refreshed release packages include this work. The original milestone used offline fixtures. Live 2255 and local FFmpeg acceptance resumed on 2026-10-01; see `RELEASE_NOTES.md` for exact results and remaining gaps.

## Display tools

SLM screen offers Fit (both available dimensions), 100%, 200% (default) and 400%. Pixel — Nearest Neighbor is the default; Sharp — Lanczos and Smooth — Bicubic use the named Pillow filters. Preferences are saved under new versioned keys so legacy Fit/Smooth defaults do not override the requested defaults. The controls column has its own scrolling area, and status sits above the image rather than covering it. Fixed zoom can scroll; Fit preserves the entire aspect ratio within the visible display. Fullscreen inherits current zoom/filter, and retains original image freshness.

**Save original SLM PNG** preserves the last received bytes and incoming resolution. **Save processed display PNG** re-encodes the image at the selected display scale/render mode; it does not include the status overlay. Check freshness before saving either. Neither action overwrites existing files. Output location is shown after saving.

Arm controls once for the connection. Successful Start/Pause/Stop, Identify and screen navigation retain arming; disconnect/read failures and uncertain writes disarm. No automatic retry occurs. Start/Pause/Stop have no repeated dialog; settings/metadata keep their existing double confirmation.

Acknowledge **Measurement view — enable screen keys** on a fresh display once before using Up/Down/Left/Right without repeated dialogs. Untick before entering menus physically. The centre **Menu / OK** sends advertised KeyMenu only from that acknowledged measurement view, then locks the keypad. Return using the physical SLM and acknowledge the measurement screen again. B&KG does not classify PNG menu contents automatically; the acknowledgement is the user's responsibility. No remote menu editing, repeated/held keys, Back/Power, calibration/reset/service or generic writes are enabled.

## Record original frames

1. Connect the instrument explicitly when it is available. Recording never connects, wakes the display or changes measurement state automatically.
2. In SLM screen, choose **Start screen recording…** and a parent directory. A new uniquely named `BnKG-SLM-<UTC>-<suffix>` folder is created. There is no reuse or overwrite of another recording.
3. New PNGs are recorded independently of local scalar capture/logging. Polling continues on other pages while recording is active; a workspace banner shows recording/encoding status. The existing one-second polling loop is retained: actual receipt intervals can vary. No 4-Hz/native-stream claim is made.
4. **Stop and finish** drains accepted frames, saves the manifest and optionally encodes. **Cancel; keep originals** cancels pending work and preserves files already written. Disconnect/source change ends capture; closing cancels encoding and waits for worker/process shutdown. Page-based polling resumes after recording ends.

Files:

- `frame-000000.png`, etc.: original PNG bytes, never replaced by workspace screenshots or Demo.
- `frames.jsonl`: append-only receipt ledger with PC UTC/monotonic times, relative time, SHA-256, byte size, unchanged duration and gaps over three seconds. These are PC receipt times, not instrument integration periods. An unchanged display may be static or asleep; identical arrivals do not prove a fresh measurement.
- `recording.json`: capture/encoding status, limits, reason, dropped-frame count, dimensions and encoding/probe details when available. After an abrupt interruption the ledger and PNGs are recovery evidence even if the manifest still says capturing.

Limits: eight queued frames, 8 MiB per PNG, 2048 pixels per axis, 512 MiB original PNGs, 3,600 frames and one hour. Capture stops on a full queue, changed resolution, invalid frame, low disk space (64 MiB reserve), non-increasing receipt clock or 30 seconds without frames. Limits stop the recorder rather than block acquisition. Partial writes and already saved originals are retained for inspection; do not treat an incomplete file as a validated frame. Recording folders may contain private instrument information and are not public release assets.

## Optional processed MP4

Select **Also create processed MP4 after Stop**, then select external **FFmpeg** and **ffprobe** executables. The app does not download or bundle tools. A separate local installation is supported; see [FFmpeg setup](FFMPEG_SETUP.md) for downloads, paths, Browse controls and codec/licensing details. The selected build must provide libx264; its version and output validation are recorded. The user is responsible for choosing a trusted build and its applicable licence. Core PNG recording needs no encoder.

The current path offers AVC baseline/main/high, CRF 1–51 (default 18), fixed medium preset and yuv420p. It pads right/bottom to even dimensions without scaling. MP4 is lossy; the PNG archive remains the original. CRF 0/lossless mode, other codecs, scaling, advanced presets and audio are not implemented.

The concat timeline uses measured frame-to-frame receipt intervals, holds the previous image through gaps and adds an explicit one-second final hold. Input timing is quantized to 40 ms by the PNG demuxer time base; exact times remain in the ledger. No motion interpolation is used. A held/unchanged frame in video is not proof of ongoing measurement. Keep `recording.json` and `frames.jsonl` with the video.

Encoding is an argument-list subprocess with no shell or visible console, cancellation, a five-minute encoding deadline, bounded diagnostics and disk/output checks (512 MiB encoded-output cap). FFprobe must confirm H.264, expected padded dimensions, frame count, approximate duration and absence of audio before `video.partial.mp4` is published as `video.mp4` using an exclusive hard link. This requires local filesystem hard-link support (e.g. NTFS). Cancellation/failure retains original frames and any partial video; final publication never overwrites another video. A valid probe does not certify acoustic data or universal player compatibility.

Offline coverage includes original-byte identity, display lifecycle, responsive layout, receipt gaps/unchanged frames, bounded queue, low disk, missing encoder, cancellation, bad-probe rejection and clean shutdown. Real external encoding, long recordings, live disconnect/display-off behavior, native high-DPI and Linux/2245 remain acceptance work.

References consulted: [FFmpeg concat demuxer](https://ffmpeg.org/ffmpeg-formats.html#concat), [FFmpeg libx264 options](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb). HBKG supplied design docs provide functional inspiration; their fixed 4-Hz, overwrite and lossless-video implications were not adopted. Optional instrument audio remains gated on verified transport and stream-setup safety.

2026-10-01 acceptance: short real 2255 PNG/MP4 recording passed. Sparse receipt-timed encoding explicitly disables B-frames (`-bf 0`) to preserve duration; strict ffprobe checks remain. Native AAC is the accepted external AAC encoder choice; audio acquisition is still unimplemented. See [acceptance scope and remaining gaps](RELEASE_NOTES.md).


## Current media extension — 2026-10-10

The screen archive remains independent and its `video.mp4` remains silent. An explicitly paired audio capture adds matching clock/session provenance; a separate background media export combines the finalized screen video with AAC. This preserves originals and existing screen-only workflows. See [audio playback/export and timing limits](AUDIO_CAPTURE.md). Earlier audio-deferred statements above describe prior stages.


Filter reference: [Pillow resampling filters](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters). Scaling is local; original PNG saving and recording still preserve received bytes.
