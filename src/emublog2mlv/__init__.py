"""emublog2mlv — convert ECU Master EMU Black .emublog logs to MegaLogViewer HD."""
from .core import (
    CHANNELS,
    DERIVED,
    channel_names,
    channel_units,
    convert,
    planned_output,
    summarize,
)

__version__ = "1.2.0"
__all__ = [
    "convert",
    "summarize",
    "planned_output",
    "channel_names",
    "channel_units",
    "CHANNELS",
    "DERIVED",
    "__version__",
]
