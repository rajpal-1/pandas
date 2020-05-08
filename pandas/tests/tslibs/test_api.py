"""Tests that the tslibs API is locked down"""

from pandas._libs import tslibs


def test_namespace():

    submodules = [
        "base",
        "ccalendar",
        "conversion",
        "fields",
        "frequencies",
        "nattype",
        "np_datetime",
        "offsets",
        "parsing",
        "period",
        "resolution",
        "strptime",
        "timedeltas",
        "timestamps",
        "timezones",
        "tzconversion",
    ]

    api = [
        "NaT",
        "NaTType",
        "iNaT",
        "is_null_datetimelike",
        "NullFrequencyError",
        "OutOfBoundsDatetime",
        "Period",
        "IncompatibleFrequency",
        "Timedelta",
        "Timestamp",
        "delta_to_nanoseconds",
        "ints_to_pytimedelta",
        "localize_pydatetime",
        "tz_convert_single",
    ]

    expected = set(submodules + api)
    names = [x for x in dir(tslibs) if not x.startswith("__")]
    assert set(names) == expected
