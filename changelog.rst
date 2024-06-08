Changelog
=========


Version 0.1.10 (8th Jun 2024)
-----------------------------

* Remove raw-fstring, not supported by mpy-cross


Version 0.1.9 (8th Jun 2024)
----------------------------

Refactor of the parser, to get closer to the specification
* Add functionality to test against spec (`toml-test`)
* Parse inline (not multiline) triple-quoted strings (`"""` and `'''`)
* Handle quoted keys as expected (`"key.value" = 0` != `key.value = 0`)
* Support escape sequences
* `inf` and `nan`
* Numbers with underscores
* Better string parsing, may still fail, and perhaps some missed regression
* Extra validations that were not done yet (eg: double sign is invalid)


Version 0.1.8 (1st Jun 2024)
----------------------------

* Fix #6 (@dtcooper), "selected" table should not be reset upon finding an empty line
* Remove functionality (against common libraries) to accept strings in `load` and `dump`
* Remove `ignore_exc`


Version 0.1.7 (6th Apr 2024)
----------------------------

* Fix #5 (@joshua-beck-0908), we can handle multiple strings! (and some refactor)


Version 0.1.6 (21st Dec 2023)
----------------------------

* Cleanup some typing and var names
* Implement `__contains__` and `__delitem__` (partial fix for #4)


Version 0.1.5 (18th Dec 2023)
----------------------------

* Add support for both paths and files on `toml.load` and `toml.dump`
* Refactor test suite


Version 0.1.4 (27th Nov 2023)
----------------------------

* Fix #3 (@jepler), should not crash with empty mappings
* Add test case for empty dicts to cover edge cases like the one above


Version 0.1.3 (16th Nov 2023)
----------------------------

* Cleanup prior to PR into Community Bundle


Version 0.1.2 (7th Aug 2023)
----------------------------

* Merged #2 (@bill88t), reducing RAM usage + format on CI/CD
* Actual parsing of arrays
* More compliant with TOML spec (@tannewt feedback)


Version 0.1.1 (1st Aug 2023)
----------------------------

* Re-do with decent architecture (token + syntaxchecker + parser) instead of tons of coupling


Version 0.0.0 (Late July 2023)
------------------------------

* Basic and ugly version
* Didnt really have a version number, dunno actual date
