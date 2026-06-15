# emublog2mlv

Convert **ECU Master EMU Black** `.emublog` binary logs into a format
[MegaLogViewer HD](https://www.efianalytics.com/MegaLogViewer/) can open —
a MegaSquirt `.msl` (tab-delimited) or plain `.csv`.

[![CI](https://github.com/zazzn/emublog2mlv/actions/workflows/ci.yml/badge.svg)](https://github.com/zazzn/emublog2mlv/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/zazzn/emublog2mlv)](https://github.com/zazzn/emublog2mlv/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

The EMU Client stores logs in an undocumented gzip-compressed binary format that
only its own software can open. This tool decodes that format directly, so you
can analyse EMU logs in MegaLogViewer HD (overlay channels, histograms, VE/AFR
analysis) instead of being locked into the EMU Client viewer.

---

## Three ways to use it

### 1. Standalone apps (no Python needed) — easiest

Download from the [**Releases**](https://github.com/zazzn/emublog2mlv/releases) page:

- **`emublog2mlv-gui.exe`** — double-click for a simple window: add one or many
  logs (or a whole folder), choose `.msl`/`.csv`, set the output folder or a
  custom name for a single file, then **Convert**. Best for batch/mass conversion.
- **`emublog2mlv.exe`** — command-line version. Drag a log onto it, or:

  ```bat
  emublog2mlv.exe yourlog.emublog       REM -> yourlog.msl
  emublog2mlv.exe *.emublog              REM batch convert
  ```

Open the resulting `.msl` in MegaLogViewer HD.

### 2. Python package (CLI + library)

```bash
pip install git+https://github.com/zazzn/emublog2mlv
```

```bash
emublog2mlv yourlog.emublog              # -> yourlog.msl
emublog2mlv yourlog.emublog --csv        # -> yourlog.csv
emublog2mlv *.emublog                     # batch convert
emublog2mlv yourlog.emublog --summary     # print channel ranges as JSON (no file written)
```

As a library:

```python
from emublog2mlv import convert, summarize
convert("yourlog.emublog", fmt="msl")     # returns stats dict
summarize("yourlog.emublog")              # per-channel min/max/mean
```

### 3. MCP server (let an AI use it as a tool)

`emublog2mlv` ships an [MCP](https://modelcontextprotocol.io) server so an AI
assistant (Claude Desktop / Claude Code, etc.) can convert and inspect logs for
you.

```bash
pip install "emublog2mlv[mcp] @ git+https://github.com/zazzn/emublog2mlv"
claude mcp add emublog2mlv -- emublog2mlv-mcp
```

Tools exposed:

| Tool | What it does |
|------|--------------|
| `convert_emublog(input_path, output_format="msl", output_path=None)` | Convert a log; returns stats |
| `emublog_summary(input_path)` | Per-channel min/max/mean/first/last (no file written) |
| `list_channels()` | The decoded channel map (offsets/scales) |

Then just ask: *"Convert C:\logs\drive.emublog and tell me where lambda goes lean."*

---

## Output

A `.msl` file has a name row, a units row, then one row per 25 Hz sample, with a
`Time` column in seconds. **Time is anchored to the device's frameStamp clock**,
so it stays accurate even though the real sample rate (~25.18 Hz) jitters — a
naïve `index / 25` drifts ~0.7% over a few minutes.

### Decoded channels

31 measured channels plus 2 derived (`AFR`, `AFRTarget` = λ × 14.7):

`RPM`, `MAP`, `TPS`, `VE`, `IgnitionAngle`, `IgnFromTable`, `InjectorsPW`,
`InjectorsDC`, `InjCalTime`, `ShortTermTrim`, `Lambda`, `LambdaTarget`, `IAT`,
`ChargeTemp`, `CLT`, `OilTemp`, `OilPressure`, `FuelPressure`, `IATCorrection`,
`Ethanol`, `AirFlow`, `CAM1valveDC`, `AccelEnrichment`, `AccelEnrichmentPW`,
`KnockSensor`, `BatteryVoltage`, `BoostTarget`, `BoostDC`, `BoostDCFromTable`,
`IdleTarget`, `FCustomCorrActive`.

Still unmapped — each needs a drive that *exercises* it: knock level / ignition
retard (a knock event), decel enrichment (overrun), warmup/afterstart (a cold
start), boost PID correction (closed-loop boost), plus dwell, BARO, gear, vehicle
speed, AFR2/Lambda2, and engine power/torque — they read flat in a gentle cruise.
EGT is omitted (this car has no EGT sensor). See
[Contributing](#contributing-add-a-channel).

---

## How the format was reverse-engineered

ECU Master does not publish the `.emublog` layout. It was recovered by
correlation:

1. The file is **gzip-compressed**. Decompressed, it is a **12-byte header**
   followed by fixed **308-byte records**, one per sample
   (`records = (size − 12) / 308`).
2. Export the *same* drive from EMU Client to CSV (it caps at 13 channels per
   export, so several exports are taken). These CSVs are **row-aligned** to the
   binary (sample *N* = record *N*).
3. For each known CSV channel, Pearson-correlate its series against a `u16` (or
   `u8`) value read at **every** byte offset; the offset with |r| ≈ 1.0 is the
   channel, and the linear fit gives the scale.
4. Overlapping clusters (e.g. oil-pressure / oil-temp / fuel-pressure / coolant
   packed into bytes 111–115) were pinned by **dumping raw bytes next to the CSV
   truth** — temperatures turned out to be single-byte integers, pressures a
   dominant high byte.

Every decoded channel matches the EMU CSV export to the decimal. (The only
discrepancies are ~0.8% of rows where EMU's own CSV export jitters ±1–2 frames
against the binary — so this converter is actually *more* faithful than
re-exporting CSV from the EMU Client.)

This was reverse-engineered for **EMU Black V2** (firmware 2.169). **EMU Black
V3** writes a different `.emublog3` layout, which is **not** supported.

---

## Contributing: add a channel

The channel map lives in [`src/emublog2mlv/core.py`](src/emublog2mlv/core.py) as
the `CHANNELS` table: `(name, unit, offset, kind, scale, extra)`. To map a new
channel, get a log that *exercises* it (e.g. a boost pull for boost/knock/EGT),
export it to CSV from EMU Client, correlate each byte offset against the CSV
column, verify the decode against the CSV, then add a row. PRs welcome.

Run the tests:

```bash
pip install -e ".[dev]"
pytest -q
```

---

## License

[MIT](LICENSE) © 2026 Eric W
