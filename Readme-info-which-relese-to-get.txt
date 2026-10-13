B&KG / BnKG — Which release should I get?
Development alpha 0.4.0a1 | https://github.com/GGadash/BnKG/releases

MOST WINDOWS USERS: win64-Executable-Portable.zip
No installed Python needed. Extract the whole ZIP, then run Launch-BnKG-Portable.cmd.
Keeps local data in the package data folder. Easy to inspect/replace libraries.
Keep all extracted files together; larger than a single executable.

WINDOWS SINGLE FILE: win64-Standalone.exe
No installed Python needed. Copy and run the EXE. Convenient for occasional use;
extracts its runtime to a temporary folder, so startup can be slower. User data
normally goes to your per-user application-data folder. It is not an installer.
Pass --data-dir to select a different writable folder. Unsigned development build.

LINUX: linux-x86_64-Executable-Portable.tar.gz
Targets Ubuntu 22.04/24.04 x86-64. No installed Python needed. Extract with tar,
then run ./BnKG/Launch-BnKG-Portable.sh. Requires a desktop session and the system
libraries listed in docs/LINUX.md. Other distributions/ARM are not validated.
Linux GUI smoke checks do not prove real-meter or audio-device compatibility.

PYTHON USERS / DEVELOPERS: Python-Portable.zip
Application source, guides and pinned dependencies; no Python runtime included.
Requires Python 3.12–3.14 (3.12 used for builds) and Internet for initial setup.
Windows: run Setup-BnKG-After-Move.cmd, then Launch-BnKG-Portable.cmd.
Linux: follow docs/LINUX.md, then Launch-BnKG-Portable.sh.
Easiest to modify/debug; initial dependency installation takes extra work.

DEVELOPERS / LICENSING: Corresponding-Library-Sources.zip
Unmodified source archives and provenance for bundled copyleft libraries.
Not an app; ordinary users do not need it to run BnKG. Third-Party-Notices.zip
contains component notices. SHA256SUMS.txt verifies downloaded asset integrity.

All editions use the same application source. Extra media exports require a
separately installed FFmpeg with x264, native AAC, FLAC and Opus; see
https://github.com/GGadash/BnKG/blob/main/docs/FFMPEG_SETUP.md
Qt playback uses separate LGPL FFmpeg libraries; their source is on the release page.

UNDER DEVELOPMENT: some information may be incomplete, delayed or incorrect.
Double-check values, units, times and settings on the SLM. No manufacturer
endorsement, warranty or measurement/regulatory compliance claim is made.
Read README-INFO.md, QUICK_START.md, LEGAL.md, CREDITS.md and THIRD_PARTY_NOTICES.md.

Developer/related and possibly more developed editions: https://github.com/GGadash/
HBKG: https://github.com/GGadash/HBKG
Source and contributions: https://github.com/GGadash/BnKG
Wiki: https://github.com/GGadash/BnKG/wiki
Discussions: https://github.com/GGadash/BnKG/discussions
Developer support: https://ko-fi.com/gadash
B&KG / HBKG product: https://ko-fi.com/s/06caf1c2f0
