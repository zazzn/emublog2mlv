"""
Decode ECU Master EMU Black ``.emublog`` binary logs.

Format (reverse-engineered for EMU Black **V2**, firmware 2.169):

* gzip-compressed; decompress -> 12-byte header, then fixed 308-byte records,
  one record per sample.  ``records = (size - 12) / 308``.
* Little-endian.  Most channels are ``u16`` with a power-of-two (or pressure)
  scale; a few are ``u8``; some booleans are bits inside a ``u16`` flag word.
* ``frameStamp`` (``u32`` @ offset 304) is a 1 Hz seconds counter used to build
  a drift-free time base (the true sample rate is ~25.18 Hz and jitters).

NOTE: EMU Black **V3** writes a different ``.emublog3`` layout — not handled here.

The channel map was verified by Pearson-correlating every byte offset against
row-aligned CSV exports of the same drive, then disambiguating overlapping
clusters by decoding raw bytes against the CSV truth.  Channels that stay flat
in a gentle cruise log (knock level, boost duty/target/correction, EGT, gear,
vehicle speed, AFR2, BARO, engine power/torque, dwell, warmup) are not mapped
yet — add them to ``CHANNELS`` once a dynamic "Rosetta" drive is available to
correlate them.
"""
from __future__ import annotations

import gzip
import os
import struct

HEADER_LEN = 12
RECORD_LEN = 308
NOMINAL_HZ = 25.0
FRAMESTAMP_OFFSET = 304

# (name, unit, offset, kind, scale, extra)
#   kind "u16"  -> (b[o] + 256*b[o+1]) * scale
#   kind "u8"   ->  b[o]               * scale
#   kind "flag" -> bit `extra` of the u16 at offset o  -> 0/1
# NOTE: keep every channel's `scale` coarse enough that meaningful readings stay
# >= ~0.001 — the .msl/.csv writer (_fmt) emits 3 decimals.
CHANNELS = [
    # name,               unit,     off, kind,   scale,     extra
    ("RPM",               "rpm",      2, "u16",  1.0,       None),
    ("MAP",               "kPa",      4, "u16",  1.0,       None),
    ("TPS",               "%",        5, "u16",  1.0 / 256, None),
    ("VE",                "%",       11, "u16",  1.0 / 10,  None),
    ("IgnitionAngle",     "deg",     13, "u8",   0.5,       None),
    ("IgnFromTable",      "deg",     61, "u16",  1.0 / 512, None),
    ("InjectorsPW",       "ms",      31, "u16",  1.0 / 64,  None),
    ("InjectorsDC",       "%",       97, "u16",  1.0 / 512, None),
    ("InjCalTime",        "ms",      15, "u8",   1.0 / 32,  None),
    ("ShortTermTrim",     "%",       39, "u16",  1.0 / 512, None),
    ("Lambda",            "lambda",  43, "u16",  1.0 / 128, None),
    ("LambdaTarget",      "lambda", 189, "u16",  1.0 / 100, None),
    ("IAT",               "C",      187, "u16",  1.0 / 256, None),
    ("ChargeTemp",        "C",      187, "u16",  1.0 / 256, None),  # ==IAT off-boost; needs boost log to separate
    ("CLT",               "C",      115, "u8",   1.0,       None),
    ("OilTemp",           "C",      113, "u8",   1.0,       None),
    ("OilPressure",       "psi",    111, "u16",  0.003541,  None),
    ("FuelPressure",      "psi",    114, "u8",   0.90643,   None),  # byte 113 is OilTemp; high byte 114 carries it
    ("IATCorrection",     "%",       99, "u16",  1.0 / 256, None),
    ("Ethanol",           "%",      125, "u16",  1.0 / 512, None),
    ("AirFlow",           "",       256, "u16",  1.0 / 256, None),
    ("CAM1valveDC",       "%",      104, "u16",  1.0 / 256, None),  # ~0 in cruise (tentative)
    # added 2026-06-15: event-correlated vs the 0614 CSVs (r=1.0, decode-verified to CSV)
    ("AccelEnrichment",   "%",       37, "u8",   1.0,       None),  # tip-in enrichment, raw = %
    ("AccelEnrichmentPW", "ms",      38, "u16",  1.0 / 62,  None),  # ~0.01613; byte 39 shared w/ STT structural-zero low byte
    ("KnockSensor",       "V",       19, "u16",  7.66354e-5, None), # knock sensor signal (scale/unit tentative)
    ("BatteryVoltage",    "V",        8, "u16",  1.0 / 37,  None),  # ~0.027/count (small intercept dropped)
    # added 2026-06-15 from the 0128 boost drive (r=1.0, decode-verified to CSV)
    ("BoostTarget",       "kPa",     84, "u16",  1.0,       None),  # MAP-target (kPa abs)
    ("BoostDC",           "%",       81, "u16",  1.0 / 256, None),  # wastegate solenoid duty
    ("BoostDCFromTable",  "%",       83, "u8",   1.0,       None),  # open-loop base duty from table
    ("IdleTarget",        "rpm",     23, "u16",  1.0,       None),  # phantom: stock ECU runs idle on this car
    ("FCustomCorrActive", "bool",   214, "flag", None,      11),    # bit 11 (0x800)
]

# Derived columns appended after decode: (name, unit, fn(record) -> value).
# AFR is the gasoline-equivalent (lambda x 14.7) display; the car runs E85 but
# the ECU works in lambda, so AFR is just a familiar-scale view.
DERIVED = [
    ("AFR",       "afr", lambda r: r["Lambda"] * 14.7),
    ("AFRTarget", "afr", lambda r: r["LambdaTarget"] * 14.7),
]

VALID_FORMATS = ("msl", "csv")


def channel_names():
    """Ordered output column names (excluding the leading Time column)."""
    return [c[0] for c in CHANNELS] + [d[0] for d in DERIVED]


def channel_units():
    """Units matching :func:`channel_names`."""
    return [c[1] for c in CHANNELS] + [d[1] for d in DERIVED]


def read_records(path):
    """Return ``(body_bytes, n_records, trailing_bytes)`` for an ``.emublog``
    (gzip or raw)."""
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        with gzip.open(path, "rb") as gz:
            raw = gz.read()
    else:
        with open(path, "rb") as f:
            raw = f.read()
    if len(raw) < HEADER_LEN + RECORD_LEN:
        raise ValueError(
            f"{os.path.basename(path)}: only {len(raw)} bytes after decompress — "
            f"not a valid EMU Black V2 .emublog (need >= {HEADER_LEN + RECORD_LEN})."
        )
    body = raw[HEADER_LEN:]
    n, rem = divmod(len(body), RECORD_LEN)
    return body, n, rem


def build_timebase(body, n):
    """Per-record time in seconds, anchored to the device frameStamp clock.

    The true rate is ~25.18 Hz and jitters, so a flat ``index/25`` drifts ~0.7%.
    Here each record gets its absolute second plus an even fraction within that
    1-second bucket — drift-free and monotonic.  Falls back to ``index/25`` if
    the frameStamp field looks invalid.
    """
    if n == 0:
        return []
    fs = [struct.unpack_from("<I", body, i * RECORD_LEN + FRAMESTAMP_OFFSET)[0]
          for i in range(n)]
    if fs[-1] <= fs[0] or any(fs[i + 1] < fs[i] for i in range(n - 1)):
        return [i / NOMINAL_HZ for i in range(n)]
    t0 = fs[0]
    times = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and fs[j] == fs[i]:
            j += 1
        k = j - i
        for r in range(k):
            times[i + r] = (fs[i] - t0) + r / k
        i = j
    return times


def decode_record(body, i):
    """Decode record ``i`` into a ``{channel: value}`` dict (no Time key)."""
    base = i * RECORD_LEN
    b = body[base:base + RECORD_LEN]
    rec = {}
    for name, _unit, off, kind, scale, extra in CHANNELS:
        if kind == "u16":
            rec[name] = (b[off] + 256 * b[off + 1]) * scale
        elif kind == "u8":
            rec[name] = b[off] * scale
        elif kind == "flag":
            word = b[off] + 256 * b[off + 1]
            rec[name] = 1 if (word >> extra) & 1 else 0
    for name, _unit, fn in DERIVED:
        rec[name] = fn(rec)
    return rec


def iter_rows(path):
    """Yield ``(time_s, record_dict)`` for every sample in ``path``."""
    body, n, _rem = read_records(path)
    times = build_timebase(body, n)
    for i in range(n):
        yield times[i], decode_record(body, i)


def _fmt(v):
    # 3-decimal output is clean and lossless for every mapped channel (the
    # finest scale is 1/512 ~= 0.002). The guard keeps a future fine-scale
    # channel from rounding a small nonzero value away to "0".
    if isinstance(v, int) or v == int(v):
        return str(int(v))
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    if s in ("0", "-0"):
        s = f"{v:.6g}"
    return s


def default_output(in_path, fmt):
    return os.path.splitext(in_path)[0] + ("." + fmt)


def planned_output(in_path, fmt, out_dir=None, out_name=None):
    """Resolve the output path for a GUI / batch conversion.

    ``out_dir``: target directory (default: the source file's directory).
    ``out_name``: custom file name for single-file export (default: source stem).
    The extension is always forced to match ``fmt`` so name and content agree.
    """
    base = (out_name or "").strip() or os.path.basename(in_path)
    stem = os.path.splitext(base)[0]
    directory = (out_dir or "").strip() or os.path.dirname(os.path.abspath(in_path))
    return os.path.join(directory, stem + "." + fmt)


def convert(in_path, out_path=None, fmt="msl"):
    """Convert one ``.emublog`` to a MegaLogViewer-HD log.

    ``fmt`` is ``"msl"`` (tab-delimited MegaSquirt log, the default) or ``"csv"``.
    Returns a stats dict: ``{input, output, format, records, duration_s,
    channels, sample_rate_hz, trailing_bytes}``.  ``duration_s`` and
    ``sample_rate_hz`` are frameStamp-derived; if the device clock is unusable
    they degrade to the nominal 25 Hz estimate (so 25.0 is not a measurement).
    """
    fmt = fmt.lower()
    if fmt not in VALID_FORMATS:
        raise ValueError(f"format must be one of {VALID_FORMATS}, got {fmt!r}")
    if out_path is None:
        out_path = default_output(in_path, fmt)
    body, n, rem = read_records(in_path)
    times = build_timebase(body, n)
    sep = "," if fmt == "csv" else "\t"
    names = ["Time"] + channel_names()
    units = ["s"] + channel_units()
    with open(out_path, "w", newline="") as out:
        if fmt == "msl":
            out.write('"MLVHD log from EMU Black .emublog"\t"emublog2mlv"\n')
        out.write(sep.join(names) + "\n")
        out.write(sep.join(units) + "\n")
        for i in range(n):
            rec = decode_record(body, i)
            row = [f"{times[i]:.3f}"] + [_fmt(rec[name]) for name in channel_names()]
            out.write(sep.join(row) + "\n")
    duration = times[-1] if n else 0.0
    return {
        "input": in_path,
        "output": out_path,
        "format": fmt,
        "records": n,
        "duration_s": round(duration, 3),
        "channels": len(names),
        "sample_rate_hz": round(n / duration, 3) if duration else NOMINAL_HZ,
        "trailing_bytes": rem,
    }


def summarize(path):
    """Decode ``path`` and return metadata + per-channel min/max/mean/first/last.

    Writes nothing — handy for an AI or a quick sanity check before converting.
    """
    body, n, rem = read_records(path)
    times = build_timebase(body, n)
    names = channel_names()
    stats = {name: {"min": None, "max": None, "sum": 0.0, "first": None, "last": None}
             for name in names}
    for i in range(n):
        rec = decode_record(body, i)
        for name in names:
            v = rec[name]
            s = stats[name]
            if s["first"] is None:
                s["first"] = v
            s["last"] = v
            s["min"] = v if s["min"] is None else min(s["min"], v)
            s["max"] = v if s["max"] is None else max(s["max"], v)
            s["sum"] += v
    duration = times[-1] if n else 0.0
    channels = []
    for name, unit in zip(names, channel_units()):
        s = stats[name]
        channels.append({
            "name": name, "unit": unit,
            "min": round(s["min"], 4) if s["min"] is not None else None,
            "max": round(s["max"], 4) if s["max"] is not None else None,
            "mean": round(s["sum"] / n, 4) if n else None,
            "first": round(s["first"], 4) if s["first"] is not None else None,
            "last": round(s["last"], 4) if s["last"] is not None else None,
        })
    return {
        "input": path,
        "records": n,
        "duration_s": round(duration, 3),
        "sample_rate_hz": round(n / duration, 3) if duration else NOMINAL_HZ,
        "trailing_bytes": rem,
        "channels": channels,
    }
