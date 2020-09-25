import operator
import re

import numpy as np
from numpy.random import randn
import pytest

import pandas._testing as tm
from pandas.core.api import DataFrame, Index, Series
from pandas.core.computation import expressions as expr

_frame = DataFrame(randn(10000, 4), columns=list("ABCD"), dtype="float64")
_frame2 = DataFrame(randn(100, 4), columns=list("ABCD"), dtype="float64")
_mixed = DataFrame(
    {
        "A": _frame["A"].copy(),
        "B": _frame["B"].astype("float32"),
        "C": _frame["C"].astype("int64"),
        "D": _frame["D"].astype("int32"),
    }
)
_mixed2 = DataFrame(
    {
        "A": _frame2["A"].copy(),
        "B": _frame2["B"].astype("float32"),
        "C": _frame2["C"].astype("int64"),
        "D": _frame2["D"].astype("int32"),
    }
)
_integer = DataFrame(
    np.random.randint(1, 100, size=(10001, 4)), columns=list("ABCD"), dtype="int64"
)
_integer2 = DataFrame(
    np.random.randint(1, 100, size=(101, 4)), columns=list("ABCD"), dtype="int64"
)


@pytest.mark.skipif(not expr.USE_NUMEXPR, reason="not using numexpr")
class TestExpressions:
    def setup_method(self, method):

        self.frame = _frame.copy()
        self.frame2 = _frame2.copy()
        self.mixed = _mixed.copy()
        self.mixed2 = _mixed2.copy()
        self._MIN_ELEMENTS = expr._MIN_ELEMENTS

    def teardown_method(self, method):
        expr._MIN_ELEMENTS = self._MIN_ELEMENTS

    def run_arithmetic(self, df, other):
        expr._MIN_ELEMENTS = 0
        operations = ["add", "sub", "mul", "mod", "truediv", "floordiv"]
        for test_flex in [True, False]:
            for arith in operations:
                # TODO: share with run_binary
                if test_flex:
                    op = lambda x, y: getattr(x, arith)(y)
                    op.__name__ = arith
                else:
                    op = getattr(operator, arith)
                expr.set_use_numexpr(False)
                expected = op(df, other)
                expr.set_use_numexpr(True)

                result = op(df, other)
                if arith == "truediv":
                    if expected.ndim == 1:
                        assert expected.dtype.kind == "f"
                    else:
                        assert all(x.kind == "f" for x in expected.dtypes.values)
                tm.assert_equal(expected, result)

    def run_binary(self, df, other):
        """
        tests solely that the result is the same whether or not numexpr is
        enabled.  Need to test whether the function does the correct thing
        elsewhere.
        """
        expr._MIN_ELEMENTS = 0
        expr.set_test_mode(True)
        operations = ["gt", "lt", "ge", "le", "eq", "ne"]

        for test_flex in [True, False]:
            for arith in operations:
                if test_flex:
                    op = lambda x, y: getattr(x, arith)(y)
                    op.__name__ = arith
                else:
                    op = getattr(operator, arith)
                expr.set_use_numexpr(False)
                expected = op(df, other)
                expr.set_use_numexpr(True)

                expr.get_test_result()
                result = op(df, other)
                used_numexpr = expr.get_test_result()
                assert used_numexpr, "Did not use numexpr as expected."
                tm.assert_equal(expected, result)

    def run_frame(self, df, other, run_binary=True):
        self.run_arithmetic(df, other)
        if run_binary:
            expr.set_use_numexpr(False)
            binary_comp = other + 1
            expr.set_use_numexpr(True)
            self.run_binary(df, binary_comp)

        for i in range(len(df.columns)):
            self.run_arithmetic(df.iloc[:, i], other.iloc[:, i])
            # FIXME: dont leave commented-out
            # series doesn't uses vec_compare instead of numexpr...
            # binary_comp = other.iloc[:, i] + 1
            # self.run_binary(df.iloc[:, i], binary_comp)

    @pytest.mark.parametrize(
        "df",
        [
            _integer,
            _integer2,
            # randint to get a case with zeros
            _integer * np.random.randint(0, 2, size=np.shape(_integer)),
            _frame,
            _frame2,
            _mixed,
            _mixed2,
        ],
    )
    def test_arithmetic(self, df):
        # TODO: FIGURE OUT HOW TO GET RUN_BINARY TO WORK WITH MIXED=...
        # can't do arithmetic because comparison methods try to do *entire*
        # frame instead of by-column
        kinds = {x.kind for x in df.dtypes.values}
        should = len(kinds) == 1

        self.run_frame(df, df, run_binary=should)

    def test_invalid(self):

        # no op
        result = expr._can_use_numexpr(
            operator.add, None, self.frame, self.frame, "evaluate"
        )
        assert not result

        # mixed
        result = expr._can_use_numexpr(
            operator.add, "+", self.mixed, self.frame, "evaluate"
        )
        assert not result

        # min elements
        result = expr._can_use_numexpr(
            operator.add, "+", self.frame2, self.frame2, "evaluate"
        )
        assert not result

        # ok, we only check on first part of expression
        result = expr._can_use_numexpr(
            operator.add, "+", self.frame, self.frame2, "evaluate"
        )
        assert result

    @pytest.mark.parametrize(
        "opname,op_str",
        [("add", "+"), ("sub", "-"), ("mul", "*"), ("truediv", "/"), ("pow", "**")],
    )
    @pytest.mark.parametrize("left,right", [(_frame, _frame2), (_mixed, _mixed2)])
    def test_binary_ops(self, opname, op_str, left, right):
        def testit():

            if opname == "pow":
                # TODO: get this working
                return

            op = getattr(operator, opname)

            result = expr._can_use_numexpr(op, op_str, left, left, "evaluate")
            assert result != left._is_mixed_type

            result = expr.evaluate(op, left, left, use_numexpr=True)
            expected = expr.evaluate(op, left, left, use_numexpr=False)

            if isinstance(result, DataFrame):
                tm.assert_frame_equal(result, expected)
            else:
                tm.assert_numpy_array_equal(result, expected.values)

            result = expr._can_use_numexpr(op, op_str, right, right, "evaluate")
            assert not result

        expr.set_use_numexpr(False)
        testit()
        expr.set_use_numexpr(True)
        expr.set_numexpr_threads(1)
        testit()
        expr.set_numexpr_threads()
        testit()

    @pytest.mark.parametrize(
        "opname,op_str",
        [
            ("gt", ">"),
            ("lt", "<"),
            ("ge", ">="),
            ("le", "<="),
            ("eq", "=="),
            ("ne", "!="),
        ],
    )
    @pytest.mark.parametrize("left,right", [(_frame, _frame2), (_mixed, _mixed2)])
    def test_comparison_ops(self, opname, op_str, left, right):
        def testit():
            f12 = left + 1
            f22 = right + 1

            op = getattr(operator, opname)

            result = expr._can_use_numexpr(op, op_str, left, f12, "evaluate")
            assert result != left._is_mixed_type

            result = expr.evaluate(op, left, f12, use_numexpr=True)
            expected = expr.evaluate(op, left, f12, use_numexpr=False)
            if isinstance(result, DataFrame):
                tm.assert_frame_equal(result, expected)
            else:
                tm.assert_numpy_array_equal(result, expected.values)

            result = expr._can_use_numexpr(op, op_str, right, f22, "evaluate")
            assert not result

        expr.set_use_numexpr(False)
        testit()
        expr.set_use_numexpr(True)
        expr.set_numexpr_threads(1)
        testit()
        expr.set_numexpr_threads()
        testit()

    @pytest.mark.parametrize("cond", [True, False])
    @pytest.mark.parametrize("df", [_frame, _frame2, _mixed, _mixed2])
    def test_where(self, cond, df):
        def testit():
            c = np.empty(df.shape, dtype=np.bool_)
            c.fill(cond)
            result = expr.where(c, df.values, df.values + 1)
            expected = np.where(c, df.values, df.values + 1)
            tm.assert_numpy_array_equal(result, expected)

        expr.set_use_numexpr(False)
        testit()
        expr.set_use_numexpr(True)
        expr.set_numexpr_threads(1)
        testit()
        expr.set_numexpr_threads()
        testit()

    @pytest.mark.parametrize(
        "op_str,opname", [("/", "truediv"), ("//", "floordiv"), ("**", "pow")]
    )
    def test_bool_ops_raise_on_arithmetic(self, op_str, opname):
        df = DataFrame({"a": np.random.rand(10) > 0.5, "b": np.random.rand(10) > 0.5})

        msg = f"operator {repr(op_str)} not implemented for bool dtypes"
        f = getattr(operator, opname)
        err_msg = re.escape(msg)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(df, df)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(df.a, df.b)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(df.a, True)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(False, df.a)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(False, df)

        with pytest.raises(NotImplementedError, match=err_msg):
            f(df, True)

    @pytest.mark.parametrize(
        "op_str,opname", [("+", "add"), ("*", "mul"), ("-", "sub")]
    )
    def test_bool_ops_warn_on_arithmetic(self, op_str, opname):
        n = 10
        df = DataFrame({"a": np.random.rand(n) > 0.5, "b": np.random.rand(n) > 0.5})

        subs = {"+": "|", "*": "&", "-": "^"}
        sub_funcs = {"|": "or_", "&": "and_", "^": "xor"}

        f = getattr(operator, opname)
        fe = getattr(operator, sub_funcs[subs[op_str]])

        if op_str == "-":
            # raises TypeError
            return

        with tm.use_numexpr(True, min_elements=5):
            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(df, df)
                e = fe(df, df)
                tm.assert_frame_equal(r, e)

            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(df.a, df.b)
                e = fe(df.a, df.b)
                tm.assert_series_equal(r, e)

            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(df.a, True)
                e = fe(df.a, True)
                tm.assert_series_equal(r, e)

            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(False, df.a)
                e = fe(False, df.a)
                tm.assert_series_equal(r, e)

            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(False, df)
                e = fe(False, df)
                tm.assert_frame_equal(r, e)

            with tm.assert_produces_warning(check_stacklevel=False):
                r = f(df, True)
                e = fe(df, True)
                tm.assert_frame_equal(r, e)

    @pytest.mark.parametrize(
        "test_input,expected",
        [
            (
                DataFrame(
                    [[0, 1, 2, "aa"], [0, 1, 2, "aa"]], columns=["a", "b", "c", "dtype"]
                ),
                DataFrame([[False, False], [False, False]], columns=["a", "dtype"]),
            ),
            (
                DataFrame(
                    [[0, 3, 2, "aa"], [0, 4, 2, "aa"], [0, 1, 1, "bb"]],
                    columns=["a", "b", "c", "dtype"],
                ),
                DataFrame(
                    [[False, False], [False, False], [False, False]],
                    columns=["a", "dtype"],
                ),
            ),
        ],
    )
    def test_bool_ops_column_name_dtype(self, test_input, expected):
        # GH 22383 - .ne fails if columns containing column name 'dtype'
        result = test_input.loc[:, ["a", "dtype"]].ne(test_input.loc[:, ["a", "dtype"]])
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "arith", ("add", "sub", "mul", "mod", "truediv", "floordiv")
    )
    @pytest.mark.parametrize("axis", (0, 1))
    def test_frame_series_axis(self, axis, arith):
        # GH#26736 Dataframe.floordiv(Series, axis=1) fails

        df = self.frame
        if axis == 1:
            other = self.frame.iloc[0, :]
        else:
            other = self.frame.iloc[:, 0]

        expr._MIN_ELEMENTS = 0

        op_func = getattr(df, arith)

        expr.set_use_numexpr(False)
        expected = op_func(other, axis=axis)
        expr.set_use_numexpr(True)

        result = op_func(other, axis=axis)
        tm.assert_frame_equal(expected, result)

    @pytest.mark.parametrize(
        "op",
        [
            "__mod__",
            pytest.param("__rmod__", marks=pytest.mark.xfail(reason="GH-36552")),
            "__floordiv__",
            "__rfloordiv__",
        ],
    )
    @pytest.mark.parametrize(
        "box, tester",
        [
            (DataFrame, tm.assert_frame_equal),
            (Series, tm.assert_series_equal),
            (Index, tm.assert_index_equal),
        ],
    )
    @pytest.mark.parametrize("scalar", [-5, 5])
    def test_python_semantics_with_numexpr_installed(self, op, box, tester, scalar):
        # https://github.com/pandas-dev/pandas/issues/36047
        expr._MIN_ELEMENTS = 0
        data = np.arange(-50, 50)
        obj = box(data)
        method = getattr(obj, op)
        result = method(scalar)

        # compare result with numpy
        expr.set_use_numexpr(False)
        expected = method(scalar)
        expr.set_use_numexpr(True)
        tester(result, expected)

        # compare result element-wise with Python
        for i, elem in enumerate(data):
            if box == DataFrame:
                scalar_result = result.iloc[i, 0]
            else:
                scalar_result = result[i]
            try:
                expected = getattr(int(elem), op)(scalar)
            except ZeroDivisionError:
                pass
            else:
                assert scalar_result == expected
