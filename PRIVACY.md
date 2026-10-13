# B&KG — Privacy

B&KG is local-first: no telemetry, account, cloud upload, advertising, automatic update check or exposed local server.

Preferences and SQLite sessions are stored locally. Exports/screenshots go to user-selected files. The default is the platform local application-data directory; --data-dir selects another directory. Probe captures can contain IP, serial and configuration; keep them private until sanitized.

The user explicitly chooses instrument contact. Demo mode has no network traffic. Ordinary HTTP Web-XI is not encrypted. The client does not send ambient proxy/.netrc credentials or follow redirects.

Private transfer archives include project files even when ignored by Git, except documented caches/environments/archive directories. They are not public releases and are not encrypted.

Explicit discovery uses local mDNS multicast or a user-selected bounded subnet (HTTP checks and Windows ping). Recent successful device addresses are saved locally. Network passwords stay in memory and are not saved; ordinary HTTP transport is unencrypted. Discovery is never automatically triggered by demo or startup.

Reviewed location-text transfers create a local audit in audit/BnKG-Location-Writes.jsonl under the application data directory, independently of measurement logging. It includes slot/name, old/new text (potentially location/operator details), source, instrument address and PC UTC outcome timestamps, never the password. Manual coordinates are not automatically acquired or uploaded; map/network providers are not enabled. Review audit/session files before sharing a private transfer archive.
