"""
Minimal library intended for CircuitPython usage.
It is **not** aimed to be a full compliant TOML parser,
but a good enough solution for embedded devices.

Non-exhaustive list of missing features/wrong behaviour:
  - Multi-line strings (triple quotes)
  - Escape sequences in strings
      * Some may work if you do eg: value.replace("\\n", \n")
  - Nested lists:
  - Strings in lists
"""

__author__ = "elpekenin"
__version__ = (0, 1, 1)

from ._toml import *
