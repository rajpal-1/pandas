from datetime import datetime, time

import numpy as np
import pytest

from pandas._libs.tslibs import timezones
import pandas.util._test_decorators as td

from pandas import DataFrame, Series, date_range
import pandas._testing as tm


class TestBetweenTime:
    @pytest.mark.parametrize("tzstr", ["US/Eastern", "dateutil/US/Eastern"])
    def test_localized_between_time(self, tzstr):
        tz = timezones.maybe_get_tz(tzstr)

        rng = date_range("4/16/2012", "5/1/2012", freq="H")
        ts = Series(np.random.randn(len(rng)), index=rng)

        ts_local = ts.tz_localize(tzstr)

        t1, t2 = time(10, 0), time(11, 0)
        result = ts_local.between_time(t1, t2)
        expected = ts.between_time(t1, t2).tz_localize(tzstr)
        tm.assert_series_equal(result, expected)
        assert timezones.tz_compare(result.index.tz, tz)

    def test_between_time_types(self):
        # GH11818
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        msg = r"Cannot convert arg \[datetime\.datetime\(2010, 1, 2, 1, 0\)\] to a time"
        with pytest.raises(ValueError, match=msg):
            rng.indexer_between_time(datetime(2010, 1, 2, 1), datetime(2010, 1, 2, 5))

        frame = DataFrame({"A": 0}, index=rng)
        with pytest.raises(ValueError, match=msg):
            frame.between_time(datetime(2010, 1, 2, 1), datetime(2010, 1, 2, 5))

        series = Series(0, index=rng)
        with pytest.raises(ValueError, match=msg):
            series.between_time(datetime(2010, 1, 2, 1), datetime(2010, 1, 2, 5))

    @td.skip_if_has_locale
    def test_between_time_formats(self):
        # GH11818
        rng = date_range("1/1/2000", "1/5/2000", freq="5min")
        ts = DataFrame(np.random.randn(len(rng), 2), index=rng)

        strings = [
            ("2:00", "2:30"),
            ("0200", "0230"),
            ("2:00am", "2:30am"),
            ("0200am", "0230am"),
            ("2:00:00", "2:30:00"),
            ("020000", "023000"),
            ("2:00:00am", "2:30:00am"),
            ("020000am", "023000am"),
        ]
        expected_length = 28

        for time_string in strings:
            assert len(ts.between_time(*time_string)) == expected_length

    def test_between_time_axis(self):
        # issue 8839
        rng = date_range("1/1/2000", periods=100, freq="10min")
        ts = Series(np.random.randn(len(rng)), index=rng)
        stime, etime = ("08:00:00", "09:00:00")
        expected_length = 7

        assert len(ts.between_time(stime, etime)) == expected_length
        assert len(ts.between_time(stime, etime, axis=0)) == expected_length
        msg = "No axis named 1 for object type Series"
        with pytest.raises(ValueError, match=msg):
            ts.between_time(stime, etime, axis=1)
