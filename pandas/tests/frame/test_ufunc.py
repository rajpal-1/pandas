import numpy as np
import pytest

import pandas as pd
import pandas._testing as tm

dtypes = [
    "int64",
    "Int64",
    {"A": "int64", "B": "Int64"},
]


@pytest.mark.parametrize("dtype", dtypes)
def test_unary_unary(dtype):
    # unary input, unary output
    values = np.array([[-1, -1], [1, 1]], dtype="int64")
    df = pd.DataFrame(values, columns=["A", "B"], index=["a", "b"]).astype(dtype=dtype)
    result = np.positive(df)
    expected = pd.DataFrame(
        np.positive(values), index=df.index, columns=df.columns
    ).astype(dtype)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("dtype", dtypes)
def test_unary_binary(request, dtype):
    # unary input, binary output
    if pd.api.types.is_extension_array_dtype(dtype) or isinstance(dtype, dict):
        request.node.add_marker(
            pytest.mark.xfail(
                reason="Extension / mixed with multiple outputs not implemented."
            )
        )

    values = np.array([[-1, -1], [1, 1]], dtype="int64")
    df = pd.DataFrame(values, columns=["A", "B"], index=["a", "b"]).astype(dtype=dtype)
    result_pandas = np.modf(df)
    assert isinstance(result_pandas, tuple)
    assert len(result_pandas) == 2
    expected_numpy = np.modf(values)

    for result, b in zip(result_pandas, expected_numpy):
        expected = pd.DataFrame(b, index=df.index, columns=df.columns)
        tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("dtype", dtypes)
def test_binary_input_dispatch_binop(dtype):
    # binop ufuncs are dispatched to our dunder methods.
    values = np.array([[-1, -1], [1, 1]], dtype="int64")
    df = pd.DataFrame(values, columns=["A", "B"], index=["a", "b"]).astype(dtype=dtype)
    result = np.add(df, df)
    expected = pd.DataFrame(
        np.add(values, values), index=df.index, columns=df.columns
    ).astype(dtype)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("dtype_a", dtypes)
@pytest.mark.parametrize("dtype_b", dtypes)
def test_binary_input_aligns_columns(request, dtype_a, dtype_b):
    if (
        pd.api.types.is_extension_array_dtype(dtype_a)
        or isinstance(dtype_a, dict)
        or pd.api.types.is_extension_array_dtype(dtype_b)
        or isinstance(dtype_b, dict)
    ):
        request.node.add_marker(
            pytest.mark.xfail(
                reason="Extension / mixed with multiple inputs not implemented."
            )
        )

    df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]}).astype(dtype_a)

    if isinstance(dtype_a, dict) and isinstance(dtype_b, dict):
        dtype_b["C"] = dtype_b.pop("B")

    df2 = pd.DataFrame({"A": [1, 2], "C": [3, 4]}).astype(dtype_b)
    with tm.assert_produces_warning(FutureWarning):
        result = np.heaviside(df1, df2)
    # Expected future behaviour:
    # expected = np.heaviside(
    #     np.array([[1, 3, np.nan], [2, 4, np.nan]]),
    #     np.array([[1, np.nan, 3], [2, np.nan, 4]]),
    # )
    # expected = pd.DataFrame(expected, index=[0, 1], columns=["A", "B", "C"])
    expected = pd.DataFrame([[1.0, 1.0], [1.0, 1.0]], columns=["A", "B"])
    tm.assert_frame_equal(result, expected)

    # ensure the expected is the same when applying with numpy array
    result = np.heaviside(df1, df2.values)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("dtype", dtypes)
def test_binary_input_aligns_index(request, dtype):
    if pd.api.types.is_extension_array_dtype(dtype) or isinstance(dtype, dict):
        request.node.add_marker(
            pytest.mark.xfail(
                reason="Extension / mixed with multiple inputs not implemented."
            )
        )
    df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]}, index=["a", "b"]).astype(dtype)
    df2 = pd.DataFrame({"A": [1, 2], "B": [3, 4]}, index=["a", "c"]).astype(dtype)
    with tm.assert_produces_warning(FutureWarning):
        result = np.heaviside(df1, df2)
    # Expected future behaviour:
    # expected = np.heaviside(
    #     np.array([[1, 3], [3, 4], [np.nan, np.nan]]),
    #     np.array([[1, 3], [np.nan, np.nan], [3, 4]]),
    # )
    # # TODO(FloatArray): this will be Float64Dtype.
    # expected = pd.DataFrame(expected, index=["a", "b", "c"], columns=["A", "B"])
    expected = pd.DataFrame(
        [[1.0, 1.0], [1.0, 1.0]], columns=["A", "B"], index=["a", "b"]
    )
    tm.assert_frame_equal(result, expected)

    # ensure the expected is the same when applying with numpy array
    result = np.heaviside(df1, df2.values)
    tm.assert_frame_equal(result, expected)


def test_binary_frame_series_raises():
    # We don't currently implement
    df = pd.DataFrame({"A": [1, 2]})
    # with pytest.raises(NotImplementedError, match="logaddexp"):
    with pytest.raises(ValueError, match=""):
        np.logaddexp(df, df["A"])

    # with pytest.raises(NotImplementedError, match="logaddexp"):
    with pytest.raises(ValueError, match=""):
        np.logaddexp(df["A"], df)


def test_frame_outer_deprecated():
    df = pd.DataFrame({"A": [1, 2]})
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        np.subtract.outer(df, df)


def test_alignment_deprecation():

    df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    df2 = pd.DataFrame({"b": [1, 2, 3], "c": [4, 5, 6]})
    s1 = pd.Series([1, 2], index=["a", "b"])
    s2 = pd.Series([1, 2], index=["b", "c"])

    # binary
    with tm.assert_produces_warning(None):
        # aligned -> no warning!
        result = np.add(df1, df1)
    expected = pd.DataFrame({"a": [2, 4, 6], "b": [8, 10, 12]})
    tm.assert_frame_equal(result, expected)

    with tm.assert_produces_warning(FutureWarning):
        result = np.add(df1, df2)
    tm.assert_frame_equal(result, expected)

    result = np.add(df1, df2.values)
    tm.assert_frame_equal(result, expected)

    result = np.add(df1.values, df2)
    expected = pd.DataFrame({"b": [2, 4, 6], "c": [8, 10, 12]})
    tm.assert_frame_equal(result, expected)

    with tm.assert_produces_warning(FutureWarning):
        result = np.add(df1, s2)
    expected = pd.DataFrame({"a": [2, 3, 4], "b": [6, 7, 8]})
    tm.assert_frame_equal(result, expected)

    with tm.assert_produces_warning(None):
        # aligned -> no warning!
        result = np.add(df1, s1)
    tm.assert_frame_equal(result, expected)

    with tm.assert_produces_warning(FutureWarning):
        result = np.add(s2, df1)
    tm.assert_frame_equal(result, expected)

    result = np.add(df1, s2.values)
    tm.assert_frame_equal(result, expected)
