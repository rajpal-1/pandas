import operator

import numpy as np
import pytest

from pandas.compat import np_version_under1p20

import pandas as pd
import pandas._testing as tm
from pandas.core import ops
from pandas.core.arrays.sparse import SparseArray, SparseDtype


@pytest.fixture(params=["integer", "block"])
def kind(request):
    """kind kwarg to pass to SparseArray/SparseSeries"""
    return request.param


@pytest.fixture(params=[True, False])
def mix(request):
    # whether to operate op(sparse, dense) instead of op(sparse, sparse)
    return request.param


class TestSparseArrayArithmetics:

    _base = np.array
    _klass = SparseArray

    def _assert(self, a, b):
        tm.assert_numpy_array_equal(a, b)

    def _check_numeric_ops(self, a, b, a_dense, b_dense, mix, op):
        with np.errstate(invalid="ignore", divide="ignore"):
            if mix:
                result = op(a, b_dense).to_dense()
            else:
                result = op(a, b).to_dense()

            if op in [operator.truediv, ops.rtruediv]:
                # pandas uses future division
                expected = op(a_dense * 1.0, b_dense)
            else:
                expected = op(a_dense, b_dense)

            if op in [operator.floordiv, ops.rfloordiv]:
                # Series sets 1//0 to np.inf, which SparseArray does not do (yet)
                mask = np.isinf(expected)
                if mask.any():
                    expected[mask] = np.nan

            self._assert(result, expected)

    def _check_bool_result(self, res):
        assert isinstance(res, self._klass)
        assert isinstance(res.dtype, SparseDtype)
        assert res.dtype.subtype == np.bool_
        assert isinstance(res.fill_value, bool)

    def _check_comparison_ops(self, a, b, a_dense, b_dense):
        with np.errstate(invalid="ignore"):
            # Unfortunately, trying to wrap the computation of each expected
            # value is with np.errstate() is too tedious.
            #
            # sparse & sparse
            self._check_bool_result(a == b)
            self._assert((a == b).to_dense(), a_dense == b_dense)

            self._check_bool_result(a != b)
            self._assert((a != b).to_dense(), a_dense != b_dense)

            self._check_bool_result(a >= b)
            self._assert((a >= b).to_dense(), a_dense >= b_dense)

            self._check_bool_result(a <= b)
            self._assert((a <= b).to_dense(), a_dense <= b_dense)

            self._check_bool_result(a > b)
            self._assert((a > b).to_dense(), a_dense > b_dense)

            self._check_bool_result(a < b)
            self._assert((a < b).to_dense(), a_dense < b_dense)

            # sparse & dense
            self._check_bool_result(a == b_dense)
            self._assert((a == b_dense).to_dense(), a_dense == b_dense)

            self._check_bool_result(a != b_dense)
            self._assert((a != b_dense).to_dense(), a_dense != b_dense)

            self._check_bool_result(a >= b_dense)
            self._assert((a >= b_dense).to_dense(), a_dense >= b_dense)

            self._check_bool_result(a <= b_dense)
            self._assert((a <= b_dense).to_dense(), a_dense <= b_dense)

            self._check_bool_result(a > b_dense)
            self._assert((a > b_dense).to_dense(), a_dense > b_dense)

            self._check_bool_result(a < b_dense)
            self._assert((a < b_dense).to_dense(), a_dense < b_dense)

    def _check_logical_ops(self, a, b, a_dense, b_dense):
        # sparse & sparse
        self._check_bool_result(a & b)
        self._assert((a & b).to_dense(), a_dense & b_dense)

        self._check_bool_result(a | b)
        self._assert((a | b).to_dense(), a_dense | b_dense)
        # sparse & dense
        self._check_bool_result(a & b_dense)
        self._assert((a & b_dense).to_dense(), a_dense & b_dense)

        self._check_bool_result(a | b_dense)
        self._assert((a | b_dense).to_dense(), a_dense | b_dense)

    @pytest.mark.parametrize("scalar", [0, 1, 3])
    @pytest.mark.parametrize("fill_value", [None, 0, 2])
    def test_float_scalar(
        self, kind, mix, all_arithmetic_functions, fill_value, scalar, request
    ):
        op = all_arithmetic_functions

        if not np_version_under1p20:
            if op in [operator.floordiv, ops.rfloordiv]:
                mark = pytest.mark.xfail(reason="GH#38172")
                request.node.add_marker(mark)

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])

        a = self._klass(values, kind=kind, fill_value=fill_value)
        self._check_numeric_ops(a, scalar, values, scalar, mix, op)

    def test_float_scalar_comparison(self, kind):
        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])

        a = self._klass(values, kind=kind)
        self._check_comparison_ops(a, 1, values, 1)
        self._check_comparison_ops(a, 0, values, 0)
        self._check_comparison_ops(a, 3, values, 3)

        a = self._klass(values, kind=kind, fill_value=0)
        self._check_comparison_ops(a, 1, values, 1)
        self._check_comparison_ops(a, 0, values, 0)
        self._check_comparison_ops(a, 3, values, 3)

        a = self._klass(values, kind=kind, fill_value=2)
        self._check_comparison_ops(a, 1, values, 1)
        self._check_comparison_ops(a, 0, values, 0)
        self._check_comparison_ops(a, 3, values, 3)

    def test_float_same_index_without_nans(
        self, kind, mix, all_arithmetic_functions, request
    ):
        # when sp_index are the same
        op = all_arithmetic_functions

        values = self._base([0.0, 1.0, 2.0, 6.0, 0.0, 0.0, 1.0, 2.0, 1.0, 0.0])
        rvalues = self._base([0.0, 2.0, 3.0, 4.0, 0.0, 0.0, 1.0, 3.0, 2.0, 0.0])

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_float_same_index_with_nans(
        self, kind, mix, all_arithmetic_functions, request
    ):
        # when sp_index are the same
        op = all_arithmetic_functions

        if not np_version_under1p20:
            if op in [operator.floordiv, ops.rfloordiv]:
                mark = pytest.mark.xfail(reason="GH#38172")
                request.node.add_marker(mark)

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([np.nan, 2, 3, 4, np.nan, 0, 1, 3, 2, np.nan])

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_float_same_index_comparison(self, kind):
        # when sp_index are the same
        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([np.nan, 2, 3, 4, np.nan, 0, 1, 3, 2, np.nan])

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        self._check_comparison_ops(a, b, values, rvalues)

        values = self._base([0.0, 1.0, 2.0, 6.0, 0.0, 0.0, 1.0, 2.0, 1.0, 0.0])
        rvalues = self._base([0.0, 2.0, 3.0, 4.0, 0.0, 0.0, 1.0, 3.0, 2.0, 0.0])

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        self._check_comparison_ops(a, b, values, rvalues)

    def test_float_array(self, kind, mix, all_arithmetic_functions):
        op = all_arithmetic_functions

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([2, np.nan, 2, 3, np.nan, 0, 1, 5, 2, np.nan])

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)
        self._check_numeric_ops(a, b * 0, values, rvalues * 0, mix, op)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind=kind, fill_value=1)
        b = self._klass(rvalues, kind=kind, fill_value=2)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_float_array_different_kind(self, mix, all_arithmetic_functions):
        op = all_arithmetic_functions

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([2, np.nan, 2, 3, np.nan, 0, 1, 5, 2, np.nan])

        a = self._klass(values, kind="integer")
        b = self._klass(rvalues, kind="block")
        self._check_numeric_ops(a, b, values, rvalues, mix, op)
        self._check_numeric_ops(a, b * 0, values, rvalues * 0, mix, op)

        a = self._klass(values, kind="integer", fill_value=0)
        b = self._klass(rvalues, kind="block")
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind="integer", fill_value=0)
        b = self._klass(rvalues, kind="block", fill_value=0)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind="integer", fill_value=1)
        b = self._klass(rvalues, kind="block", fill_value=2)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_float_array_comparison(self, kind):
        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([2, np.nan, 2, 3, np.nan, 0, 1, 5, 2, np.nan])

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        self._check_comparison_ops(a, b, values, rvalues)
        self._check_comparison_ops(a, b * 0, values, rvalues * 0)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, kind=kind, fill_value=1)
        b = self._klass(rvalues, kind=kind, fill_value=2)
        self._check_comparison_ops(a, b, values, rvalues)

    def test_int_array(self, kind, mix, all_arithmetic_functions):
        op = all_arithmetic_functions

        # have to specify dtype explicitly until fixing GH 667
        dtype = np.int64

        values = self._base([0, 1, 2, 0, 0, 0, 1, 2, 1, 0], dtype=dtype)
        rvalues = self._base([2, 0, 2, 3, 0, 0, 1, 5, 2, 0], dtype=dtype)

        a = self._klass(values, dtype=dtype, kind=kind)
        assert a.dtype == SparseDtype(dtype)
        b = self._klass(rvalues, dtype=dtype, kind=kind)
        assert b.dtype == SparseDtype(dtype)

        self._check_numeric_ops(a, b, values, rvalues, mix, op)
        self._check_numeric_ops(a, b * 0, values, rvalues * 0, mix, op)

        a = self._klass(values, fill_value=0, dtype=dtype, kind=kind)
        assert a.dtype == SparseDtype(dtype)
        b = self._klass(rvalues, dtype=dtype, kind=kind)
        assert b.dtype == SparseDtype(dtype)

        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, fill_value=0, dtype=dtype, kind=kind)
        assert a.dtype == SparseDtype(dtype)
        b = self._klass(rvalues, fill_value=0, dtype=dtype, kind=kind)
        assert b.dtype == SparseDtype(dtype)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, fill_value=1, dtype=dtype, kind=kind)
        assert a.dtype == SparseDtype(dtype, fill_value=1)
        b = self._klass(rvalues, fill_value=2, dtype=dtype, kind=kind)
        assert b.dtype == SparseDtype(dtype, fill_value=2)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_int_array_comparison(self, kind):
        dtype = "int64"
        # int32 NI ATM

        values = self._base([0, 1, 2, 0, 0, 0, 1, 2, 1, 0], dtype=dtype)
        rvalues = self._base([2, 0, 2, 3, 0, 0, 1, 5, 2, 0], dtype=dtype)

        a = self._klass(values, dtype=dtype, kind=kind)
        b = self._klass(rvalues, dtype=dtype, kind=kind)
        self._check_comparison_ops(a, b, values, rvalues)
        self._check_comparison_ops(a, b * 0, values, rvalues * 0)

        a = self._klass(values, dtype=dtype, kind=kind, fill_value=0)
        b = self._klass(rvalues, dtype=dtype, kind=kind)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, dtype=dtype, kind=kind, fill_value=0)
        b = self._klass(rvalues, dtype=dtype, kind=kind, fill_value=0)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, dtype=dtype, kind=kind, fill_value=1)
        b = self._klass(rvalues, dtype=dtype, kind=kind, fill_value=2)
        self._check_comparison_ops(a, b, values, rvalues)

    @pytest.mark.parametrize("fill_value", [True, False, np.nan])
    def test_bool_same_index(self, kind, fill_value):
        # GH 14000
        # when sp_index are the same
        values = self._base([True, False, True, True], dtype=np.bool_)
        rvalues = self._base([True, False, True, True], dtype=np.bool_)

        a = self._klass(values, kind=kind, dtype=np.bool_, fill_value=fill_value)
        b = self._klass(rvalues, kind=kind, dtype=np.bool_, fill_value=fill_value)
        self._check_logical_ops(a, b, values, rvalues)

    @pytest.mark.parametrize("fill_value", [True, False, np.nan])
    def test_bool_array_logical(self, kind, fill_value):
        # GH 14000
        # when sp_index are the same
        values = self._base([True, False, True, False, True, True], dtype=np.bool_)
        rvalues = self._base([True, False, False, True, False, True], dtype=np.bool_)

        a = self._klass(values, kind=kind, dtype=np.bool_, fill_value=fill_value)
        b = self._klass(rvalues, kind=kind, dtype=np.bool_, fill_value=fill_value)
        self._check_logical_ops(a, b, values, rvalues)

    def test_mixed_array_float_int(self, kind, mix, all_arithmetic_functions, request):
        op = all_arithmetic_functions

        if not np_version_under1p20:
            if op in [operator.floordiv, ops.rfloordiv] and mix:
                mark = pytest.mark.xfail(strict=True, reason="GH#38172")
                request.node.add_marker(mark)

        rdtype = "int64"

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([2, 0, 2, 3, 0, 0, 1, 5, 2, 0], dtype=rdtype)

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        assert b.dtype == SparseDtype(rdtype)

        self._check_numeric_ops(a, b, values, rvalues, mix, op)
        self._check_numeric_ops(a, b * 0, values, rvalues * 0, mix, op)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind)
        assert b.dtype == SparseDtype(rdtype)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        assert b.dtype == SparseDtype(rdtype)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

        a = self._klass(values, kind=kind, fill_value=1)
        b = self._klass(rvalues, kind=kind, fill_value=2)
        assert b.dtype == SparseDtype(rdtype, fill_value=2)
        self._check_numeric_ops(a, b, values, rvalues, mix, op)

    def test_mixed_array_comparison(self, kind):
        rdtype = "int64"
        # int32 NI ATM

        values = self._base([np.nan, 1, 2, 0, np.nan, 0, 1, 2, 1, np.nan])
        rvalues = self._base([2, 0, 2, 3, 0, 0, 1, 5, 2, 0], dtype=rdtype)

        a = self._klass(values, kind=kind)
        b = self._klass(rvalues, kind=kind)
        assert b.dtype == SparseDtype(rdtype)

        self._check_comparison_ops(a, b, values, rvalues)
        self._check_comparison_ops(a, b * 0, values, rvalues * 0)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind)
        assert b.dtype == SparseDtype(rdtype)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, kind=kind, fill_value=0)
        b = self._klass(rvalues, kind=kind, fill_value=0)
        assert b.dtype == SparseDtype(rdtype)
        self._check_comparison_ops(a, b, values, rvalues)

        a = self._klass(values, kind=kind, fill_value=1)
        b = self._klass(rvalues, kind=kind, fill_value=2)
        assert b.dtype == SparseDtype(rdtype, fill_value=2)
        self._check_comparison_ops(a, b, values, rvalues)

    def test_xor(self):
        s = SparseArray([True, True, False, False])
        t = SparseArray([True, False, True, False])
        result = s ^ t
        sp_index = pd.core.arrays.sparse.IntIndex(4, np.array([0, 1, 2], dtype="int32"))
        expected = SparseArray([False, True, True], sparse_index=sp_index)
        tm.assert_sp_array_equal(result, expected)


@pytest.mark.parametrize("op", [operator.eq, operator.add])
def test_with_list(op):
    arr = SparseArray([0, 1], fill_value=0)
    result = op(arr, [0, 1])
    expected = op(arr, SparseArray([0, 1]))
    tm.assert_sp_array_equal(result, expected)


def test_with_dataframe():
    # GH#27910
    arr = SparseArray([0, 1], fill_value=0)
    df = pd.DataFrame([[1, 2], [3, 4]])
    result = arr.__add__(df)
    assert result is NotImplemented


def test_with_zerodim_ndarray():
    # GH#27910
    arr = SparseArray([0, 1], fill_value=0)

    result = arr * np.array(2)
    expected = arr * 2
    tm.assert_sp_array_equal(result, expected)


@pytest.mark.parametrize("ufunc", [np.abs, np.exp])
@pytest.mark.parametrize(
    "arr", [SparseArray([0, 0, -1, 1]), SparseArray([None, None, -1, 1])]
)
def test_ufuncs(ufunc, arr):
    result = ufunc(arr)
    fill_value = ufunc(arr.fill_value)
    expected = SparseArray(ufunc(np.asarray(arr)), fill_value=fill_value)
    tm.assert_sp_array_equal(result, expected)


@pytest.mark.parametrize(
    "a, b",
    [
        (SparseArray([0, 0, 0]), np.array([0, 1, 2])),
        (SparseArray([0, 0, 0], fill_value=1), np.array([0, 1, 2])),
        (SparseArray([0, 0, 0], fill_value=1), np.array([0, 1, 2])),
        (SparseArray([0, 0, 0], fill_value=1), np.array([0, 1, 2])),
        (SparseArray([0, 0, 0], fill_value=1), np.array([0, 1, 2])),
    ],
)
@pytest.mark.parametrize("ufunc", [np.add, np.greater])
def test_binary_ufuncs(ufunc, a, b):
    # can't say anything about fill value here.
    result = ufunc(a, b)
    expected = ufunc(np.asarray(a), np.asarray(b))
    assert isinstance(result, SparseArray)
    tm.assert_numpy_array_equal(np.asarray(result), expected)


def test_ndarray_inplace():
    sparray = SparseArray([0, 2, 0, 0])
    ndarray = np.array([0, 1, 2, 3])
    ndarray += sparray
    expected = np.array([0, 3, 2, 3])
    tm.assert_numpy_array_equal(ndarray, expected)


def test_sparray_inplace():
    sparray = SparseArray([0, 2, 0, 0])
    ndarray = np.array([0, 1, 2, 3])
    sparray += ndarray
    expected = SparseArray([0, 3, 2, 3], fill_value=0)
    tm.assert_sp_array_equal(sparray, expected)


@pytest.mark.parametrize("fill_value", [True, False])
def test_invert(fill_value):
    arr = np.array([True, False, False, True])
    sparray = SparseArray(arr, fill_value=fill_value)
    result = ~sparray
    expected = SparseArray(~arr, fill_value=not fill_value)
    tm.assert_sp_array_equal(result, expected)

    result = ~pd.Series(sparray)
    expected = pd.Series(expected)
    tm.assert_series_equal(result, expected)

    result = ~pd.DataFrame({"A": sparray})
    expected = pd.DataFrame({"A": expected})
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("fill_value", [0, np.nan])
@pytest.mark.parametrize("op", [operator.pos, operator.neg])
def test_unary_op(op, fill_value):
    arr = np.array([0, 1, np.nan, 2])
    sparray = SparseArray(arr, fill_value=fill_value)
    result = op(sparray)
    expected = SparseArray(op(arr), fill_value=op(fill_value))
    tm.assert_sp_array_equal(result, expected)
