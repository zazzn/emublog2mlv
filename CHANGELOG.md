# Changelog

## 1.2.0 — 2026-06-15

- Expand the decoded channel map to **31 measured + 2 derived** (was 24 + 2). New
  channels, all r ≈ 1.0 and decode-verified against EMU CSV exports:
  `AccelEnrichment`, `AccelEnrichmentPW`, `KnockSensor`, `BatteryVoltage` (from
  cruise logs), and `BoostTarget`, `BoostDC`, `BoostDCFromTable` (from a boost drive).

## 1.1.0 — 2026-06-15

- Add a simple desktop **GUI** (`emublog2mlv-gui`, Tkinter / standard library):
  pick files or a whole folder, choose `.msl`/`.csv`, set the output folder or a
  custom name (single file), and batch-convert with a progress bar.
- Ship a second standalone `emublog2mlv-gui.exe` (windowed) alongside the CLI exe.
- New `core.planned_output()` helper resolving output paths for batch/GUI use.

## 1.0.0 — 2026-06-14

First release.

- Decode ECU Master EMU Black **V2** `.emublog` binary logs (12-byte header +
  308-byte records, gzip-compressed) to MegaLogViewer HD `.msl` (tab-delimited)
  or `.csv`.
- 24 verified channels + 2 derived (AFR, AFR target), validated to the decimal
  against row-aligned EMU CSV exports.
- frameStamp-anchored, drift-free time base (handles the real ~25.18 Hz rate).
- Three interfaces: CLI (`emublog2mlv`), Python library, and an MCP server
  (`emublog2mlv-mcp`) exposing `convert_emublog`, `emublog_summary`,
  `list_channels`.
- Standalone Windows `.exe` (no Python required), built via PyInstaller and
  attached to GitHub Releases by CI.
