"""
these are systematically testing all of the args to value_counts
with different size combinations. This is to ensure stability of the sorting
and proper parameter handling
"""

from itertools import product

import numpy as np
import pytest

from pandas import DataFrame, Grouper, MultiIndex, Series, date_range
from pandas.util import testing as tm


# our starting frame
def seed_df(seed_nans, n, m):
    np.random.seed(1234)
    days = date_range("2015-08-24", periods=10)

    frame = DataFrame(
        {
            "1st": np.random.choice(list("abcd"), n),
            "2nd": np.random.choice(days, n),
            "3rd": np.random.randint(1, m + 1, n),
        }
    )

    if seed_nans:
        frame.loc[1::11, "1st"] = np.nan
        frame.loc[3::17, "2nd"] = np.nan
        frame.loc[7::19, "3rd"] = np.nan
        frame.loc[8::19, "3rd"] = np.nan
        frame.loc[9::19, "3rd"] = np.nan

    return frame


# create input df, keys, and the bins
binned = []
ids = []
for seed_nans in [True, False]:
    for n, m in product((100, 1000), (5, 20)):

        df = seed_df(seed_nans, n, m)
        bins = None, np.arange(0, max(5, df["3rd"].max()) + 1, 2)
        keys = "1st", "2nd", ["1st", "2nd"]
        for k, b in product(keys, bins):
            binned.append((df, k, b, n, m))
            ids.append("{}-{}-{}".format(k, n, m))


@pytest.mark.slow
@pytest.mark.parametrize("df, keys, bins, n, m", binned, ids=ids)
@pytest.mark.parametrize("isort", [True, False])
@pytest.mark.parametrize("normalize", [True, False])
@pytest.mark.parametrize("sort", [True, False])
@pytest.mark.parametrize("ascending", [True, False])
@pytest.mark.parametrize("dropna", [True, False])
def test_series_groupby_value_counts(
    df, keys, bins, n, m, isort, normalize, sort, ascending, dropna
):
    def rebuild_index(df):
        arr = list(map(df.index.get_level_values, range(df.index.nlevels)))
        df.index = MultiIndex.from_arrays(arr, names=df.index.names)
        return df

    kwargs = dict(
        normalize=normalize, sort=sort, ascending=ascending, dropna=dropna, bins=bins
    )

    gr = df.groupby(keys, sort=isort)
    left = gr["3rd"].value_counts(**kwargs)

    gr = df.groupby(keys, sort=isort)
    right = gr["3rd"].apply(Series.value_counts, **kwargs)
    right.index.names = right.index.names[:-1] + ["3rd"]

    # have to sort on index because of unstable sort on values
    left, right = map(rebuild_index, (left, right))  # xref GH9212
    tm.assert_series_equal(left.sort_index(), right.sort_index())


@pytest.mark.parametrize(
    "freq, size, frac", product(["1D", "2D", "1W", "1Y"], [100, 1000], [0.1, 0.5, 1])
)
def test_series_groupby_value_counts_with_grouper(freq, size, frac):
    np.random.seed(42)

    df = DataFrame.from_dict(
        {
            "date": date_range("2019-09-25", periods=size),
            "name": np.random.choice(list("abcd"), size),
        }
    ).sample(frac=frac)

    gr = df.groupby(Grouper(key="date", freq=freq))["name"]

    # have to sort on index because of unstable sort on values xref GH9212
    result = gr.value_counts().sort_index()
    expected = gr.apply(Series.value_counts).sort_index()
    expected.index.names = (
        result.index.names
    )  # .apply(Series.value_counts) can't create all names

    tm.assert_series_equal(result, expected)
