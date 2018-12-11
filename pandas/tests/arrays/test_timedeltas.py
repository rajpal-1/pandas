# -*- coding: utf-8 -*-

import numpy as np
import pytest

import pandas as pd
from pandas.core.arrays import TimedeltaArrayMixin as TimedeltaArray
import pandas.util.testing as tm


class TestTimedeltaArrayConstructor(object):
    def test_non_array_raises(self):
        with pytest.raises(ValueError, match='list'):
            TimedeltaArray([1, 2, 3])

    def test_other_type_raises(self):
        with pytest.raises(ValueError,
                           match="The dtype of 'values' is incorrect"):
            TimedeltaArray(np.array([1, 2, 3], dtype='bool'))

    def test_incorrect_dtype_raises(self):
        with pytest.raises(ValueError, match=".dtype. must be .timedelta64."):
            TimedeltaArray(np.array([1, 2, 3], dtype='i8'), dtype='category')

        with pytest.raises(ValueError, match=".dtype. must be .timedelta64."):
            TimedeltaArray(np.array([1, 2, 3], dtype='i8'),
                           dtype=np.dtype(int))

    def test_freq_infer_raises(self):
        with pytest.raises(ValueError, match='Frequency inference'):
            TimedeltaArray(np.array([1, 2, 3]), freq="infer")


class TestTimedeltaArray(object):
    def test_from_sequence_dtype(self):
        msg = r"Only timedelta64\[ns\] dtype is valid"
        with pytest.raises(ValueError, match=msg):
            TimedeltaArray._from_sequence([], dtype=object)

    def test_abs(self):
        vals = np.array([-3600 * 10**9, 'NaT', 7200 * 10**9], dtype='m8[ns]')
        arr = TimedeltaArray(vals)

        evals = np.array([3600 * 10**9, 'NaT', 7200 * 10**9], dtype='m8[ns]')
        expected = TimedeltaArray(evals)

        result = abs(arr)
        tm.assert_timedelta_array_equal(result, expected)

    def test_neg(self):
        vals = np.array([-3600 * 10**9, 'NaT', 7200 * 10**9], dtype='m8[ns]')
        arr = TimedeltaArray(vals)

        evals = np.array([3600 * 10**9, 'NaT', -7200 * 10**9], dtype='m8[ns]')
        expected = TimedeltaArray(evals)

        result = -arr
        tm.assert_timedelta_array_equal(result, expected)

    def test_neg_freq(self):
        tdi = pd.timedelta_range('2 Days', periods=4, freq='H')
        arr = TimedeltaArray(tdi, freq=tdi.freq)

        expected = TimedeltaArray(-tdi._data, freq=-tdi.freq)

        result = -arr
        tm.assert_timedelta_array_equal(result, expected)
