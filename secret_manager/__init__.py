# Load pydantic fully before any PySide6 import: shiboken's import hook inspects each
# module as it loads and trips over pydantic's lazily loaded attributes otherwise
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError  # noqa: F401
