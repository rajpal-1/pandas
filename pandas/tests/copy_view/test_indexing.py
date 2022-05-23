import numpy as np
import pytest

import pandas as pd
from pandas import (
    DataFrame,
    Series,
)
import pandas._testing as tm
import pandas.core.common as com

# -----------------------------------------------------------------------------
# Indexing operations taking subset + modifying the subset/parent


def test_subset_column_selection(using_copy_on_write):
    # Case: taking a subset of the columns of a DataFrame
    # + afterwards modifying the subset
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()

    subset = df[["a", "c"]]

    if using_copy_on_write:
        # the subset shares memory ...
        assert np.shares_memory(subset["a"].values, df["a"].values)
        # ... but uses CoW when being modified
        subset.iloc[0, 0] = 0
    else:
        assert not np.shares_memory(subset["a"].values, df["a"].values)
        # INFO this no longer raise warning since pandas 1.4
        # with pd.option_context("chained_assignment", "warn"):
        #     with tm.assert_produces_warning(com.SettingWithCopyWarning):
        subset.iloc[0, 0] = 0

    assert not np.shares_memory(subset["a"].values, df["a"].values)

    expected = DataFrame({"a": [0, 2, 3], "c": [0.1, 0.2, 0.3]})
    tm.assert_frame_equal(subset, expected)
    tm.assert_frame_equal(df, df_orig)


def test_subset_column_selection_modify_parent(using_copy_on_write):
    # Case: taking a subset of the columns of a DataFrame
    # + afterwards modifying the parent
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})

    subset = df[["a", "c"]]
    if using_copy_on_write:
        # the subset shares memory ...
        assert np.shares_memory(subset["a"].values, df["a"].values)
        # ... but parent uses CoW parent when it is modified
    df.iloc[0, 0] = 0

    assert not np.shares_memory(subset["a"].values, df["a"].values)
    if using_copy_on_write:
        # different column/block still shares memory
        assert np.shares_memory(subset["c"].values, df["c"].values)

    expected = DataFrame({"a": [1, 2, 3], "c": [0.1, 0.2, 0.3]})
    tm.assert_frame_equal(subset, expected)


def test_subset_row_slice(using_copy_on_write):
    # Case: taking a subset of the rows of a DataFrame using a slice
    # + afterwards modifying the subset
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()

    subset = df[1:3]
    subset._mgr._verify_integrity()

    assert np.shares_memory(subset["a"].values, df["a"].values)

    if using_copy_on_write:
        subset.iloc[0, 0] = 0
        assert not np.shares_memory(subset["a"].values, df["a"].values)

    else:
        # INFO this no longer raise warning since pandas 1.4
        # with pd.option_context("chained_assignment", "warn"):
        #     with tm.assert_produces_warning(com.SettingWithCopyWarning):
        subset.iloc[0, 0] = 0

    subset._mgr._verify_integrity()

    expected = DataFrame({"a": [0, 3], "b": [5, 6], "c": [0.2, 0.3]}, index=range(1, 3))
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write:
        # original parent dataframe is not modified (CoW)
        tm.assert_frame_equal(df, df_orig)
    else:
        # original parent dataframe is actually updated
        df_orig.iloc[1, 0] = 0
        tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "dtype", ["int64", "float64"], ids=["single-block", "mixed-block"]
)
def test_subset_column_slice(using_copy_on_write, using_array_manager, dtype):
    # Case: taking a subset of the columns of a DataFrame using a slice
    # + afterwards modifying the subset
    single_block = (dtype == "int64") and not using_array_manager
    df = DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)}
    )
    df_orig = df.copy()

    subset = df.iloc[:, 1:]
    subset._mgr._verify_integrity()

    if using_copy_on_write:
        assert np.shares_memory(subset["b"].values, df["b"].values)

        subset.iloc[0, 0] = 0
        assert not np.shares_memory(subset["b"].values, df["b"].values)

    else:
        # we only get a warning in case of a single block
        warn = com.SettingWithCopyWarning if single_block else None
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(warn):
                subset.iloc[0, 0] = 0

    expected = DataFrame({"b": [0, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)})
    tm.assert_frame_equal(subset, expected)
    # original parent dataframe is not modified (also not for BlockManager case,
    # except for single block)
    if not using_copy_on_write and (using_array_manager or single_block):
        df_orig.iloc[0, 1] = 0
        tm.assert_frame_equal(df, df_orig)
    else:
        tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "dtype", ["int64", "float64"], ids=["single-block", "mixed-block"]
)
@pytest.mark.parametrize(
    "row_indexer",
    [slice(1, 2), np.array([False, True, True]), np.array([1, 2])],
    ids=["slice", "mask", "array"],
)
@pytest.mark.parametrize(
    "column_indexer",
    [slice("b", "c"), np.array([False, True, True]), ["b", "c"]],
    ids=["slice", "mask", "array"],
)
def test_subset_loc_rows_columns(
    dtype, row_indexer, column_indexer, using_array_manager
):
    # Case: taking a subset of the rows+columns of a DataFrame using .loc
    # + afterwards modifying the subset
    # Generic test for several combinations of row/column indexers, not all
    # of those could actually return a view / need CoW (so this test is not
    # checking memory sharing, only ensuring subsequent mutation doesn't
    # affect the parent dataframe)
    df = DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)}
    )
    df_orig = df.copy()

    subset = df.loc[row_indexer, column_indexer]

    # modifying the subset never modifies the parent
    subset.iloc[0, 0] = 0

    expected = DataFrame(
        {"b": [0, 6], "c": np.array([8, 9], dtype=dtype)}, index=range(1, 3)
    )
    tm.assert_frame_equal(subset, expected)
    # a few corner cases _do_ actually modify the parent (with both row and column
    # slice, and in case of ArrayManager or BlockManager with single block)
    if (
        isinstance(row_indexer, slice)
        and isinstance(column_indexer, slice)
        and (using_array_manager or dtype == "int64")
    ):
        df_orig.iloc[1, 1] = 0
    tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "dtype", ["int64", "float64"], ids=["single-block", "mixed-block"]
)
@pytest.mark.parametrize(
    "row_indexer",
    [slice(1, 3), np.array([False, True, True]), np.array([1, 2])],
    ids=["slice", "mask", "array"],
)
@pytest.mark.parametrize(
    "column_indexer",
    [slice(1, 3), np.array([False, True, True]), [1, 2]],
    ids=["slice", "mask", "array"],
)
def test_subset_iloc_rows_columns(
    dtype, row_indexer, column_indexer, using_array_manager
):
    # Case: taking a subset of the rows+columns of a DataFrame using .iloc
    # + afterwards modifying the subset
    # Generic test for several combinations of row/column indexers, not all
    # of those could actually return a view / need CoW (so this test is not
    # checking memory sharing, only ensuring subsequent mutation doesn't
    # affect the parent dataframe)
    df = DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)}
    )
    df_orig = df.copy()

    subset = df.iloc[row_indexer, column_indexer]

    # modifying the subset never modifies the parent
    subset.iloc[0, 0] = 0

    expected = DataFrame(
        {"b": [0, 6], "c": np.array([8, 9], dtype=dtype)}, index=range(1, 3)
    )
    tm.assert_frame_equal(subset, expected)
    # a few corner cases _do_ actually modify the parent (with both row and column
    # slice, and in case of ArrayManager or BlockManager with single block)
    if (
        isinstance(row_indexer, slice)
        and isinstance(column_indexer, slice)
        and (using_array_manager or dtype == "int64")
    ):
        df_orig.iloc[1, 1] = 0
    tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "indexer",
    [slice(0, 2), np.array([True, True, False]), np.array([0, 1])],
    ids=["slice", "mask", "array"],
)
def test_subset_set_with_row_indexer(indexer_si, indexer, using_copy_on_write):
    # Case: setting values with a row indexer on a viewing subset
    # subset[indexer] = value and subset.iloc[indexer] = value
    df = DataFrame({"a": [1, 2, 3, 4], "b": [4, 5, 6, 7], "c": [0.1, 0.2, 0.3, 0.4]})
    df_orig = df.copy()
    subset = df[1:4]

    if (
        indexer_si is tm.setitem
        and isinstance(indexer, np.ndarray)
        and indexer.dtype == "int"
    ):
        pytest.skip("setitem with labels selects on columns")

    if using_copy_on_write:
        indexer_si(subset)[indexer] = 0
    else:
        # INFO iloc no longer raises warning since pandas 1.4
        warn = com.SettingWithCopyWarning if indexer_si is tm.setitem else None
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(warn):
                indexer_si(subset)[indexer] = 0

    expected = DataFrame(
        {"a": [0, 0, 4], "b": [0, 0, 7], "c": [0.0, 0.0, 0.4]}, index=range(1, 4)
    )
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write:
        # original parent dataframe is not modified (CoW)
        tm.assert_frame_equal(df, df_orig)
    else:
        # original parent dataframe is actually updated
        df_orig[1:3] = 0
        tm.assert_frame_equal(df, df_orig)


def test_subset_set_with_mask(using_copy_on_write):
    # Case: setting values with a mask on a viewing subset: subset[mask] = value
    df = DataFrame({"a": [1, 2, 3, 4], "b": [4, 5, 6, 7], "c": [0.1, 0.2, 0.3, 0.4]})
    df_orig = df.copy()
    subset = df[1:4]

    mask = subset > 3

    if using_copy_on_write:
        subset[mask] = 0
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset[mask] = 0

    expected = DataFrame(
        {"a": [2, 3, 0], "b": [0, 0, 0], "c": [0.20, 0.3, 0.4]}, index=range(1, 4)
    )
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write:
        # original parent dataframe is not modified (CoW)
        tm.assert_frame_equal(df, df_orig)
    else:
        # original parent dataframe is actually updated
        df_orig.loc[3, "a"] = 0
        df_orig.loc[1:3, "b"] = 0
        tm.assert_frame_equal(df, df_orig)


def test_subset_set_column(using_copy_on_write):
    # Case: setting a single column on a viewing subset -> subset[col] = value
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()
    subset = df[1:3]

    if using_copy_on_write:
        subset["a"] = np.array([10, 11], dtype="int64")
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset["a"] = np.array([10, 11], dtype="int64")

    subset._mgr._verify_integrity()
    expected = DataFrame(
        {"a": [10, 11], "b": [5, 6], "c": [0.2, 0.3]}, index=range(1, 3)
    )
    tm.assert_frame_equal(subset, expected)
    tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "dtype", ["int64", "float64"], ids=["single-block", "mixed-block"]
)
def test_subset_set_column_with_loc(using_copy_on_write, using_array_manager, dtype):
    # Case: setting a single column with loc on a viewing subset
    # -> subset.loc[:, col] = value
    df = DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)}
    )
    df_orig = df.copy()
    subset = df[1:3]

    if using_copy_on_write:
        subset.loc[:, "a"] = np.array([10, 11], dtype="int64")
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset.loc[:, "a"] = np.array([10, 11], dtype="int64")

    subset._mgr._verify_integrity()
    expected = DataFrame(
        {"a": [10, 11], "b": [5, 6], "c": np.array([8, 9], dtype=dtype)},
        index=range(1, 3),
    )
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write or using_array_manager:
        # original parent dataframe is not modified (CoW)
        tm.assert_frame_equal(df, df_orig)
    else:
        # original parent dataframe is actually updated
        df_orig.loc[1:3, "a"] = np.array([10, 11], dtype="int64")
        tm.assert_frame_equal(df, df_orig)


def test_subset_set_column_with_loc2(using_copy_on_write, using_array_manager):
    # Case: setting a single column with loc on a viewing subset
    # -> subset.loc[:, col] = value
    # separate test for case of DataFrame of a single column -> takes a separate
    # code path
    df = DataFrame({"a": [1, 2, 3]})
    df_orig = df.copy()
    subset = df[1:3]

    if using_copy_on_write:
        subset.loc[:, "a"] = 0
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset.loc[:, "a"] = 0

    subset._mgr._verify_integrity()
    expected = DataFrame({"a": [0, 0]}, index=range(1, 3))
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write or using_array_manager:
        # original parent dataframe is not modified (CoW)
        tm.assert_frame_equal(df, df_orig)
    else:
        # original parent dataframe is actually updated
        df_orig.loc[1:3, "a"] = 0
        tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "dtype", ["int64", "float64"], ids=["single-block", "mixed-block"]
)
def test_subset_set_columns(using_copy_on_write, dtype):
    # Case: setting multiple columns on a viewing subset
    # -> subset[[col1, col2]] = value
    df = DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": np.array([7, 8, 9], dtype=dtype)}
    )
    df_orig = df.copy()
    subset = df[1:3]

    if using_copy_on_write:
        subset[["a", "c"]] = 0
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset[["a", "c"]] = 0

    subset._mgr._verify_integrity()
    if using_copy_on_write:
        # first and third column should certainly have no references anymore
        assert all(subset._mgr._has_no_reference(i) for i in [0, 2])
    expected = DataFrame({"a": [0, 0], "b": [5, 6], "c": [0, 0]}, index=range(1, 3))
    tm.assert_frame_equal(subset, expected)
    tm.assert_frame_equal(df, df_orig)


@pytest.mark.parametrize(
    "indexer",
    [slice("a", "b"), np.array([True, True, False]), ["a", "b"]],
    ids=["slice", "mask", "array"],
)
def test_subset_set_with_column_indexer(
    indexer, using_copy_on_write, using_array_manager
):
    # Case: setting multiple columns with a column indexer on a viewing subset
    # -> subset.loc[:, [col1, col2]] = value
    df = DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3], "c": [4, 5, 6]})
    df_orig = df.copy()
    subset = df[1:3]

    if using_copy_on_write:
        subset.loc[:, indexer] = 0
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                subset.loc[:, indexer] = 0

    subset._mgr._verify_integrity()
    expected = DataFrame({"a": [0, 0], "b": [0.0, 0.0], "c": [5, 6]}, index=range(1, 3))
    # TODO full row slice .loc[:, idx] update inplace instead of overwrite?
    expected["b"] = expected["b"].astype("int64")
    tm.assert_frame_equal(subset, expected)
    if using_copy_on_write or using_array_manager:
        tm.assert_frame_equal(df, df_orig)
    else:
        # In the mixed case with BlockManager, only one of the two columns is
        # mutated in the parent frame ..
        df_orig.loc[1:2, ["a"]] = 0
        tm.assert_frame_equal(df, df_orig)


# TODO add more tests modifying the parent


# -----------------------------------------------------------------------------
# Series -- Indexing operations taking subset + modifying the subset/parent


def test_series_getitem_slice(using_copy_on_write):
    # Case: taking a slice of a Series + afterwards modifying the subset
    s = Series([1, 2, 3], index=["a", "b", "c"])
    s_orig = s.copy()

    subset = s[:]
    assert np.shares_memory(subset.values, s.values)

    subset.iloc[0] = 0

    if using_copy_on_write:
        assert not np.shares_memory(subset.values, s.values)

    expected = Series([0, 2, 3], index=["a", "b", "c"])
    tm.assert_series_equal(subset, expected)

    if using_copy_on_write:
        # original parent series is not modified (CoW)
        tm.assert_series_equal(s, s_orig)
    else:
        # original parent series is actually updated
        assert s.iloc[0] == 0


@pytest.mark.parametrize(
    "indexer",
    [slice(0, 2), np.array([True, True, False]), np.array([0, 1])],
    ids=["slice", "mask", "array"],
)
def test_series_subset_set_with_indexer(indexer_si, indexer, using_copy_on_write):
    # Case: setting values in a viewing Series with an indexer
    s = Series([1, 2, 3], index=["a", "b", "c"])
    s_orig = s.copy()
    subset = s[:]

    indexer_si(subset)[indexer] = 0
    expected = Series([0, 0, 3], index=["a", "b", "c"])
    tm.assert_series_equal(subset, expected)

    if using_copy_on_write:
        tm.assert_series_equal(s, s_orig)
    else:
        tm.assert_series_equal(s, expected)


# -----------------------------------------------------------------------------
# del operator


def test_del_frame(using_copy_on_write):
    # Case: deleting a column with `del` on a viewing child dataframe should
    # not modify parent + update the references
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()
    df2 = df[:]

    assert np.shares_memory(df["a"].values, df2["a"].values)

    del df2["b"]

    assert np.shares_memory(df["a"].values, df2["a"].values)
    tm.assert_frame_equal(df, df_orig)
    tm.assert_frame_equal(df2, df_orig[["a", "c"]])
    df2._mgr._verify_integrity()

    # TODO in theory modifying column "b" of the parent wouldn't need a CoW
    # but the weakref is still alive and so we still perform CoW

    df2.loc[0, "a"] = 100
    if using_copy_on_write:
        # modifying child after deleting a column still doesn't update parent
        tm.assert_frame_equal(df, df_orig)
    else:
        assert df.loc[0, "a"] == 100


def test_del_series():
    s = Series([1, 2, 3], index=["a", "b", "c"])
    s_orig = s.copy()
    s2 = s[:]

    assert np.shares_memory(s.values, s2.values)

    del s2["a"]

    assert not np.shares_memory(s.values, s2.values)
    tm.assert_series_equal(s, s_orig)
    tm.assert_series_equal(s2, s_orig[["b", "c"]])

    # modifying s2 doesn't need copy on write (due to `del`, s2 is backed by new array)
    values = s2.values
    s2.loc["b"] = 100
    assert values[0] == 100


# -----------------------------------------------------------------------------
# Accessing column as Series


def test_column_as_series(using_copy_on_write, using_array_manager):
    # Case: selecting a single column now also uses Copy-on-Write
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()

    s = df["a"]

    assert np.shares_memory(s.values, df["a"].values)

    if using_copy_on_write or using_array_manager:
        s[0] = 0
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                s[0] = 0

    expected = Series([0, 2, 3], name="a")
    tm.assert_series_equal(s, expected)
    if using_copy_on_write:
        # assert not np.shares_memory(s.values, df["a"].values)
        tm.assert_frame_equal(df, df_orig)
        # ensure cached series on getitem is not the changed series
        tm.assert_series_equal(df["a"], df_orig["a"])
    else:
        df_orig.iloc[0, 0] = 0
        tm.assert_frame_equal(df, df_orig)


def test_column_as_series_set_with_upcast(using_copy_on_write, using_array_manager):
    # Case: selecting a single column now also uses Copy-on-Write -> when
    # setting a value causes an upcast, we don't need to update the parent
    # DataFrame through the cache mechanism
    df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [0.1, 0.2, 0.3]})
    df_orig = df.copy()

    s = df["a"]
    if using_copy_on_write or using_array_manager:
        s[0] = "foo"
    else:
        with pd.option_context("chained_assignment", "warn"):
            with tm.assert_produces_warning(com.SettingWithCopyWarning):
                s[0] = "foo"

    expected = Series(["foo", 2, 3], dtype=object, name="a")
    tm.assert_series_equal(s, expected)
    if using_copy_on_write:
        tm.assert_frame_equal(df, df_orig)
        # ensure cached series on getitem is not the changed series
        tm.assert_series_equal(df["a"], df_orig["a"])
    else:
        df_orig["a"] = expected
        tm.assert_frame_equal(df, df_orig)


# TODO add tests for other indexing methods on the Series


def test_dataframe_add_column_from_series():
    # Case: adding a new column to a DataFrame from an existing column/series
    # -> always already takes a copy on assignment
    # (no change in behaviour here)
    # TODO can we achieve the same behaviour with Copy-on-Write?
    df = DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})

    s = Series([10, 11, 12])
    df["new"] = s
    assert not np.shares_memory(df["new"].values, s.values)

    # editing series -> doesn't modify column in frame
    s[0] = 0
    expected = DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3], "new": [10, 11, 12]})
    tm.assert_frame_equal(df, expected)

    # editing column in frame -> doesn't modify series
    df.loc[2, "new"] = 100
    expected_s = Series([0, 11, 12])
    tm.assert_series_equal(s, expected_s)


# TODO add tests for constructors
