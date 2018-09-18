# -*- coding: utf-8 -*-
"""
Tests for DatetimeIndex methods behaving like their Timestamp counterparts
"""
from datetime import datetime

import numpy as np
import pytest

import pandas.util.testing as tm
import pandas as pd

from pandas import date_range, Timestamp, DatetimeIndex
from pandas.tseries.frequencies import to_offset


class TestDatetimeIndexOps(object):
    def test_dti_time(self):
        rng = date_range('1/1/2000', freq='12min', periods=10)
        result = pd.Index(rng).time
        expected = [t.time() for t in rng]
        assert (result == expected).all()

    def test_dti_date(self):
        rng = date_range('1/1/2000', freq='12H', periods=10)
        result = pd.Index(rng).date
        expected = [t.date() for t in rng]
        assert (result == expected).all()

    def test_dti_date_out_of_range(self):
        # GH#1475
        pytest.raises(ValueError, DatetimeIndex, ['1400-01-01'])
        pytest.raises(ValueError, DatetimeIndex, [datetime(1400, 1, 1)])

    @pytest.mark.parametrize('field', [
        'dayofweek', 'dayofyear', 'week', 'weekofyear', 'quarter',
        'days_in_month', 'is_month_start', 'is_month_end',
        'is_quarter_start', 'is_quarter_end', 'is_year_start',
        'is_year_end', 'weekday_name'])
    def test_dti_timestamp_fields(self, field):
        # extra fields from DatetimeIndex like quarter and week
        idx = tm.makeDateIndex(100)
        expected = getattr(idx, field)[-1]
        if field == 'weekday_name':
            with tm.assert_produces_warning(FutureWarning,
                                            check_stacklevel=False):
                result = getattr(Timestamp(idx[-1]), field)
        else:
            result = getattr(Timestamp(idx[-1]), field)
        assert result == expected

    def test_dti_timestamp_freq_fields(self):
        # extra fields from DatetimeIndex like quarter and week
        idx = tm.makeDateIndex(100)

        assert idx.freq == Timestamp(idx[-1], idx.freq).freq
        assert idx.freqstr == Timestamp(idx[-1], idx.freq).freqstr

    # ----------------------------------------------------------------
    # DatetimeIndex.round

    def test_round_daily(self):
        dti = date_range('20130101 09:10:11', periods=5)
        result = dti.round('D')
        expected = date_range('20130101', periods=5)
        tm.assert_index_equal(result, expected)

        dti = dti.tz_localize('UTC').tz_convert('US/Eastern')
        result = dti.round('D')
        expected = date_range('20130101',
                              periods=5).tz_localize('US/Eastern')
        tm.assert_index_equal(result, expected)

        result = dti.round('s')
        tm.assert_index_equal(result, dti)

        # invalid
        for freq in ['Y', 'M', 'foobar']:
            pytest.raises(ValueError, lambda: dti.round(freq))

    def test_round(self, tz_naive_fixture):
        tz = tz_naive_fixture
        rng = date_range(start='2016-01-01', periods=5,
                         freq='30Min', tz=tz)
        elt = rng[1]

        expected_rng = DatetimeIndex([
            Timestamp('2016-01-01 00:00:00', tz=tz, freq='30T'),
            Timestamp('2016-01-01 00:00:00', tz=tz, freq='30T'),
            Timestamp('2016-01-01 01:00:00', tz=tz, freq='30T'),
            Timestamp('2016-01-01 02:00:00', tz=tz, freq='30T'),
            Timestamp('2016-01-01 02:00:00', tz=tz, freq='30T'),
        ])
        expected_elt = expected_rng[1]

        tm.assert_index_equal(rng.round(freq='H'), expected_rng)
        assert elt.round(freq='H') == expected_elt

        msg = pd._libs.tslibs.frequencies.INVALID_FREQ_ERR_MSG
        with tm.assert_raises_regex(ValueError, msg):
            rng.round(freq='foo')
        with tm.assert_raises_regex(ValueError, msg):
            elt.round(freq='foo')

        msg = "<MonthEnd> is a non-fixed frequency"
        tm.assert_raises_regex(ValueError, msg, rng.round, freq='M')
        tm.assert_raises_regex(ValueError, msg, elt.round, freq='M')

        # GH#14440 & GH#15578
        index = DatetimeIndex(['2016-10-17 12:00:00.0015'], tz=tz)
        result = index.round('ms')
        expected = DatetimeIndex(['2016-10-17 12:00:00.002000'], tz=tz)
        tm.assert_index_equal(result, expected)

        for freq in ['us', 'ns']:
            tm.assert_index_equal(index, index.round(freq))

        index = DatetimeIndex(['2016-10-17 12:00:00.00149'], tz=tz)
        result = index.round('ms')
        expected = DatetimeIndex(['2016-10-17 12:00:00.001000'], tz=tz)
        tm.assert_index_equal(result, expected)

        index = DatetimeIndex(['2016-10-17 12:00:00.001501031'])
        result = index.round('10ns')
        expected = DatetimeIndex(['2016-10-17 12:00:00.001501030'])
        tm.assert_index_equal(result, expected)

        with tm.assert_produces_warning(False):
            ts = '2016-10-17 12:00:00.001501031'
            DatetimeIndex([ts]).round('1010ns')

    def test_no_rounding_occurs(self, tz_naive_fixture):
        # GH 21262
        tz = tz_naive_fixture
        rng = date_range(start='2016-01-01', periods=5,
                         freq='2Min', tz=tz)

        expected_rng = DatetimeIndex([
            Timestamp('2016-01-01 00:00:00', tz=tz, freq='2T'),
            Timestamp('2016-01-01 00:02:00', tz=tz, freq='2T'),
            Timestamp('2016-01-01 00:04:00', tz=tz, freq='2T'),
            Timestamp('2016-01-01 00:06:00', tz=tz, freq='2T'),
            Timestamp('2016-01-01 00:08:00', tz=tz, freq='2T'),
        ])

        tm.assert_index_equal(rng.round(freq='2T'), expected_rng)

    @pytest.mark.parametrize('test_input, rounder, freq, expected', [
        (['2117-01-01 00:00:45'], 'floor', '15s', ['2117-01-01 00:00:45']),
        (['2117-01-01 00:00:45'], 'ceil', '15s', ['2117-01-01 00:00:45']),
        (['2117-01-01 00:00:45.000000012'], 'floor', '10ns',
         ['2117-01-01 00:00:45.000000010']),
        (['1823-01-01 00:00:01.000000012'], 'ceil', '10ns',
         ['1823-01-01 00:00:01.000000020']),
        (['1823-01-01 00:00:01'], 'floor', '1s', ['1823-01-01 00:00:01']),
        (['1823-01-01 00:00:01'], 'ceil', '1s', ['1823-01-01 00:00:01']),
        (['2018-01-01 00:15:00'], 'ceil', '15T', ['2018-01-01 00:15:00']),
        (['2018-01-01 00:15:00'], 'floor', '15T', ['2018-01-01 00:15:00']),
        (['1823-01-01 03:00:00'], 'ceil', '3H', ['1823-01-01 03:00:00']),
        (['1823-01-01 03:00:00'], 'floor', '3H', ['1823-01-01 03:00:00']),
        (('NaT', '1823-01-01 00:00:01'), 'floor', '1s',
         ('NaT', '1823-01-01 00:00:01')),
        (('NaT', '1823-01-01 00:00:01'), 'ceil', '1s',
         ('NaT', '1823-01-01 00:00:01'))
    ])
    def test_ceil_floor_edge(self, test_input, rounder, freq, expected):
        dt = DatetimeIndex(list(test_input))
        func = getattr(dt, rounder)
        result = func(freq)
        expected = DatetimeIndex(list(expected))
        assert expected.equals(result)

    @pytest.mark.parametrize('start, index_freq, periods', [
        ('2018-01-01', '12H', 25),
        ('2018-01-01 0:0:0.124999', '1ns', 1000),
    ])
    @pytest.mark.parametrize('rounding_freq', [
        '2ns', '3ns', '4ns', '5ns', '6ns', '7ns',
        '250ns', '500ns', '750ns',
        '1us', '19us', '250us', '500us', '750us',
        '1s', '2s', '3s',
        '12H', '1D',
    ])
    def test_round_int64(self, start, index_freq, periods, rounding_freq):
        dt = DatetimeIndex(start=start, freq=index_freq, periods=periods)
        unit = to_offset(rounding_freq).nanos
        # test floor
        result = dt.floor(rounding_freq).asi8
        diff = dt.asi8 - result
        mod = result % unit
        assert (mod == 0).all(), "floor not a %s multiple" % (rounding_freq, )
        assert (0 <= diff).all() and (diff < unit).all(), "floor error"
        # test ceil
        result = dt.ceil(rounding_freq).asi8
        diff = result - dt.asi8
        mod = result % unit
        assert (mod == 0).all(), "ceil not a %s multiple" % (rounding_freq, )
        assert (0 <= diff).all() and (diff < unit).all(), "ceil error"
        # test round
        result = dt.round(rounding_freq).asi8
        diff = abs(result - dt.asi8)
        mod = result % unit
        assert (mod == 0).all(), "round not a %s multiple" % (rounding_freq, )
        assert (diff <= unit // 2).all(), "round error"
        if unit % 2 == 0:
            assert (
                result[diff == unit // 2] % 2 == 0
            ).all(), "round half to even error"

    # ----------------------------------------------------------------
    # DatetimeIndex.normalize

    def test_normalize(self):
        rng = date_range('1/1/2000 9:30', periods=10, freq='D')

        result = rng.normalize()
        expected = date_range('1/1/2000', periods=10, freq='D')
        tm.assert_index_equal(result, expected)

        arr_ns = np.array([1380585623454345752,
                           1380585612343234312]).astype("datetime64[ns]")
        rng_ns = DatetimeIndex(arr_ns)
        rng_ns_normalized = rng_ns.normalize()

        arr_ns = np.array([1380585600000000000,
                           1380585600000000000]).astype("datetime64[ns]")
        expected = DatetimeIndex(arr_ns)
        tm.assert_index_equal(rng_ns_normalized, expected)

        assert result.is_normalized
        assert not rng.is_normalized


class TestDateTimeIndexToJulianDate(object):

    def test_1700(self):
        dr = date_range(start=Timestamp('1710-10-01'), periods=5, freq='D')
        r1 = pd.Index([x.to_julian_date() for x in dr])
        r2 = dr.to_julian_date()
        assert isinstance(r2, pd.Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_2000(self):
        dr = date_range(start=Timestamp('2000-02-27'), periods=5, freq='D')
        r1 = pd.Index([x.to_julian_date() for x in dr])
        r2 = dr.to_julian_date()
        assert isinstance(r2, pd.Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_hour(self):
        dr = date_range(start=Timestamp('2000-02-27'), periods=5, freq='H')
        r1 = pd.Index([x.to_julian_date() for x in dr])
        r2 = dr.to_julian_date()
        assert isinstance(r2, pd.Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_minute(self):
        dr = date_range(start=Timestamp('2000-02-27'), periods=5, freq='T')
        r1 = pd.Index([x.to_julian_date() for x in dr])
        r2 = dr.to_julian_date()
        assert isinstance(r2, pd.Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_second(self):
        dr = date_range(start=Timestamp('2000-02-27'), periods=5, freq='S')
        r1 = pd.Index([x.to_julian_date() for x in dr])
        r2 = dr.to_julian_date()
        assert isinstance(r2, pd.Float64Index)
        tm.assert_index_equal(r1, r2)
