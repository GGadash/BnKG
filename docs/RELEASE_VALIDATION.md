# Release validation: 0.4.0a1

B&KG is an unsigned development alpha. Passing these checks is not certification of measurement accuracy or compatibility with every computer or meter.

- Windows source regression: 264 passed, one hour-long case excluded. New first-use agreement, release and setup checks: 22 passed.
- First-use agreement: explicit checked acceptance required, decline exits before the main window and worker, persistence is revisioned, failure to save blocks startup. Dialog text was visually inspected.
- Ubuntu 22.04 build: offline tests passed; extracted native Linux package launched disconnected under Xvfb on Ubuntu 22.04 and 24.04 x86-64. See [build and validation runs](https://github.com/GGadash/BnKG/actions/workflows/linux.yml).
- Release packages undergo archive/checksum and disconnected startup checks. These automated smoke checks use an isolated data folder and do not save acceptance of the first-use agreement or contact an SLM.
- Windows checks use the development PC with a restricted system-only PATH; this is not a clean second-PC acceptance test. Linux CI uses virtual displays; physical desktop, audio output and meter connection on Linux remain unverified.
- Source/library notices, corresponding-library-source hashes and public-content exclusions were reviewed before publication. Private measurements, project transfers and original development history are not release assets.

Earlier instrument evidence covers an HBK 2255 with firmware 1.3.0.478. Other firmware and B&K 2245 are not validated. BKC conversion supports only the independently compared 2255 total profile; unsupported data stays raw. Audio/video alignment uses PC receipt time and has uncertainty. Native GPS/marker writeback, audible speaker quality and extended soak acceptance remain open. No new instrument writes were performed for this release.
