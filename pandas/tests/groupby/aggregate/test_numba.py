import numpy as np
import pytest

from pandas.errors import NumbaUtilError
import pandas.util._test_decorators as td

from pandas import (
    DataFrame,
    Index,
    NamedAgg,
    Series,
    option_context,
)
import pandas._testing as tm


@td.skip_if_no("numba")
def test_correct_function_signature():
    def incorrect_function(x):
        return sum(x) * 2.7

    data = DataFrame(
        {"key": ["a", "a", "b", "b", "a"], "data": [1.0, 2.0, 3.0, 4.0, 5.0]},
        columns=["key", "data"],
    )
    with pytest.raises(NumbaUtilError, match="The first 2"):
        data.groupby("key").agg(incorrect_function, engine="numba")

    with pytest.raises(NumbaUtilError, match="The first 2"):
        data.groupby("key")["data"].agg(incorrect_function, engine="numba")


@td.skip_if_no("numba")
def test_check_nopython_kwargs():
    def incorrect_function(values, index):
        return sum(values) * 2.7

    data = DataFrame(
        {"key": ["a", "a", "b", "b", "a"], "data": [1.0, 2.0, 3.0, 4.0, 5.0]},
        columns=["key", "data"],
    )
    with pytest.raises(NumbaUtilError, match="numba does not support"):
        data.groupby("key").agg(incorrect_function, engine="numba", a=1)

    with pytest.raises(NumbaUtilError, match="numba does not support"):
        data.groupby("key")["data"].agg(incorrect_function, engine="numba", a=1)


@td.skip_if_no("numba")
@pytest.mark.filterwarnings("ignore:\n")
# Filter warnings when parallel=True and the function can't be parallelized by Numba
@pytest.mark.parametrize("jit", [True, False])
@pytest.mark.parametrize("pandas_obj", ["Series", "DataFrame"])
def test_numba_vs_cython(jit, pandas_obj, nogil, parallel, nopython):
    def func_numba(values, index):
        return np.mean(values) * 2.7

    if jit:
        # Test accepted jitted functions
        import numba

        func_numba = numba.jit(func_numba)

    data = DataFrame(
        {0: ["a", "a", "b", "b", "a"], 1: [1.0, 2.0, 3.0, 4.0, 5.0]}, columns=[0, 1]
    )
    engine_kwargs = {"nogil": nogil, "parallel": parallel, "nopython": nopython}
    grouped = data.groupby(0)
    if pandas_obj == "Series":
        grouped = grouped[1]

    result = grouped.agg(func_numba, engine="numba", engine_kwargs=engine_kwargs)
    expected = grouped.agg(lambda x: np.mean(x) * 2.7, engine="cython")

    tm.assert_equal(result, expected)


@td.skip_if_no("numba")
@pytest.mark.filterwarnings("ignore:\n")
# Filter warnings when parallel=True and the function can't be parallelized by Numba
@pytest.mark.parametrize("jit", [True, False])
@pytest.mark.parametrize("pandas_obj", ["Series", "DataFrame"])
def test_cache(jit, pandas_obj, nogil, parallel, nopython):
    # Test that the functions are cached correctly if we switch functions
    def func_1(values, index):
        return np.mean(values) - 3.4

    def func_2(values, index):
        return np.mean(values) * 2.7

    if jit:
        import numba

        func_1 = numba.jit(func_1)
        func_2 = numba.jit(func_2)

    data = DataFrame(
        {0: ["a", "a", "b", "b", "a"], 1: [1.0, 2.0, 3.0, 4.0, 5.0]}, columns=[0, 1]
    )
    engine_kwargs = {"nogil": nogil, "parallel": parallel, "nopython": nopython}
    grouped = data.groupby(0)
    if pandas_obj == "Series":
        grouped = grouped[1]

    result = grouped.agg(func_1, engine="numba", engine_kwargs=engine_kwargs)
    expected = grouped.agg(lambda x: np.mean(x) - 3.4, engine="cython")
    tm.assert_equal(result, expected)

    # Add func_2 to the cache
    result = grouped.agg(func_2, engine="numba", engine_kwargs=engine_kwargs)
    expected = grouped.agg(lambda x: np.mean(x) * 2.7, engine="cython")
    tm.assert_equal(result, expected)

    # Retest func_1 which should use the cache
    result = grouped.agg(func_1, engine="numba", engine_kwargs=engine_kwargs)
    expected = grouped.agg(lambda x: np.mean(x) - 3.4, engine="cython")
    tm.assert_equal(result, expected)


@td.skip_if_no("numba")
def test_use_global_config():
    def func_1(values, index):
        return np.mean(values) - 3.4

    data = DataFrame(
        {0: ["a", "a", "b", "b", "a"], 1: [1.0, 2.0, 3.0, 4.0, 5.0]}, columns=[0, 1]
    )
    grouped = data.groupby(0)
    expected = grouped.agg(func_1, engine="numba")
    with option_context("compute.use_numba", True):
        result = grouped.agg(func_1, engine=None)
    tm.assert_frame_equal(expected, result)


@td.skip_if_no("numba")
@pytest.mark.parametrize(
    "agg_func",
    [
        ["min", "max"],
        "min",
        {"B": ["min", "max"], "C": "sum"},
        NamedAgg(column="B", aggfunc="min"),
    ],
)
def test_multifunc_notimplimented(agg_func):
    data = DataFrame(
        {0: ["a", "a", "b", "b", "a"], 1: [1.0, 2.0, 3.0, 4.0, 5.0]}, columns=[0, 1]
    )
    grouped = data.groupby(0)
    with pytest.raises(NotImplementedError, match="Numba engine can"):
        grouped.agg(agg_func, engine="numba")

    with pytest.raises(NotImplementedError, match="Numba engine can"):
        grouped[1].agg(agg_func, engine="numba")


@td.skip_if_no("numba")
def test_args_not_cached():
    # GH 41647
    def sum_last(values, index, n):
        return values[-n:].sum()

    df = DataFrame({"id": [0, 0, 1, 1], "x": [1, 1, 1, 1]})
    grouped_x = df.groupby("id")["x"]
    result = grouped_x.agg(sum_last, 1, engine="numba")
    expected = Series([1.0] * 2, name="x", index=Index([0, 1], name="id"))
    tm.assert_series_equal(result, expected)

    result = grouped_x.agg(sum_last, 2, engine="numba")
    expected = Series([2.0] * 2, name="x", index=Index([0, 1], name="id"))
    tm.assert_series_equal(result, expected)


@td.skip_if_no("numba")
def test_index_data_correctly_passed():
    # GH 43133
    def f(values, index):
        return np.mean(index)

    df = DataFrame({"group": ["A", "A", "B"], "v": [4, 5, 6]}, index=[-1, -2, -3])
    result = df.groupby("group").aggregate(f, engine="numba")
    expected = DataFrame(
        [-1.5, -3.0], columns=["v"], index=Index(["A", "B"], name="group")
    )
    tm.assert_frame_equal(result, expected)


@td.skip_if_no("numba")
def test_engine_kwargs_not_cached():
    # If the user passes a different set of engine_kwargs don't return the same
    # jitted function
    nogil = True
    parallel = False
    nopython = True

    def func_kwargs(values, index):
        return nogil + parallel + nopython

    engine_kwargs = {"nopython": nopython, "nogil": nogil, "parallel": parallel}
    df = DataFrame({"value": [0, 0, 0]})
    result = df.groupby(level=0).aggregate(
        func_kwargs, engine="numba", engine_kwargs=engine_kwargs
    )
    expected = DataFrame({"value": [2.0, 2.0, 2.0]})
    tm.assert_frame_equal(result, expected)

    nogil = False
    engine_kwargs = {"nopython": nopython, "nogil": nogil, "parallel": parallel}
    result = df.groupby(level=0).aggregate(
        func_kwargs, engine="numba", engine_kwargs=engine_kwargs
    )
    expected = DataFrame({"value": [1.0, 1.0, 1.0]})
    tm.assert_frame_equal(result, expected)


@td.skip_if_no("numba")
def test_multiindex_one_key(nogil, parallel, nopython):
    def numba_func(values, index):
        return 1

    df = DataFrame([{"A": 1, "B": 2, "C": 3}]).set_index(["A", "B"])
    engine_kwargs = {"nopython": nopython, "nogil": nogil, "parallel": parallel}
    result = df.groupby("A").agg(
        numba_func, engine="numba", engine_kwargs=engine_kwargs
    )
    expected = DataFrame([1.0], index=Index([1], name="A"), columns=["C"])
    tm.assert_frame_equal(result, expected)


@td.skip_if_no("numba")
def test_multiindex_multi_key_not_supported(nogil, parallel, nopython):
    def numba_func(values, index):
        return 1

    df = DataFrame([{"A": 1, "B": 2, "C": 3}]).set_index(["A", "B"])
    engine_kwargs = {"nopython": nopython, "nogil": nogil, "parallel": parallel}
    with pytest.raises(NotImplementedError, match="More than 1 grouping labels"):
        df.groupby(["A", "B"]).agg(
            numba_func, engine="numba", engine_kwargs=engine_kwargs
        )
