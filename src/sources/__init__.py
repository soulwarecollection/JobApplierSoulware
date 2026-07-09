"""Job sources. Each adapter returns a list[Job]. No LinkedIn/Indeed scraping."""
from .remotive import RemotiveSource
from .remoteok import RemoteOKSource
from .greenhouse import GreenhouseSource
from .lever import LeverSource

__all__ = ["RemotiveSource", "RemoteOKSource", "GreenhouseSource", "LeverSource"]
