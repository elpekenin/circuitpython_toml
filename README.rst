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

While this is good enough for many use cases, i felt like writing a feature-complete(ish) parser would be nice for the sake of learning but also to help other users getting around these limitations.

Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_

i.e. No dependencies :)

Features
========

Covers (what i feel are) the most useful parts of the TOML spec.

Some unsupported things are (non-exhaustive list):

* Multi-line strings (aka triple quoted ones)
* Quoted keys
* Re-definition of keys is allowed (against spec)
* Date literals
* Scientific notation (eg 10e3)
* Separators in numbers (eg 10_000)

Usage Example
=============

It's pretty straight forward, it's similar to the `toml` module on CPython's standard lib.
Here's a little example showing the power of `Dotty` for accessing nested items.

.. code-block:: python

   >>> import toml
   >>> data = toml.load("settings.toml")
   >>> data["foo"]["bar"]
   "baz"
   >>> data["foo.bar"]
   "baz"

Contributing
============

TODO: Proper list of requisites and whatnot.
For now just open PRs and issues, they are very much welcome!!

Acknowledgements
================

`dotty_dict <https://github.com/pawelzny/dotty_dict>`_ For the inspiration to do a wrapper on top of a dict to easily access items based on dotted keys (`Dotty` is a subset of said library)
