# Corresponding source and build provenance

Qt 6.11.2 / PySide 6.11.2 source archives, zeroconf 0.151.3 and FFmpeg n7.1.5 are supplied in the release source ZIP, with hashes and original URLs. The exact FFmpeg GitHub archive matches SHA-1 2322a4cef2d607c7f0048953662ec5e27c587ae8 in Qt 6.11.2 provisioning. The scripts here are unmodified excerpts from the complete Qt build-instructions archive, retained with their original headers/licences. Use that complete archive for helper scripts and platform setup, not these excerpts in isolation.

Windows playback reports FFmpeg 7.1.5, LGPL-2.1-or-later; its full configuration and avcodec hash are recorded separately. No local patch was applied. Qt's shared FFmpeg configuration and Windows zlib 1.3.1 dependency are included. Qt/PySide sources include their build files, third-party notices and library source. See docs/DEPENDENCY_SOURCES.md for replacement and rebuild instructions.
