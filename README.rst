******************
circuitpython_toml
******************

:Info: Basic(TM) library meant to work with a subset of TOML spec, intended to be used on CircuitPython.
:Author: Pablo Martinez Bernal <elpekenin@elpekenin.dev>

Motivation
==========

As of summer 2023, `os.getenv`:

* Only supports reading base-10 integers and strings.
* File to be read is hardcoded at compilation (`settings.toml` by default).
* Can only read one key at a time.
* Cant change values. To be fair, most of the times CircuitPython will have read-only access t othe filesystem, anyway.

While this is good enough for many use cases, i felt like writing a feature-complete(ish) parser would be nice for the sake of learning but also to help other users getting around these limitations

Features
========

Covers a nice amount of the TOML spec, some of the limitations are (non-exhaustive list):

* Multi-line strings (aka triple quoted ones)
* Quoted keys
* Re-definition of keys is allowed (against spec)
* Date literals
* Scientific notation (eg 10e3)
* Separators in numbers (eg 10_000)

Contributing
============

TODO: Proper list of requisites and whatnot. For now just open PRs and issues as desired.

Acknowledgements
================

`dotty_dict <https://github.com/pawelzny/dotty_dict>`_ For the inspiration for the wrapper (which is also a subset re-implementation) to easily set values based on dotted keys
