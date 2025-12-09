"""
Top-level package for the BCI project.

Provides convenient access to acquisition and preprocessing subpackages.
"""

from . import acquisition
# from . import preprocessing  # TODO: Create this module
from . import processing

__all__ = ["acquisition", "processing"]
