import numpy as np
import pytest

from pandas import (
    CategoricalIndex,
    DatetimeIndex,
    Index,
    PeriodIndex,
    TimedeltaIndex,
    isna,
)
import pandas._testing as tm
from pandas.api.types import is_complex_dtype
from pandas.core.api import NumericIndex
from pandas.core.arrays import BooleanArray
from pandas.core.indexes.datetimelike import DatetimeIndexOpsMixin


def test_numpy_ufuncs_out(index):
    result = index == index

    out = np.empty(index.shape, dtype=bool)
    np.equal(index, index, out=out)
    tm.assert_numpy_array_equal(out, result)

    if not index._is_multi:
        # same thing on the ExtensionArray
        out = np.empty(index.shape, dtype=bool)
        np.equal(index.array, index.array, out=out)
        tm.assert_numpy_array_equal(out, result)


@pytest.mark.parametrize(
    "func",
    [
        np.exp,
        np.exp2,
        np.expm1,
        np.log,
        np.log2,
        np.log10,
        np.log1p,
        np.sqrt,
        np.sin,
        np.cos,
        np.tan,
        np.arcsin,
        np.arccos,
        np.arctan,
        np.sinh,
        np.cosh,
        np.tanh,
        np.arcsinh,
        np.arccosh,
        np.arctanh,
        np.deg2rad,
        np.rad2deg,
    ],
    ids=lambda x: x.__name__,
)
def test_numpy_ufuncs_basic(index, func):
    # test ufuncs of numpy, see:
    # https://numpy.org/doc/stable/reference/ufuncs.html

    if isinstance(index, DatetimeIndexOpsMixin):
        with tm.external_error_raised((TypeError, AttributeError)):
            with np.errstate(all="ignore"):
                func(index)
    elif (
        isinstance(index, NumericIndex)
        or (not isinstance(index.dtype, np.dtype) and index.dtype._is_numeric)
        or (index.dtype.kind == "c" and func not in [np.deg2rad, np.rad2deg])
        or index.dtype == bool
    ):
        # coerces to float (e.g. np.sin)
        with np.errstate(all="ignore"):
            result = func(index)
            exp = Index(func(index.values), name=index.name)

        tm.assert_index_equal(result, exp)
        if type(index) is not Index or index.dtype == bool:
            assert type(result) is NumericIndex
            if is_complex_dtype(index):
                assert result.dtype == "complex64"
            elif index.dtype in {
                "bool",
                "int8",
                "int16",
                "uint8",
                "uint16",
                "float16",
                "float32",
            }:
                assert result.dtype == "float32"
            else:
                assert result.dtype == "float64"
        else:
            # e.g. np.exp with Int64 -> Float64
            assert type(result) is Index
    else:
        # raise AttributeError or TypeError
        if len(index) == 0:
            pass
        else:
            with tm.external_error_raised((TypeError, AttributeError)):
                with np.errstate(all="ignore"):
                    func(index)


@pytest.mark.parametrize(
    "func", [np.isfinite, np.isinf, np.isnan, np.signbit], ids=lambda x: x.__name__
)
def test_numpy_ufuncs_other(index, func):
    # test ufuncs of numpy, see:
    # https://numpy.org/doc/stable/reference/ufuncs.html
    if isinstance(index, (DatetimeIndex, TimedeltaIndex)):

        if func in (np.isfinite, np.isinf, np.isnan):
            # numpy 1.18 changed isinf and isnan to not raise on dt64/td64
            result = func(index)
            assert isinstance(result, np.ndarray)

            out = np.empty(index.shape, dtype=bool)
            func(index, out=out)
            tm.assert_numpy_array_equal(out, result)
        else:
            with tm.external_error_raised(TypeError):
                func(index)

    elif isinstance(index, PeriodIndex):
        with tm.external_error_raised(TypeError):
            func(index)

    elif (
        isinstance(index, NumericIndex)
        or (not isinstance(index.dtype, np.dtype) and index.dtype._is_numeric)
        or (index.dtype.kind == "c" and func is not np.signbit)
        or index.dtype == bool
    ):
        # Results in bool array
        result = func(index)
        if not isinstance(index.dtype, np.dtype):
            # e.g. Int64 we expect to get BooleanArray back
            assert isinstance(result, BooleanArray)
        else:
            assert isinstance(result, np.ndarray)

        out = np.empty(index.shape, dtype=bool)
        func(index, out=out)

        if not isinstance(index.dtype, np.dtype):
            tm.assert_numpy_array_equal(out, result._data)
        else:
            tm.assert_numpy_array_equal(out, result)

    else:
        if len(index) == 0:
            pass
        else:
            with tm.external_error_raised(TypeError):
                func(index)


@pytest.mark.parametrize("func", [np.maximum, np.minimum])
def test_numpy_ufuncs_reductions(index, func, request):
    # TODO: overlap with tests.series.test_ufunc.test_reductions
    if len(index) == 0:
        return

    if repr(index.dtype) == "string[pyarrow]":
        mark = pytest.mark.xfail(reason="ArrowStringArray has no min/max")
        request.node.add_marker(mark)

    if isinstance(index, CategoricalIndex) and index.dtype.ordered is False:
        with pytest.raises(TypeError, match="is not ordered for"):
            func.reduce(index)
        return
    else:
        result = func.reduce(index)

    if func is np.maximum:
        expected = index.max(skipna=False)
    else:
        expected = index.min(skipna=False)
        # TODO: do we have cases both with and without NAs?

    assert type(result) is type(expected)
    if isna(result):
        assert isna(expected)
    else:
        assert result == expected


@pytest.mark.parametrize("func", [np.bitwise_and, np.bitwise_or, np.bitwise_xor])
def test_numpy_ufuncs_bitwise(func):
    # https://github.com/pandas-dev/pandas/issues/46769
    idx1 = Index([1, 2, 3, 4], dtype="int64")
    idx2 = Index([3, 4, 5, 6], dtype="int64")

    with tm.assert_produces_warning(None):
        result = func(idx1, idx2)

    expected = Index(func(idx1.values, idx2.values))
    tm.assert_index_equal(result, expected)
