import pytest

from pandas import Series
import pandas._testing as tm


class TestSeriesUnaryOps:
    # __neg__, __pos__, __inv__

    def test_neg(self):
        ser = tm.makeStringSeries()
        ser.name = "series"
        tm.assert_series_equal(-ser, -1 * ser)

    def test_invert(self):
        ser = tm.makeStringSeries()
        ser.name = "series"
        tm.assert_series_equal(-(ser < 0), ~(ser < 0))

    @pytest.mark.parametrize(
        "source, neg_target, abs_target",
        [
            ([1, 2, 3], [-1, -2, -3], [1, 2, 3]),
            ([1, 2, None], [-1, -2, None], [1, 2, None]),
            ([-1, 0, 1], [1, 0, -1], [1, 0, 1]),
        ],
    )
    def test_all_numeric_unary_operators(
        self, any_signed_nullable_numeric_dtype, source, neg_target, abs_target
    ):
        # GH38794
        dtype = any_signed_nullable_numeric_dtype
        ser = Series(source, dtype=dtype)
        neg_result, pos_result, abs_result = -ser, +ser, abs(ser)
        neg_target = Series(neg_target, dtype=dtype)
        abs_target = Series(abs_target, dtype=dtype)

        tm.assert_series_equal(neg_result, neg_target)
        tm.assert_series_equal(pos_result, ser)
        tm.assert_series_equal(abs_result, abs_target)

    @pytest.mark.parametrize("op", ["__neg__", "__abs__", "__pos__"])
    def test_unary_float_op_mask(self, float_ea_dtype, op):
        dtype = float_ea_dtype
        ser = Series([1.1, 2.2, 3.3], dtype=dtype)
        result = getattr(ser, op)()
        target = result.copy(deep=True)
        ser[0] = None
        tm.assert_series_equal(result, target)
