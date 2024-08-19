# SPDX-FileCopyrightText: 2024 Pablo Martinez Bernal (elpekenin)
#
# SPDX-License-Identifier: MIT

"""TOML parser to be used on CircuitPython."""

__author__ = "elpekenin"
__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/elpekenin/CircuitPython_toml.git"

from ._toml import TOMLError, dump, dumps, load, loads

__all__ = [
    "TOMLError",
    "loads",
    "load",
    "dumps",
    "dump",
]
