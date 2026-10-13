# Optional FFmpeg setup

B&KG screen recording always saves original PNGs and receipt timing. MP4 additionally needs **ffmpeg + ffprobe from the same trusted build**, with the `libx264` encoder. Tool discovery does not execute/download anything; encoding runs only after an explicit recording finishes. Audio capture/decoding is not implemented, regardless of the external tool's codecs.

## Windows (Python, Executable Portable or Standalone)

1. Open [Gyan Windows builds](https://www.gyan.dev/ffmpeg/builds/), linked by the [official FFmpeg download page](https://ffmpeg.org/download.html). Choose **Release Essentials ZIP**, not source code. It includes x264, Opus and native AAC/FLAC; Full is not required for B&KG. These builds are for 64-bit Windows 10 or later.
2. Download its `.sha256` file too. In PowerShell run `Get-FileHash -Algorithm SHA256 'C:\path\to\ffmpeg-release-essentials.zip'` and compare the complete hash with the publisher's checksum. Extract only a matching archive. A checksum from the same publisher checks integrity, not independent authenticity.
3. Copy the extracted build's **contents** into `external-tools/ffmpeg/` beside `BnKG.exe`, the Standalone EXE, or `BnKG_Run_Python.py`. Keep its LICENSE, README and documentation. Avoid a second nested build-name directory. The paths should be:

   ```text
   BnKG/
     external-tools/ffmpeg/
       bin/ffmpeg.exe
       bin/ffprobe.exe
       LICENSE
       README.txt
   ```

4. Restart B&KG for discovery, or open **SLM Display → Local screen recording**, enable **Also create processed MP4 after Stop**, and use **Browse FFmpeg…** to select `bin/ffmpeg.exe`. Its sibling `ffprobe.exe` is filled automatically when present; you can also browse for it. Missing-tool instructions and clickable/copyable download links appear with the MP4 options. No administrator access or PATH change is needed. A trusted installation elsewhere works equally well through Browse.
5. Start a short recording with the connected SLM, then Stop. Originals remain in the new recording folder; successful MP4 is `video.mp4`, with codec/dimensions/duration/frame-count validation in `recording.json`. Failed/cancelled encoding preserves originals and any partial output. Review the timing ledger for gaps; MP4 is processed/lossy, not a lossless native-video stream.

Discovery prefers valid saved paths, then a probe beside the saved encoder, then the application-adjacent folder above, then a paired installation on PATH. Missing old paths from another PC can be corrected with Browse. Discovery only checks file presence; recording verifies the required encoder and output.

## Linux

Install your distribution's maintained FFmpeg package using its package manager, including `ffprobe`. Verify `ffmpeg -hide_banner -encoders` lists `libx264`, then use PATH discovery or Browse for `/usr/bin/ffmpeg` and `/usr/bin/ffprobe`. Distribution codec availability varies. Windows EXEs do not run natively on Linux. See [official platform downloads](https://ffmpeg.org/download.html).

## Codecs and licensing

| Requested capability | Selected local build | B&KG use |
| --- | --- | --- |
| H.264 / x264 | `libx264` | Screen MP4 |
| FLAC | `flac` | Lossless app capture; external decoding/conversion checks |
| AAC | Native `aac` | App AAC/M4A and paired MP4 export; **not FDK-AAC** |
| Opus | `libopus` | Lossy app Opus export |
| Fraunhofer FDK-AAC | **Absent** | No silent substitution or support claim |

The selected Gyan build is GPLv3 (its exact LICENSE and build configuration control). FFmpeg's [licence documentation](https://ffmpeg.org/doxygen/trunk/md_LICENSE.html) explains that x264 enables GPL terms, while combining GPL components with FDK-AAC requires `--enable-nonfree` and makes the resulting binary non-redistributable. Do not obtain an arbitrary all-codecs build for redistribution. The user explicitly selected **native AAC (`aac`) instead of FDK-AAC on 2026-10-01**; no FDK build is needed. The media panel offers native AAC and Opus export controls.

`external-tools/` is excluded from Git, generated end-user packages and the project transfer exporter. Guidance ships with the source/packages and is embedded in the app's recording controls, including the Standalone edition. On a new PC obtain tools again or select an existing trusted installation. Do not force-add binaries to Git. Any future public redistribution needs exact-build notices, corresponding-source/build obligations and dependency review; merely adding a licence link does not meet those obligations. The application's original MIT code licence is unchanged.

## Local acceptance installation — 2026-10-01

- Gyan FFmpeg **9.0.2 Essentials**, publisher mirror: [release 9.0.2](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2).
- Archive `ffmpeg-9.0.2-essentials_build.zip`, SHA-256 `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`, matched the publisher's checksum before execution.
- Installed under `external-tools/ffmpeg/`; original LICENSE/README/docs preserved, plus `DOWNLOAD_PROVENANCE.json`. Versions, configuration, codecs and local acceptance evidence are recorded separately. This is a local optional tool, not a bundled release dependency.

## Audio capture update — 2026-10-02

[Instrument FLAC capture](AUDIO_CAPTURE.md) now works independently of FFmpeg. Playback, native AAC/Opus exports and receipt-aligned paired MP4 are implemented; see the audio guide for timing limits and controls. Qt Multimedia playback includes its own shared FFmpeg libraries, distinct from the optional external encoder executables; see [dependency sources](DEPENDENCY_SOURCES.md).
