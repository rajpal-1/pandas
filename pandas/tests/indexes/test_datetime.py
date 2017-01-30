
import warnings
import numpy as np
from numpy.random import rand
from datetime import datetime, time, timedelta

import pandas as pd
import pandas.util.testing as tm
import pandas.compat as compat
from pandas.compat import lrange
from pandas.core.common import PerformanceWarning
from pandas.compat.numpy import np_datetime64_compat
from pandas import (
    Series, DataFrame, Timestamp, Index, Int64Index, Float64Index, date_range,
    bdate_range, offsets, datetime, DatetimeIndex, _np_version_under1p8)
from pandas.util.testing import (
    assert_frame_equal, assert_series_equal, assert_almost_equal,
    _skip_if_has_locale, slow)


randn = np.random.randn


class TestDatetimeIndex(tm.TestCase):
    _multiprocess_can_split_ = True

    def test_hash_error(self):
        index = date_range('20010101', periods=10)
        with tm.assertRaisesRegexp(TypeError, "unhashable type: %r" %
                                   type(index).__name__):
            hash(index)

    def test_stringified_slice_with_tz(self):
        # GH2658
        import datetime
        start = datetime.datetime.now()
        idx = DatetimeIndex(start=start, freq="1d", periods=10)
        df = DataFrame(lrange(10), index=idx)
        df["2013-01-14 23:44:34.437768-05:00":]  # no exception here

    def test_append_join_nondatetimeindex(self):
        rng = date_range('1/1/2000', periods=10)
        idx = Index(['a', 'b', 'c', 'd'])

        result = rng.append(idx)
        tm.assertIsInstance(result[0], Timestamp)

        # it works
        rng.join(idx, how='outer')

    def test_to_period_nofreq(self):
        idx = DatetimeIndex(['2000-01-01', '2000-01-02', '2000-01-04'])
        self.assertRaises(ValueError, idx.to_period)

        idx = DatetimeIndex(['2000-01-01', '2000-01-02', '2000-01-03'],
                            freq='infer')
        self.assertEqual(idx.freqstr, 'D')
        expected = pd.PeriodIndex(['2000-01-01', '2000-01-02',
                                   '2000-01-03'], freq='D')
        tm.assert_index_equal(idx.to_period(), expected)

        # GH 7606
        idx = DatetimeIndex(['2000-01-01', '2000-01-02', '2000-01-03'])
        self.assertEqual(idx.freqstr, None)
        tm.assert_index_equal(idx.to_period(), expected)

    def test_000constructor_resolution(self):
        # 2252
        t1 = Timestamp((1352934390 * 1000000000) + 1000000 + 1000 + 1)
        idx = DatetimeIndex([t1])

        self.assertEqual(idx.nanosecond[0], t1.nanosecond)

    def test_constructor_coverage(self):
        rng = date_range('1/1/2000', periods=10.5)
        exp = date_range('1/1/2000', periods=10)
        tm.assert_index_equal(rng, exp)

        self.assertRaises(ValueError, DatetimeIndex, start='1/1/2000',
                          periods='foo', freq='D')

        self.assertRaises(ValueError, DatetimeIndex, start='1/1/2000',
                          end='1/10/2000')

        self.assertRaises(ValueError, DatetimeIndex, '1/1/2000')

        # generator expression
        gen = (datetime(2000, 1, 1) + timedelta(i) for i in range(10))
        result = DatetimeIndex(gen)
        expected = DatetimeIndex([datetime(2000, 1, 1) + timedelta(i)
                                  for i in range(10)])
        tm.assert_index_equal(result, expected)

        # NumPy string array
        strings = np.array(['2000-01-01', '2000-01-02', '2000-01-03'])
        result = DatetimeIndex(strings)
        expected = DatetimeIndex(strings.astype('O'))
        tm.assert_index_equal(result, expected)

        from_ints = DatetimeIndex(expected.asi8)
        tm.assert_index_equal(from_ints, expected)

        # string with NaT
        strings = np.array(['2000-01-01', '2000-01-02', 'NaT'])
        result = DatetimeIndex(strings)
        expected = DatetimeIndex(strings.astype('O'))
        tm.assert_index_equal(result, expected)

        from_ints = DatetimeIndex(expected.asi8)
        tm.assert_index_equal(from_ints, expected)

        # non-conforming
        self.assertRaises(ValueError, DatetimeIndex,
                          ['2000-01-01', '2000-01-02', '2000-01-04'], freq='D')

        self.assertRaises(ValueError, DatetimeIndex, start='2011-01-01',
                          freq='b')
        self.assertRaises(ValueError, DatetimeIndex, end='2011-01-01',
                          freq='B')
        self.assertRaises(ValueError, DatetimeIndex, periods=10, freq='D')

    def test_constructor_datetime64_tzformat(self):
        # GH 6572
        tm._skip_if_no_pytz()
        import pytz
        # ISO 8601 format results in pytz.FixedOffset
        for freq in ['AS', 'W-SUN']:
            idx = date_range('2013-01-01T00:00:00-05:00',
                             '2016-01-01T23:59:59-05:00', freq=freq)
            expected = date_range('2013-01-01T00:00:00', '2016-01-01T23:59:59',
                                  freq=freq, tz=pytz.FixedOffset(-300))
            tm.assert_index_equal(idx, expected)
            # Unable to use `US/Eastern` because of DST
            expected_i8 = date_range('2013-01-01T00:00:00',
                                     '2016-01-01T23:59:59', freq=freq,
                                     tz='America/Lima')
            self.assert_numpy_array_equal(idx.asi8, expected_i8.asi8)

            idx = date_range('2013-01-01T00:00:00+09:00',
                             '2016-01-01T23:59:59+09:00', freq=freq)
            expected = date_range('2013-01-01T00:00:00', '2016-01-01T23:59:59',
                                  freq=freq, tz=pytz.FixedOffset(540))
            tm.assert_index_equal(idx, expected)
            expected_i8 = date_range('2013-01-01T00:00:00',
                                     '2016-01-01T23:59:59', freq=freq,
                                     tz='Asia/Tokyo')
            self.assert_numpy_array_equal(idx.asi8, expected_i8.asi8)

        tm._skip_if_no_dateutil()

        # Non ISO 8601 format results in dateutil.tz.tzoffset
        for freq in ['AS', 'W-SUN']:
            idx = date_range('2013/1/1 0:00:00-5:00', '2016/1/1 23:59:59-5:00',
                             freq=freq)
            expected = date_range('2013-01-01T00:00:00', '2016-01-01T23:59:59',
                                  freq=freq, tz=pytz.FixedOffset(-300))
            tm.assert_index_equal(idx, expected)
            # Unable to use `US/Eastern` because of DST
            expected_i8 = date_range('2013-01-01T00:00:00',
                                     '2016-01-01T23:59:59', freq=freq,
                                     tz='America/Lima')
            self.assert_numpy_array_equal(idx.asi8, expected_i8.asi8)

            idx = date_range('2013/1/1 0:00:00+9:00',
                             '2016/1/1 23:59:59+09:00', freq=freq)
            expected = date_range('2013-01-01T00:00:00', '2016-01-01T23:59:59',
                                  freq=freq, tz=pytz.FixedOffset(540))
            tm.assert_index_equal(idx, expected)
            expected_i8 = date_range('2013-01-01T00:00:00',
                                     '2016-01-01T23:59:59', freq=freq,
                                     tz='Asia/Tokyo')
            self.assert_numpy_array_equal(idx.asi8, expected_i8.asi8)

    def test_constructor_dtype(self):

        # passing a dtype with a tz should localize
        idx = DatetimeIndex(['2013-01-01', '2013-01-02'],
                            dtype='datetime64[ns, US/Eastern]')
        expected = DatetimeIndex(['2013-01-01', '2013-01-02']
                                 ).tz_localize('US/Eastern')
        tm.assert_index_equal(idx, expected)

        idx = DatetimeIndex(['2013-01-01', '2013-01-02'],
                            tz='US/Eastern')
        tm.assert_index_equal(idx, expected)

        # if we already have a tz and its not the same, then raise
        idx = DatetimeIndex(['2013-01-01', '2013-01-02'],
                            dtype='datetime64[ns, US/Eastern]')

        self.assertRaises(ValueError,
                          lambda: DatetimeIndex(idx,
                                                dtype='datetime64[ns]'))

        # this is effectively trying to convert tz's
        self.assertRaises(TypeError,
                          lambda: DatetimeIndex(idx,
                                                dtype='datetime64[ns, CET]'))
        self.assertRaises(ValueError,
                          lambda: DatetimeIndex(
                              idx, tz='CET',
                              dtype='datetime64[ns, US/Eastern]'))
        result = DatetimeIndex(idx, dtype='datetime64[ns, US/Eastern]')
        tm.assert_index_equal(idx, result)

    def test_constructor_name(self):
        idx = DatetimeIndex(start='2000-01-01', periods=1, freq='A',
                            name='TEST')
        self.assertEqual(idx.name, 'TEST')

    def test_comparisons_coverage(self):
        rng = date_range('1/1/2000', periods=10)

        # raise TypeError for now
        self.assertRaises(TypeError, rng.__lt__, rng[3].value)

        result = rng == list(rng)
        exp = rng == rng
        self.assert_numpy_array_equal(result, exp)

    def test_comparisons_nat(self):

        fidx1 = pd.Index([1.0, np.nan, 3.0, np.nan, 5.0, 7.0])
        fidx2 = pd.Index([2.0, 3.0, np.nan, np.nan, 6.0, 7.0])

        didx1 = pd.DatetimeIndex(['2014-01-01', pd.NaT, '2014-03-01', pd.NaT,
                                  '2014-05-01', '2014-07-01'])
        didx2 = pd.DatetimeIndex(['2014-02-01', '2014-03-01', pd.NaT, pd.NaT,
                                  '2014-06-01', '2014-07-01'])
        darr = np.array([np_datetime64_compat('2014-02-01 00:00Z'),
                         np_datetime64_compat('2014-03-01 00:00Z'),
                         np_datetime64_compat('nat'), np.datetime64('nat'),
                         np_datetime64_compat('2014-06-01 00:00Z'),
                         np_datetime64_compat('2014-07-01 00:00Z')])

        if _np_version_under1p8:
            # cannot test array because np.datetime('nat') returns today's date
            cases = [(fidx1, fidx2), (didx1, didx2)]
        else:
            cases = [(fidx1, fidx2), (didx1, didx2), (didx1, darr)]

        # Check pd.NaT is handles as the same as np.nan
        with tm.assert_produces_warning(None):
            for idx1, idx2 in cases:

                result = idx1 < idx2
                expected = np.array([True, False, False, False, True, False])
                self.assert_numpy_array_equal(result, expected)

                result = idx2 > idx1
                expected = np.array([True, False, False, False, True, False])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 <= idx2
                expected = np.array([True, False, False, False, True, True])
                self.assert_numpy_array_equal(result, expected)

                result = idx2 >= idx1
                expected = np.array([True, False, False, False, True, True])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 == idx2
                expected = np.array([False, False, False, False, False, True])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 != idx2
                expected = np.array([True, True, True, True, True, False])
                self.assert_numpy_array_equal(result, expected)

        with tm.assert_produces_warning(None):
            for idx1, val in [(fidx1, np.nan), (didx1, pd.NaT)]:
                result = idx1 < val
                expected = np.array([False, False, False, False, False, False])
                self.assert_numpy_array_equal(result, expected)
                result = idx1 > val
                self.assert_numpy_array_equal(result, expected)

                result = idx1 <= val
                self.assert_numpy_array_equal(result, expected)
                result = idx1 >= val
                self.assert_numpy_array_equal(result, expected)

                result = idx1 == val
                self.assert_numpy_array_equal(result, expected)

                result = idx1 != val
                expected = np.array([True, True, True, True, True, True])
                self.assert_numpy_array_equal(result, expected)

        # Check pd.NaT is handles as the same as np.nan
        with tm.assert_produces_warning(None):
            for idx1, val in [(fidx1, 3), (didx1, datetime(2014, 3, 1))]:
                result = idx1 < val
                expected = np.array([True, False, False, False, False, False])
                self.assert_numpy_array_equal(result, expected)
                result = idx1 > val
                expected = np.array([False, False, False, False, True, True])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 <= val
                expected = np.array([True, False, True, False, False, False])
                self.assert_numpy_array_equal(result, expected)
                result = idx1 >= val
                expected = np.array([False, False, True, False, True, True])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 == val
                expected = np.array([False, False, True, False, False, False])
                self.assert_numpy_array_equal(result, expected)

                result = idx1 != val
                expected = np.array([True, True, False, True, True, True])
                self.assert_numpy_array_equal(result, expected)

    def test_map(self):
        rng = date_range('1/1/2000', periods=10)

        f = lambda x: x.strftime('%Y%m%d')
        result = rng.map(f)
        exp = Index([f(x) for x in rng], dtype='<U8')
        tm.assert_index_equal(result, exp)

    def test_iteration_preserves_tz(self):

        tm._skip_if_no_dateutil()

        # GH 8890
        import dateutil
        index = date_range("2012-01-01", periods=3, freq='H', tz='US/Eastern')

        for i, ts in enumerate(index):
            result = ts
            expected = index[i]
            self.assertEqual(result, expected)

        index = date_range("2012-01-01", periods=3, freq='H',
                           tz=dateutil.tz.tzoffset(None, -28800))

        for i, ts in enumerate(index):
            result = ts
            expected = index[i]
            self.assertEqual(result._repr_base, expected._repr_base)
            self.assertEqual(result, expected)

        # 9100
        index = pd.DatetimeIndex(['2014-12-01 03:32:39.987000-08:00',
                                  '2014-12-01 04:12:34.987000-08:00'])
        for i, ts in enumerate(index):
            result = ts
            expected = index[i]
            self.assertEqual(result._repr_base, expected._repr_base)
            self.assertEqual(result, expected)

    def test_misc_coverage(self):
        rng = date_range('1/1/2000', periods=5)
        result = rng.groupby(rng.day)
        tm.assertIsInstance(list(result.values())[0][0], Timestamp)

        idx = DatetimeIndex(['2000-01-03', '2000-01-01', '2000-01-02'])
        self.assertFalse(idx.equals(list(idx)))

        non_datetime = Index(list('abc'))
        self.assertFalse(idx.equals(list(non_datetime)))

    def test_union_coverage(self):
        idx = DatetimeIndex(['2000-01-03', '2000-01-01', '2000-01-02'])
        ordered = DatetimeIndex(idx.sort_values(), freq='infer')
        result = ordered.union(idx)
        tm.assert_index_equal(result, ordered)

        result = ordered[:0].union(ordered)
        tm.assert_index_equal(result, ordered)
        self.assertEqual(result.freq, ordered.freq)

    def test_union_bug_1730(self):
        rng_a = date_range('1/1/2012', periods=4, freq='3H')
        rng_b = date_range('1/1/2012', periods=4, freq='4H')

        result = rng_a.union(rng_b)
        exp = DatetimeIndex(sorted(set(list(rng_a)) | set(list(rng_b))))
        tm.assert_index_equal(result, exp)

    def test_union_bug_1745(self):
        left = DatetimeIndex(['2012-05-11 15:19:49.695000'])
        right = DatetimeIndex(['2012-05-29 13:04:21.322000',
                               '2012-05-11 15:27:24.873000',
                               '2012-05-11 15:31:05.350000'])

        result = left.union(right)
        exp = DatetimeIndex(sorted(set(list(left)) | set(list(right))))
        tm.assert_index_equal(result, exp)

    def test_union_bug_4564(self):
        from pandas import DateOffset
        left = date_range("2013-01-01", "2013-02-01")
        right = left + DateOffset(minutes=15)

        result = left.union(right)
        exp = DatetimeIndex(sorted(set(list(left)) | set(list(right))))
        tm.assert_index_equal(result, exp)

    def test_union_freq_both_none(self):
        # GH11086
        expected = bdate_range('20150101', periods=10)
        expected.freq = None

        result = expected.union(expected)
        tm.assert_index_equal(result, expected)
        self.assertIsNone(result.freq)

    def test_union_dataframe_index(self):
        rng1 = date_range('1/1/1999', '1/1/2012', freq='MS')
        s1 = Series(np.random.randn(len(rng1)), rng1)

        rng2 = date_range('1/1/1980', '12/1/2001', freq='MS')
        s2 = Series(np.random.randn(len(rng2)), rng2)
        df = DataFrame({'s1': s1, 's2': s2})

        exp = pd.date_range('1/1/1980', '1/1/2012', freq='MS')
        tm.assert_index_equal(df.index, exp)

    def test_intersection_bug_1708(self):
        from pandas import DateOffset
        index_1 = date_range('1/1/2012', periods=4, freq='12H')
        index_2 = index_1 + DateOffset(hours=1)

        result = index_1 & index_2
        self.assertEqual(len(result), 0)

    def test_intersection(self):
        # GH 4690 (with tz)
        for tz in [None, 'Asia/Tokyo', 'US/Eastern', 'dateutil/US/Pacific']:
            base = date_range('6/1/2000', '6/30/2000', freq='D', name='idx')

            # if target has the same name, it is preserved
            rng2 = date_range('5/15/2000', '6/20/2000', freq='D', name='idx')
            expected2 = date_range('6/1/2000', '6/20/2000', freq='D',
                                   name='idx')

            # if target name is different, it will be reset
            rng3 = date_range('5/15/2000', '6/20/2000', freq='D', name='other')
            expected3 = date_range('6/1/2000', '6/20/2000', freq='D',
                                   name=None)

            rng4 = date_range('7/1/2000', '7/31/2000', freq='D', name='idx')
            expected4 = DatetimeIndex([], name='idx')

            for (rng, expected) in [(rng2, expected2), (rng3, expected3),
                                    (rng4, expected4)]:
                result = base.intersection(rng)
                tm.assert_index_equal(result, expected)
                self.assertEqual(result.name, expected.name)
                self.assertEqual(result.freq, expected.freq)
                self.assertEqual(result.tz, expected.tz)

            # non-monotonic
            base = DatetimeIndex(['2011-01-05', '2011-01-04',
                                  '2011-01-02', '2011-01-03'],
                                 tz=tz, name='idx')

            rng2 = DatetimeIndex(['2011-01-04', '2011-01-02',
                                  '2011-02-02', '2011-02-03'],
                                 tz=tz, name='idx')
            expected2 = DatetimeIndex(
                ['2011-01-04', '2011-01-02'], tz=tz, name='idx')

            rng3 = DatetimeIndex(['2011-01-04', '2011-01-02',
                                  '2011-02-02', '2011-02-03'],
                                 tz=tz, name='other')
            expected3 = DatetimeIndex(
                ['2011-01-04', '2011-01-02'], tz=tz, name=None)

            # GH 7880
            rng4 = date_range('7/1/2000', '7/31/2000', freq='D', tz=tz,
                              name='idx')
            expected4 = DatetimeIndex([], tz=tz, name='idx')

            for (rng, expected) in [(rng2, expected2), (rng3, expected3),
                                    (rng4, expected4)]:
                result = base.intersection(rng)
                tm.assert_index_equal(result, expected)
                self.assertEqual(result.name, expected.name)
                self.assertIsNone(result.freq)
                self.assertEqual(result.tz, expected.tz)

        # empty same freq GH2129
        rng = date_range('6/1/2000', '6/15/2000', freq='T')
        result = rng[0:0].intersection(rng)
        self.assertEqual(len(result), 0)

        result = rng.intersection(rng[0:0])
        self.assertEqual(len(result), 0)

    def test_string_index_series_name_converted(self):
        # #1644
        df = DataFrame(np.random.randn(10, 4),
                       index=date_range('1/1/2000', periods=10))

        result = df.loc['1/3/2000']
        self.assertEqual(result.name, df.index[2])

        result = df.T['1/3/2000']
        self.assertEqual(result.name, df.index[2])

    # GH 10699
    def test_datetime64_with_DateOffset(self):
        for klass, assert_func in zip([Series, DatetimeIndex],
                                      [self.assert_series_equal,
                                       tm.assert_index_equal]):
            s = klass(date_range('2000-01-01', '2000-01-31'), name='a')
            result = s + pd.DateOffset(years=1)
            result2 = pd.DateOffset(years=1) + s
            exp = klass(date_range('2001-01-01', '2001-01-31'), name='a')
            assert_func(result, exp)
            assert_func(result2, exp)

            result = s - pd.DateOffset(years=1)
            exp = klass(date_range('1999-01-01', '1999-01-31'), name='a')
            assert_func(result, exp)

            s = klass([Timestamp('2000-01-15 00:15:00', tz='US/Central'),
                       pd.Timestamp('2000-02-15', tz='US/Central')], name='a')
            result = s + pd.offsets.Day()
            result2 = pd.offsets.Day() + s
            exp = klass([Timestamp('2000-01-16 00:15:00', tz='US/Central'),
                         Timestamp('2000-02-16', tz='US/Central')], name='a')
            assert_func(result, exp)
            assert_func(result2, exp)

            s = klass([Timestamp('2000-01-15 00:15:00', tz='US/Central'),
                       pd.Timestamp('2000-02-15', tz='US/Central')], name='a')
            result = s + pd.offsets.MonthEnd()
            result2 = pd.offsets.MonthEnd() + s
            exp = klass([Timestamp('2000-01-31 00:15:00', tz='US/Central'),
                         Timestamp('2000-02-29', tz='US/Central')], name='a')
            assert_func(result, exp)
            assert_func(result2, exp)

            # array of offsets - valid for Series only
            if klass is Series:
                with tm.assert_produces_warning(PerformanceWarning):
                    s = klass([Timestamp('2000-1-1'), Timestamp('2000-2-1')])
                    result = s + Series([pd.offsets.DateOffset(years=1),
                                         pd.offsets.MonthEnd()])
                    exp = klass([Timestamp('2001-1-1'), Timestamp('2000-2-29')
                                 ])
                    assert_func(result, exp)

                    # same offset
                    result = s + Series([pd.offsets.DateOffset(years=1),
                                         pd.offsets.DateOffset(years=1)])
                    exp = klass([Timestamp('2001-1-1'), Timestamp('2001-2-1')])
                    assert_func(result, exp)

            s = klass([Timestamp('2000-01-05 00:15:00'),
                       Timestamp('2000-01-31 00:23:00'),
                       Timestamp('2000-01-01'),
                       Timestamp('2000-03-31'),
                       Timestamp('2000-02-29'),
                       Timestamp('2000-12-31'),
                       Timestamp('2000-05-15'),
                       Timestamp('2001-06-15')])

            # DateOffset relativedelta fastpath
            relative_kwargs = [('years', 2), ('months', 5), ('days', 3),
                               ('hours', 5), ('minutes', 10), ('seconds', 2),
                               ('microseconds', 5)]
            for i, kwd in enumerate(relative_kwargs):
                op = pd.DateOffset(**dict([kwd]))
                assert_func(klass([x + op for x in s]), s + op)
                assert_func(klass([x - op for x in s]), s - op)
                op = pd.DateOffset(**dict(relative_kwargs[:i + 1]))
                assert_func(klass([x + op for x in s]), s + op)
                assert_func(klass([x - op for x in s]), s - op)

            # assert these are equal on a piecewise basis
            offsets = ['YearBegin', ('YearBegin', {'month': 5}), 'YearEnd',
                       ('YearEnd', {'month': 5}), 'MonthBegin', 'MonthEnd',
                       'SemiMonthEnd', 'SemiMonthBegin',
                       'Week', ('Week', {
                           'weekday': 3
                       }), 'BusinessDay', 'BDay', 'QuarterEnd', 'QuarterBegin',
                       'CustomBusinessDay', 'CDay', 'CBMonthEnd',
                       'CBMonthBegin', 'BMonthBegin', 'BMonthEnd',
                       'BusinessHour', 'BYearBegin', 'BYearEnd',
                       'BQuarterBegin', ('LastWeekOfMonth', {
                           'weekday': 2
                       }), ('FY5253Quarter', {'qtr_with_extra_week': 1,
                                              'startingMonth': 1,
                                              'weekday': 2,
                                              'variation': 'nearest'}),
                       ('FY5253', {'weekday': 0,
                                   'startingMonth': 2,
                                   'variation':
                                   'nearest'}), ('WeekOfMonth', {'weekday': 2,
                                                                 'week': 2}),
                       'Easter', ('DateOffset', {'day': 4}),
                       ('DateOffset', {'month': 5})]

            with warnings.catch_warnings(record=True):
                for normalize in (True, False):
                    for do in offsets:
                        if isinstance(do, tuple):
                            do, kwargs = do
                        else:
                            do = do
                            kwargs = {}

                        for n in [0, 5]:
                            if (do in ['WeekOfMonth', 'LastWeekOfMonth',
                                       'FY5253Quarter', 'FY5253'] and n == 0):
                                continue
                            op = getattr(pd.offsets, do)(n,
                                                         normalize=normalize,
                                                         **kwargs)
                            assert_func(klass([x + op for x in s]), s + op)
                            assert_func(klass([x - op for x in s]), s - op)
                            assert_func(klass([op + x for x in s]), op + s)

    def test_overflow_offset(self):
        # xref https://github.com/statsmodels/statsmodels/issues/3374
        # ends up multiplying really large numbers which overflow

        t = Timestamp('2017-01-13 00:00:00', freq='D')
        offset = 20169940 * pd.offsets.Day(1)

        def f():
            t + offset
        self.assertRaises(OverflowError, f)

        def f():
            offset + t
        self.assertRaises(OverflowError, f)

        def f():
            t - offset
        self.assertRaises(OverflowError, f)

    def test_get_duplicates(self):
        idx = DatetimeIndex(['2000-01-01', '2000-01-02', '2000-01-02',
                             '2000-01-03', '2000-01-03', '2000-01-04'])

        result = idx.get_duplicates()
        ex = DatetimeIndex(['2000-01-02', '2000-01-03'])
        tm.assert_index_equal(result, ex)

    def test_argmin_argmax(self):
        idx = DatetimeIndex(['2000-01-04', '2000-01-01', '2000-01-02'])
        self.assertEqual(idx.argmin(), 1)
        self.assertEqual(idx.argmax(), 0)

    def test_sort_values(self):
        idx = DatetimeIndex(['2000-01-04', '2000-01-01', '2000-01-02'])

        ordered = idx.sort_values()
        self.assertTrue(ordered.is_monotonic)

        ordered = idx.sort_values(ascending=False)
        self.assertTrue(ordered[::-1].is_monotonic)

        ordered, dexer = idx.sort_values(return_indexer=True)
        self.assertTrue(ordered.is_monotonic)
        self.assert_numpy_array_equal(dexer,
                                      np.array([1, 2, 0], dtype=np.intp))

        ordered, dexer = idx.sort_values(return_indexer=True, ascending=False)
        self.assertTrue(ordered[::-1].is_monotonic)
        self.assert_numpy_array_equal(dexer,
                                      np.array([0, 2, 1], dtype=np.intp))

    def test_round(self):

        # round
        dt = Timestamp('20130101 09:10:11')
        result = dt.round('D')
        expected = Timestamp('20130101')
        self.assertEqual(result, expected)

        dt = Timestamp('20130101 19:10:11')
        result = dt.round('D')
        expected = Timestamp('20130102')
        self.assertEqual(result, expected)

        dt = Timestamp('20130201 12:00:00')
        result = dt.round('D')
        expected = Timestamp('20130202')
        self.assertEqual(result, expected)

        dt = Timestamp('20130104 12:00:00')
        result = dt.round('D')
        expected = Timestamp('20130105')
        self.assertEqual(result, expected)

        dt = Timestamp('20130104 12:32:00')
        result = dt.round('30Min')
        expected = Timestamp('20130104 12:30:00')
        self.assertEqual(result, expected)

        dti = date_range('20130101 09:10:11', periods=5)
        result = dti.round('D')
        expected = date_range('20130101', periods=5)
        tm.assert_index_equal(result, expected)

        # floor
        dt = Timestamp('20130101 09:10:11')
        result = dt.floor('D')
        expected = Timestamp('20130101')
        self.assertEqual(result, expected)

        # ceil
        dt = Timestamp('20130101 09:10:11')
        result = dt.ceil('D')
        expected = Timestamp('20130102')
        self.assertEqual(result, expected)

        # round with tz
        dt = Timestamp('20130101 09:10:11', tz='US/Eastern')
        result = dt.round('D')
        expected = Timestamp('20130101', tz='US/Eastern')
        self.assertEqual(result, expected)

        dt = Timestamp('20130101 09:10:11', tz='US/Eastern')
        result = dt.round('s')
        self.assertEqual(result, dt)

        dti = date_range('20130101 09:10:11',
                         periods=5).tz_localize('UTC').tz_convert('US/Eastern')
        result = dti.round('D')
        expected = date_range('20130101', periods=5).tz_localize('US/Eastern')
        tm.assert_index_equal(result, expected)

        result = dti.round('s')
        tm.assert_index_equal(result, dti)

        # invalid
        for freq in ['Y', 'M', 'foobar']:
            self.assertRaises(ValueError, lambda: dti.round(freq))

    def test_insert(self):
        idx = DatetimeIndex(
            ['2000-01-04', '2000-01-01', '2000-01-02'], name='idx')

        result = idx.insert(2, datetime(2000, 1, 5))
        exp = DatetimeIndex(['2000-01-04', '2000-01-01', '2000-01-05',
                             '2000-01-02'], name='idx')
        tm.assert_index_equal(result, exp)

        # insertion of non-datetime should coerce to object index
        result = idx.insert(1, 'inserted')
        expected = Index([datetime(2000, 1, 4), 'inserted',
                          datetime(2000, 1, 1),
                          datetime(2000, 1, 2)], name='idx')
        self.assertNotIsInstance(result, DatetimeIndex)
        tm.assert_index_equal(result, expected)
        self.assertEqual(result.name, expected.name)

        idx = date_range('1/1/2000', periods=3, freq='M', name='idx')

        # preserve freq
        expected_0 = DatetimeIndex(['1999-12-31', '2000-01-31', '2000-02-29',
                                    '2000-03-31'], name='idx', freq='M')
        expected_3 = DatetimeIndex(['2000-01-31', '2000-02-29', '2000-03-31',
                                    '2000-04-30'], name='idx', freq='M')

        # reset freq to None
        expected_1_nofreq = DatetimeIndex(['2000-01-31', '2000-01-31',
                                           '2000-02-29',
                                           '2000-03-31'], name='idx',
                                          freq=None)
        expected_3_nofreq = DatetimeIndex(['2000-01-31', '2000-02-29',
                                           '2000-03-31',
                                           '2000-01-02'], name='idx',
                                          freq=None)

        cases = [(0, datetime(1999, 12, 31), expected_0),
                 (-3, datetime(1999, 12, 31), expected_0),
                 (3, datetime(2000, 4, 30), expected_3),
                 (1, datetime(2000, 1, 31), expected_1_nofreq),
                 (3, datetime(2000, 1, 2), expected_3_nofreq)]

        for n, d, expected in cases:
            result = idx.insert(n, d)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)

        # reset freq to None
        result = idx.insert(3, datetime(2000, 1, 2))
        expected = DatetimeIndex(['2000-01-31', '2000-02-29', '2000-03-31',
                                  '2000-01-02'], name='idx', freq=None)
        tm.assert_index_equal(result, expected)
        self.assertEqual(result.name, expected.name)
        self.assertTrue(result.freq is None)

        # GH 7299
        tm._skip_if_no_pytz()
        import pytz

        idx = date_range('1/1/2000', periods=3, freq='D', tz='Asia/Tokyo',
                         name='idx')
        with tm.assertRaises(ValueError):
            result = idx.insert(3, pd.Timestamp('2000-01-04'))
        with tm.assertRaises(ValueError):
            result = idx.insert(3, datetime(2000, 1, 4))
        with tm.assertRaises(ValueError):
            result = idx.insert(3, pd.Timestamp('2000-01-04', tz='US/Eastern'))
        with tm.assertRaises(ValueError):
            result = idx.insert(3,
                                datetime(2000, 1, 4,
                                         tzinfo=pytz.timezone('US/Eastern')))

        for tz in ['US/Pacific', 'Asia/Singapore']:
            idx = date_range('1/1/2000 09:00', periods=6, freq='H', tz=tz,
                             name='idx')
            # preserve freq
            expected = date_range('1/1/2000 09:00', periods=7, freq='H', tz=tz,
                                  name='idx')
            for d in [pd.Timestamp('2000-01-01 15:00', tz=tz),
                      pytz.timezone(tz).localize(datetime(2000, 1, 1, 15))]:

                result = idx.insert(6, d)
                tm.assert_index_equal(result, expected)
                self.assertEqual(result.name, expected.name)
                self.assertEqual(result.freq, expected.freq)
                self.assertEqual(result.tz, expected.tz)

            expected = DatetimeIndex(['2000-01-01 09:00', '2000-01-01 10:00',
                                      '2000-01-01 11:00',
                                      '2000-01-01 12:00', '2000-01-01 13:00',
                                      '2000-01-01 14:00',
                                      '2000-01-01 10:00'], name='idx',
                                     tz=tz, freq=None)
            # reset freq to None
            for d in [pd.Timestamp('2000-01-01 10:00', tz=tz),
                      pytz.timezone(tz).localize(datetime(2000, 1, 1, 10))]:
                result = idx.insert(6, d)
                tm.assert_index_equal(result, expected)
                self.assertEqual(result.name, expected.name)
                self.assertTrue(result.freq is None)
                self.assertEqual(result.tz, expected.tz)

    def test_delete(self):
        idx = date_range(start='2000-01-01', periods=5, freq='M', name='idx')

        # prserve freq
        expected_0 = date_range(start='2000-02-01', periods=4, freq='M',
                                name='idx')
        expected_4 = date_range(start='2000-01-01', periods=4, freq='M',
                                name='idx')

        # reset freq to None
        expected_1 = DatetimeIndex(['2000-01-31', '2000-03-31', '2000-04-30',
                                    '2000-05-31'], freq=None, name='idx')

        cases = {0: expected_0,
                 -5: expected_0,
                 -1: expected_4,
                 4: expected_4,
                 1: expected_1}
        for n, expected in compat.iteritems(cases):
            result = idx.delete(n)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)

        with tm.assertRaises((IndexError, ValueError)):
            # either depeidnig on numpy version
            result = idx.delete(5)

        for tz in [None, 'Asia/Tokyo', 'US/Pacific']:
            idx = date_range(start='2000-01-01 09:00', periods=10, freq='H',
                             name='idx', tz=tz)

            expected = date_range(start='2000-01-01 10:00', periods=9,
                                  freq='H', name='idx', tz=tz)
            result = idx.delete(0)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freqstr, 'H')
            self.assertEqual(result.tz, expected.tz)

            expected = date_range(start='2000-01-01 09:00', periods=9,
                                  freq='H', name='idx', tz=tz)
            result = idx.delete(-1)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freqstr, 'H')
            self.assertEqual(result.tz, expected.tz)

    def test_delete_slice(self):
        idx = date_range(start='2000-01-01', periods=10, freq='D', name='idx')

        # prserve freq
        expected_0_2 = date_range(start='2000-01-04', periods=7, freq='D',
                                  name='idx')
        expected_7_9 = date_range(start='2000-01-01', periods=7, freq='D',
                                  name='idx')

        # reset freq to None
        expected_3_5 = DatetimeIndex(['2000-01-01', '2000-01-02', '2000-01-03',
                                      '2000-01-07', '2000-01-08', '2000-01-09',
                                      '2000-01-10'], freq=None, name='idx')

        cases = {(0, 1, 2): expected_0_2,
                 (7, 8, 9): expected_7_9,
                 (3, 4, 5): expected_3_5}
        for n, expected in compat.iteritems(cases):
            result = idx.delete(n)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)

            result = idx.delete(slice(n[0], n[-1] + 1))
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)

        for tz in [None, 'Asia/Tokyo', 'US/Pacific']:
            ts = pd.Series(1, index=pd.date_range(
                '2000-01-01 09:00', periods=10, freq='H', name='idx', tz=tz))
            # preserve freq
            result = ts.drop(ts.index[:5]).index
            expected = pd.date_range('2000-01-01 14:00', periods=5, freq='H',
                                     name='idx', tz=tz)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)
            self.assertEqual(result.tz, expected.tz)

            # reset freq to None
            result = ts.drop(ts.index[[1, 3, 5, 7, 9]]).index
            expected = DatetimeIndex(['2000-01-01 09:00', '2000-01-01 11:00',
                                      '2000-01-01 13:00',
                                      '2000-01-01 15:00', '2000-01-01 17:00'],
                                     freq=None, name='idx', tz=tz)
            tm.assert_index_equal(result, expected)
            self.assertEqual(result.name, expected.name)
            self.assertEqual(result.freq, expected.freq)
            self.assertEqual(result.tz, expected.tz)

    def test_take(self):
        dates = [datetime(2010, 1, 1, 14), datetime(2010, 1, 1, 15),
                 datetime(2010, 1, 1, 17), datetime(2010, 1, 1, 21)]

        for tz in [None, 'US/Eastern', 'Asia/Tokyo']:
            idx = DatetimeIndex(start='2010-01-01 09:00',
                                end='2010-02-01 09:00', freq='H', tz=tz,
                                name='idx')
            expected = DatetimeIndex(dates, freq=None, name='idx', tz=tz)

            taken1 = idx.take([5, 6, 8, 12])
            taken2 = idx[[5, 6, 8, 12]]

            for taken in [taken1, taken2]:
                tm.assert_index_equal(taken, expected)
                tm.assertIsInstance(taken, DatetimeIndex)
                self.assertIsNone(taken.freq)
                self.assertEqual(taken.tz, expected.tz)
                self.assertEqual(taken.name, expected.name)

    def test_take_fill_value(self):
        # GH 12631
        idx = pd.DatetimeIndex(['2011-01-01', '2011-02-01', '2011-03-01'],
                               name='xxx')
        result = idx.take(np.array([1, 0, -1]))
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', '2011-03-01'],
                                    name='xxx')
        tm.assert_index_equal(result, expected)

        # fill_value
        result = idx.take(np.array([1, 0, -1]), fill_value=True)
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', 'NaT'],
                                    name='xxx')
        tm.assert_index_equal(result, expected)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False,
                          fill_value=True)
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', '2011-03-01'],
                                    name='xxx')
        tm.assert_index_equal(result, expected)

        msg = ('When allow_fill=True and fill_value is not None, '
               'all indices must be >= -1')
        with tm.assertRaisesRegexp(ValueError, msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with tm.assertRaisesRegexp(ValueError, msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        with tm.assertRaises(IndexError):
            idx.take(np.array([1, -5]))

    def test_take_fill_value_with_timezone(self):
        idx = pd.DatetimeIndex(['2011-01-01', '2011-02-01', '2011-03-01'],
                               name='xxx', tz='US/Eastern')
        result = idx.take(np.array([1, 0, -1]))
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', '2011-03-01'],
                                    name='xxx', tz='US/Eastern')
        tm.assert_index_equal(result, expected)

        # fill_value
        result = idx.take(np.array([1, 0, -1]), fill_value=True)
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', 'NaT'],
                                    name='xxx', tz='US/Eastern')
        tm.assert_index_equal(result, expected)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False,
                          fill_value=True)
        expected = pd.DatetimeIndex(['2011-02-01', '2011-01-01', '2011-03-01'],
                                    name='xxx', tz='US/Eastern')
        tm.assert_index_equal(result, expected)

        msg = ('When allow_fill=True and fill_value is not None, '
               'all indices must be >= -1')
        with tm.assertRaisesRegexp(ValueError, msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with tm.assertRaisesRegexp(ValueError, msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        with tm.assertRaises(IndexError):
            idx.take(np.array([1, -5]))

    def test_map_bug_1677(self):
        index = DatetimeIndex(['2012-04-25 09:30:00.393000'])
        f = index.asof

        result = index.map(f)
        expected = Index([f(index[0])])
        tm.assert_index_equal(result, expected)

    def test_groupby_function_tuple_1677(self):
        df = DataFrame(np.random.rand(100),
                       index=date_range("1/1/2000", periods=100))
        monthly_group = df.groupby(lambda x: (x.year, x.month))

        result = monthly_group.mean()
        tm.assertIsInstance(result.index[0], tuple)

    def test_append_numpy_bug_1681(self):
        # another datetime64 bug
        dr = date_range('2011/1/1', '2012/1/1', freq='W-FRI')
        a = DataFrame()
        c = DataFrame({'A': 'foo', 'B': dr}, index=dr)

        result = a.append(c)
        self.assertTrue((result['B'] == dr).all())

    def test_isin(self):
        index = tm.makeDateIndex(4)
        result = index.isin(index)
        self.assertTrue(result.all())

        result = index.isin(list(index))
        self.assertTrue(result.all())

        assert_almost_equal(index.isin([index[2], 5]),
                            np.array([False, False, True, False]))

    def test_union(self):
        i1 = Int64Index(np.arange(0, 20, 2))
        i2 = Int64Index(np.arange(10, 30, 2))
        result = i1.union(i2)
        expected = Int64Index(np.arange(0, 30, 2))
        tm.assert_index_equal(result, expected)

    def test_union_with_DatetimeIndex(self):
        i1 = Int64Index(np.arange(0, 20, 2))
        i2 = DatetimeIndex(start='2012-01-03 00:00:00', periods=10, freq='D')
        i1.union(i2)  # Works
        i2.union(i1)  # Fails with "AttributeError: can't set attribute"

    def test_time(self):
        rng = pd.date_range('1/1/2000', freq='12min', periods=10)
        result = pd.Index(rng).time
        expected = [t.time() for t in rng]
        self.assertTrue((result == expected).all())

    def test_date(self):
        rng = pd.date_range('1/1/2000', freq='12H', periods=10)
        result = pd.Index(rng).date
        expected = [t.date() for t in rng]
        self.assertTrue((result == expected).all())

    def test_does_not_convert_mixed_integer(self):
        df = tm.makeCustomDataframe(10, 10,
                                    data_gen_f=lambda *args, **kwargs: randn(),
                                    r_idx_type='i', c_idx_type='dt')
        cols = df.columns.join(df.index, how='outer')
        joined = cols.join(df.columns)
        self.assertEqual(cols.dtype, np.dtype('O'))
        self.assertEqual(cols.dtype, joined.dtype)
        tm.assert_numpy_array_equal(cols.values, joined.values)

    def test_slice_keeps_name(self):
        # GH4226
        st = pd.Timestamp('2013-07-01 00:00:00', tz='America/Los_Angeles')
        et = pd.Timestamp('2013-07-02 00:00:00', tz='America/Los_Angeles')
        dr = pd.date_range(st, et, freq='H', name='timebucket')
        self.assertEqual(dr[1:].name, dr.name)

    def test_join_self(self):
        index = date_range('1/1/2000', periods=10)
        kinds = 'outer', 'inner', 'left', 'right'
        for kind in kinds:
            joined = index.join(index, how=kind)
            self.assertIs(index, joined)

    def assert_index_parameters(self, index):
        assert index.freq == '40960N'
        assert index.inferred_freq == '40960N'

    def test_ns_index(self):
        nsamples = 400
        ns = int(1e9 / 24414)
        dtstart = np.datetime64('2012-09-20T00:00:00')

        dt = dtstart + np.arange(nsamples) * np.timedelta64(ns, 'ns')
        freq = ns * offsets.Nano()
        index = pd.DatetimeIndex(dt, freq=freq, name='time')
        self.assert_index_parameters(index)

        new_index = pd.DatetimeIndex(start=index[0], end=index[-1],
                                     freq=index.freq)
        self.assert_index_parameters(new_index)

    def test_join_with_period_index(self):
        df = tm.makeCustomDataframe(
            10, 10, data_gen_f=lambda *args: np.random.randint(2),
            c_idx_type='p', r_idx_type='dt')
        s = df.iloc[:5, 0]
        joins = 'left', 'right', 'inner', 'outer'

        for join in joins:
            with tm.assertRaisesRegexp(ValueError, 'can only call with other '
                                       'PeriodIndex-ed objects'):
                df.columns.join(s.index, how=join)

    def test_factorize(self):
        idx1 = DatetimeIndex(['2014-01', '2014-01', '2014-02', '2014-02',
                              '2014-03', '2014-03'])

        exp_arr = np.array([0, 0, 1, 1, 2, 2], dtype=np.intp)
        exp_idx = DatetimeIndex(['2014-01', '2014-02', '2014-03'])

        arr, idx = idx1.factorize()
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, exp_idx)

        arr, idx = idx1.factorize(sort=True)
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, exp_idx)

        # tz must be preserved
        idx1 = idx1.tz_localize('Asia/Tokyo')
        exp_idx = exp_idx.tz_localize('Asia/Tokyo')

        arr, idx = idx1.factorize()
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, exp_idx)

        idx2 = pd.DatetimeIndex(['2014-03', '2014-03', '2014-02', '2014-01',
                                 '2014-03', '2014-01'])

        exp_arr = np.array([2, 2, 1, 0, 2, 0], dtype=np.intp)
        exp_idx = DatetimeIndex(['2014-01', '2014-02', '2014-03'])
        arr, idx = idx2.factorize(sort=True)
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, exp_idx)

        exp_arr = np.array([0, 0, 1, 2, 0, 2], dtype=np.intp)
        exp_idx = DatetimeIndex(['2014-03', '2014-02', '2014-01'])
        arr, idx = idx2.factorize()
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, exp_idx)

        # freq must be preserved
        idx3 = date_range('2000-01', periods=4, freq='M', tz='Asia/Tokyo')
        exp_arr = np.array([0, 1, 2, 3], dtype=np.intp)
        arr, idx = idx3.factorize()
        self.assert_numpy_array_equal(arr, exp_arr)
        tm.assert_index_equal(idx, idx3)

    def test_factorize_tz(self):
        # GH 13750
        for tz in [None, 'UTC', 'US/Eastern', 'Asia/Tokyo']:
            base = pd.date_range('2016-11-05', freq='H', periods=100, tz=tz)
            idx = base.repeat(5)

            exp_arr = np.arange(100, dtype=np.intp).repeat(5)

            for obj in [idx, pd.Series(idx)]:
                arr, res = obj.factorize()
                self.assert_numpy_array_equal(arr, exp_arr)
                tm.assert_index_equal(res, base)

    def test_factorize_dst(self):
        # GH 13750
        idx = pd.date_range('2016-11-06', freq='H', periods=12,
                            tz='US/Eastern')

        for obj in [idx, pd.Series(idx)]:
            arr, res = obj.factorize()
            self.assert_numpy_array_equal(arr, np.arange(12, dtype=np.intp))
            tm.assert_index_equal(res, idx)

        idx = pd.date_range('2016-06-13', freq='H', periods=12,
                            tz='US/Eastern')

        for obj in [idx, pd.Series(idx)]:
            arr, res = obj.factorize()
            self.assert_numpy_array_equal(arr, np.arange(12, dtype=np.intp))
            tm.assert_index_equal(res, idx)

    def test_slice_with_negative_step(self):
        ts = Series(np.arange(20),
                    date_range('2014-01-01', periods=20, freq='MS'))
        SLC = pd.IndexSlice

        def assert_slices_equivalent(l_slc, i_slc):
            assert_series_equal(ts[l_slc], ts.iloc[i_slc])
            assert_series_equal(ts.loc[l_slc], ts.iloc[i_slc])
            assert_series_equal(ts.loc[l_slc], ts.iloc[i_slc])

        assert_slices_equivalent(SLC[Timestamp('2014-10-01')::-1], SLC[9::-1])
        assert_slices_equivalent(SLC['2014-10-01'::-1], SLC[9::-1])

        assert_slices_equivalent(SLC[:Timestamp('2014-10-01'):-1], SLC[:8:-1])
        assert_slices_equivalent(SLC[:'2014-10-01':-1], SLC[:8:-1])

        assert_slices_equivalent(SLC['2015-02-01':'2014-10-01':-1],
                                 SLC[13:8:-1])
        assert_slices_equivalent(SLC[Timestamp('2015-02-01'):Timestamp(
            '2014-10-01'):-1], SLC[13:8:-1])
        assert_slices_equivalent(SLC['2015-02-01':Timestamp('2014-10-01'):-1],
                                 SLC[13:8:-1])
        assert_slices_equivalent(SLC[Timestamp('2015-02-01'):'2014-10-01':-1],
                                 SLC[13:8:-1])

        assert_slices_equivalent(SLC['2014-10-01':'2015-02-01':-1], SLC[:0])

    def test_slice_with_zero_step_raises(self):
        ts = Series(np.arange(20),
                    date_range('2014-01-01', periods=20, freq='MS'))
        self.assertRaisesRegexp(ValueError, 'slice step cannot be zero',
                                lambda: ts[::0])
        self.assertRaisesRegexp(ValueError, 'slice step cannot be zero',
                                lambda: ts.loc[::0])
        self.assertRaisesRegexp(ValueError, 'slice step cannot be zero',
                                lambda: ts.loc[::0])

    def test_slice_bounds_empty(self):
        # GH 14354
        empty_idx = DatetimeIndex(freq='1H', periods=0, end='2015')

        right = empty_idx._maybe_cast_slice_bound('2015-01-02', 'right', 'loc')
        exp = Timestamp('2015-01-02 23:59:59.999999999')
        self.assertEqual(right, exp)

        left = empty_idx._maybe_cast_slice_bound('2015-01-02', 'left', 'loc')
        exp = Timestamp('2015-01-02 00:00:00')
        self.assertEqual(left, exp)



class TestDateTimeIndexToJulianDate(tm.TestCase):

    def test_1700(self):
        r1 = Float64Index([2345897.5, 2345898.5, 2345899.5, 2345900.5,
                           2345901.5])
        r2 = date_range(start=Timestamp('1710-10-01'), periods=5,
                        freq='D').to_julian_date()
        self.assertIsInstance(r2, Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_2000(self):
        r1 = Float64Index([2451601.5, 2451602.5, 2451603.5, 2451604.5,
                           2451605.5])
        r2 = date_range(start=Timestamp('2000-02-27'), periods=5,
                        freq='D').to_julian_date()
        self.assertIsInstance(r2, Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_hour(self):
        r1 = Float64Index(
            [2451601.5, 2451601.5416666666666666, 2451601.5833333333333333,
             2451601.625, 2451601.6666666666666666])
        r2 = date_range(start=Timestamp('2000-02-27'), periods=5,
                        freq='H').to_julian_date()
        self.assertIsInstance(r2, Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_minute(self):
        r1 = Float64Index(
            [2451601.5, 2451601.5006944444444444, 2451601.5013888888888888,
             2451601.5020833333333333, 2451601.5027777777777777])
        r2 = date_range(start=Timestamp('2000-02-27'), periods=5,
                        freq='T').to_julian_date()
        self.assertIsInstance(r2, Float64Index)
        tm.assert_index_equal(r1, r2)

    def test_second(self):
        r1 = Float64Index(
            [2451601.5, 2451601.500011574074074, 2451601.5000231481481481,
             2451601.5000347222222222, 2451601.5000462962962962])
        r2 = date_range(start=Timestamp('2000-02-27'), periods=5,
                        freq='S').to_julian_date()
        self.assertIsInstance(r2, Float64Index)
        tm.assert_index_equal(r1, r2)
