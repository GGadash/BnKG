# Linux: Ubuntu 22.04 / 24.04 x86-64

Development alpha. Linux packages target these two Ubuntu releases; other distributions and ARM are not validated. Offline GUI/build checks do not establish live SLM or audio-device acceptance. More developed/different editions may be available at [GGadash](https://github.com/GGadash/), including [HBKG](https://github.com/GGadash/HBKG).

## Executable Portable

Install the desktop runtime libraries (the package needs an X11/XWayland-capable desktop):

```sh
sudo apt update
sudo apt install libegl1 libgl1 libopengl0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-render-util0 libxcb-image0 libxcb-randr0 libxcb-xfixes0 libpulse0 libglib2.0-0 libdbus-1-3 libfontconfig1 libfreetype6 libx11-xcb1 libxrender1 libxi6 libxfixes3 libxext6 libxrandr2 libxcursor1 zlib1g
```

Extract the release tar.gz into a writable folder and run `./BnKG/Launch-BnKG-Portable.sh`. It stores data beside the app in `data/`. Directly running `./BnKG/BnKG` uses the app's default per-user data location. Do not run as root. If a Wayland-specific launch fails, try `QT_QPA_PLATFORM=xcb ./BnKG/Launch-BnKG-Portable.sh` in a session with XWayland.

The bundle uses Ubuntu system libraries instead of shipping copies from the build runner. See `system-libraries-not-bundled.json` inside the package. ALSA must also be installed (`libasound2` on Ubuntu 22.04 or `libasound2t64` on Ubuntu 24.04); a normal desktop installation includes it.

## Python Portable / source

Use Python 3.12 (3.13/3.14 are declared compatible but not the build baseline). Ubuntu 24.04 provides Python 3.12; Ubuntu 22.04 needs a separately installed supported Python. Create the environment in the extracted folder:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
chmod +x Launch-BnKG-Portable.sh
./Launch-BnKG-Portable.sh
```

The source launcher is `BnKG_Run_Python.py`. For development install `requirements-dev.lock` instead. Optional external FFmpeg is separate: install a suitable distribution package or select its path in the app; verify codecs in [FFmpeg setup](FFMPEG_SETUP.md).

## Build and checks

```sh
.venv/bin/python scripts/build_linux.py
```

The GitHub Actions workflow builds on Ubuntu 22.04 and checks the extracted result on both Ubuntu versions. It never contacts a meter or publishes a release automatically. The release notes record actual results; a configured workflow alone is not a passed test.
