"""Tests for emublog2mlv against the bundled sample log (examples/sample_cruise.emublog).

The sample is the first 750 records (~31 s) of a verified EMU Black V2 cruise log.
Expected values are the deterministic binary decode (cross-checked against the
row-aligned EMU CSV export to the decimal).
"""
import os

import pytest

from emublog2mlv import core

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "examples", "sample_cruise.emublog")


def test_sample_present():
    assert os.path.isfile(SAMPLE), "bundled sample log is missing"


def test_record_count_and_no_remainder():
    body, n, rem = core.read_records(SAMPLE)
    assert n == 750
    assert rem == 0, "sample should contain whole 308-byte records only"


def test_timebase_monotonic_and_anchored():
    body, n, _ = core.read_records(SAMPLE)
    t = core.build_timebase(body, n)
    assert t[0] == 0.0
    assert all(t[i] < t[i + 1] for i in range(n - 1)), "time must be strictly increasing"
    # ~31 s at ~25 Hz; reject the naive index/25 drift (which would give 749/25 = 29.96)
    assert 30.0 < t[-1] < 31.5


def test_record0_known_values():
    body, _n, _ = core.read_records(SAMPLE)
    r = core.decode_record(body, 0)
    assert r["RPM"] == 1887
    assert r["MAP"] == 63
    assert r["VE"] == pytest.approx(60.2)
    assert r["Lambda"] == pytest.approx(119 / 128)        # 0.9296875
    assert r["LambdaTarget"] == pytest.approx(0.99)
    assert r["CLT"] == 85                                  # u8 integer degrees C
    assert r["OilTemp"] == 61                              # u8 integer degrees C
    assert r["Ethanol"] == pytest.approx(79.5)
    assert r["FuelPressure"] == pytest.approx(30.82, abs=0.05)  # u8@114 x 0.90643
    assert r["FCustomCorrActive"] == 1


def test_derived_afr_consistency():
    body, _n, _ = core.read_records(SAMPLE)
    r = core.decode_record(body, 0)
    assert r["AFR"] == pytest.approx(r["Lambda"] * 14.7)
    assert r["AFRTarget"] == pytest.approx(r["LambdaTarget"] * 14.7)


def test_channel_names_units_aligned():
    assert len(core.channel_names()) == len(core.channel_units())
    assert "RPM" in core.channel_names()
    assert "FuelPressure" in core.channel_names()


def test_convert_msl(tmp_path):
    out = tmp_path / "out.msl"
    st = core.convert(SAMPLE, str(out), "msl")
    assert st["records"] == 750
    assert st["channels"] == 1 + len(core.channel_names())  # Time + channels
    lines = out.read_text().splitlines()
    assert lines[0].startswith('"MLVHD log')
    assert lines[1].split("\t")[0] == "Time"
    assert lines[2].split("\t")[0] == "s"
    assert len(lines) == 3 + 750                            # marker + names + units + data
    assert "\t" in lines[3] and "," not in lines[3]


def test_convert_csv(tmp_path):
    out = tmp_path / "out.csv"
    st = core.convert(SAMPLE, str(out), "csv")
    assert st["format"] == "csv"
    lines = out.read_text().splitlines()
    assert lines[0].split(",")[0] == "Time"                 # no MSL marker line for CSV
    assert len(lines) == 2 + 750                            # names + units + data


def test_default_output_extension():
    assert core.default_output("a/b/log.emublog", "msl").endswith("log.msl")
    assert core.default_output("log.emublog", "csv").endswith("log.csv")


def test_planned_output():
    # default: source stem + fmt ext, beside the source
    assert core.planned_output("log.emublog", "msl").endswith("log.msl")
    # custom output folder
    out = core.planned_output("log.emublog", "csv", out_dir=os.path.join("X", "Y"))
    assert out == os.path.join("X", "Y", "log.csv")
    # custom name for a single file
    assert core.planned_output("log.emublog", "msl", out_name="myname").endswith("myname.msl")
    # extension is forced to match fmt even if the custom name carries another one
    assert core.planned_output("log.emublog", "msl", out_name="myname.csv").endswith("myname.msl")
    # blank/whitespace name falls back to the source stem
    assert core.planned_output("log.emublog", "msl", out_name="  ").endswith("log.msl")


def test_bad_format_rejected(tmp_path):
    with pytest.raises(ValueError):
        core.convert(SAMPLE, str(tmp_path / "x"), "xml")


def test_summarize_ranges_sane():
    s = core.summarize(SAMPLE)
    assert s["records"] == 750
    by = {c["name"]: c for c in s["channels"]}
    assert 0 < by["RPM"]["min"] <= by["RPM"]["max"] < 8000
    assert 0.6 < by["Lambda"]["min"] <= by["Lambda"]["max"] < 1.4
    assert by["Ethanol"]["min"] == pytest.approx(79.5, abs=1.0)


def test_lambda_is_single_byte():
    """fw 2.176 puts a non-zero value in byte 44; lambda must ignore it."""
    body, _n, _ = core.read_records(SAMPLE)
    rec = bytearray(body[:core.RECORD_LEN])
    rec[43], rec[44] = 129, 10          # 129/128 = 1.0078; old u16 read gave 21.0078
    r = core.decode_record(bytes(rec), 0)
    assert r["Lambda"] == pytest.approx(129 / 128)
    assert r["AFR"] == pytest.approx(129 / 128 * 14.7)
