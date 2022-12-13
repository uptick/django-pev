# mypy: ignore-errors
from .utils import explain  # NOQA

try:
    import importlib.metadata as importlib_metadata  # type: ignore[import]
except ModuleNotFoundError:
    import importlib_metadata  # type: ignore[import]

__version__ = importlib_metadata.version(__name__)
