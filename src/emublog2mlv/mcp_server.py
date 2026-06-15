"""
MCP (Model Context Protocol) server exposing emublog2mlv as AI-callable tools.

Run it as a stdio MCP server:

    emublog2mlv-mcp
    # or: python -m emublog2mlv.mcp_server

Register it with an MCP client (Claude Desktop / Claude Code), e.g.:

    claude mcp add emublog2mlv -- emublog2mlv-mcp

Tools exposed:
    convert_emublog(input_path, output_format="msl", output_path=None) -> stats
    emublog_summary(input_path) -> metadata + per-channel min/max/mean
    list_channels() -> the decoded channel map
"""
from __future__ import annotations

import os
from typing import Optional

from .core import CHANNELS, DERIVED, convert, summarize

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise SystemExit(
        "The MCP SDK is not installed. Install it with:\n"
        "    pip install \"emublog2mlv[mcp]\"\n"
        "or:\n"
        "    pip install mcp"
    ) from exc

mcp = FastMCP("emublog2mlv")


def _require_file(path: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"input_path not found or not a file: {path}")


@mcp.tool()
def convert_emublog(
    input_path: str,
    output_format: str = "msl",
    output_path: Optional[str] = None,
) -> dict:
    """Convert an ECU Master EMU Black ``.emublog`` binary log into a
    MegaLogViewer HD log.

    Args:
        input_path: path to the ``.emublog`` file.
        output_format: ``"msl"`` (tab-delimited MegaSquirt log, default) or ``"csv"``.
        output_path: where to write; if omitted, derived from ``input_path``.

    Returns conversion stats: input, output, format, records, duration_s,
    channels, sample_rate_hz, trailing_bytes.
    """
    _require_file(input_path)
    return convert(input_path, output_path, output_format)


@mcp.tool()
def emublog_summary(input_path: str) -> dict:
    """Decode an ``.emublog`` and return metadata plus per-channel
    min/max/mean/first/last — without writing any file. Use this to inspect a
    log (e.g. find a lean spot or check fuel pressure) before converting.
    """
    _require_file(input_path)
    return summarize(input_path)


@mcp.tool()
def list_channels() -> list:
    """List the channels this converter decodes (name, unit, byte offset, width,
    scale). Useful to understand or extend the channel map.
    """
    out = []
    for name, unit, off, kind, scale, extra in CHANNELS:
        out.append({
            "name": name, "unit": unit, "offset": off,
            "kind": kind, "scale": scale, "bit": extra,
        })
    for name, unit, _fn in DERIVED:
        out.append({"name": name, "unit": unit, "kind": "derived"})
    return out


def main():
    mcp.run()


if __name__ == "__main__":
    main()
