# Contributing

Visit [BnKG](https://github.com/GGadash/BnKG) for source and releases. Use [Discussions](https://github.com/GGadash/BnKG/discussions) for questions and ideas and Issues for reproducible bugs. Fork the repository, make a focused change and submit a pull request. Include validation and explain which model/firmware was tested.

Explore the [developer page](https://github.com/GGadash/) for related projects and contribute improvements there too. [HBKG](https://github.com/GGadash/HBKG) is the developer's related edition with more features; access/availability may vary.

Use the pinned development environment and checks in BUILDING.md. Keep device communication off the UI thread. Preserve raw values, units, provenance and stale-state labels. New device operations need documented/advertised evidence, backend safety classification and offline tests. Hardware writes are opt-in and excluded from automated tests. Never commit credentials, unrestricted private measurements or personal location/operator data.

No telemetry, automatic instrument connection or silent replay of writes. Original contributions use the repository MIT licence; keep third-party notices intact.
