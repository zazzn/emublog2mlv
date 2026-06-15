# Changelog

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
