"""emublog2mlv — convert ECU Master EMU Black .emublog logs to MegaLogViewer HD."""
from .core import (
    CHANNELS,
    DERIVED,
    channel_names,
    channel_units,
    convert,
    summarize,
)

__version__ = "1.0.0"
__all__ = [
    "convert",
    "summarize",
    "channel_names",
    "channel_units",
    "CHANNELS",
    "DERIVED",
    "__version__",
]
