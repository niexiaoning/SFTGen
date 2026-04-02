"""TextGraphTree package."""

from ._version import __version__, version_info
from .engine import TextGraphTree
from .tgt_pipeline import TGTPipeline

__all__ = ["TextGraphTree", "TGTPipeline", "__version__", "version_info"]
