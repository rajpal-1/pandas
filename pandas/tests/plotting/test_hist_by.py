import re

import numpy as np
import pytest

from pandas import DataFrame
import pandas._testing as tm
from pandas.tests.plotting.common import _check_axes_shape, _check_plot_works


@pytest.fixture(scope="module")
def test_hist_with_by_df():
    np.random.seed(0)
    df = DataFrame(np.random.randn(30, 2), columns=["A", "B"])
    df["C"] = np.random.choice(["a", "b", "c"], 30)
    df["D"] = np.random.choice(["a", "b", "c"], 30)
    return df


@pytest.mark.parametrize("by", ["C", ["C", "D"]])
@pytest.mark.parametrize("column", ["A", ["A", "B"], None])
def test_hist_plot_by_argument(by, column, test_hist_with_by_df):
    # GH 15079
    _check_plot_works(test_hist_with_by_df.plot.hist, column=column, by=by)


@pytest.mark.slow
@pytest.mark.parametrize(
    "by, column, layout, axes_num",
    [
        (["C"], "A", (2, 2), 3),
        ("C", "A", (2, 2), 3),
        (["C"], ["A"], (1, 3), 3),
        ("C", None, (3, 1), 3),
        ("C", ["A", "B"], (3, 1), 3),
        (["C", "D"], "A", (9, 1), 9),
        (["C", "D"], "A", (3, 3), 9),
        (["C", "D"], ["A"], (5, 2), 9),
        (["C", "D"], ["A", "B"], (9, 1), 9),
        (["C", "D"], None, (9, 1), 9),
        (["C", "D"], ["A", "B"], (5, 2), 9),
    ],
)
def test_hist_plot_layout_with_by(by, column, layout, axes_num, test_hist_with_by_df):
    # GH 15079
    # _check_plot_works adds an ax so catch warning. see GH #13188
    with tm.assert_produces_warning(UserWarning):
        axes = _check_plot_works(
            test_hist_with_by_df.plot.hist, column=column, by=by, layout=layout
        )
    _check_axes_shape(axes, axes_num=axes_num, layout=layout)


def test_hist_plot_invalid_layout_with_by_raises(test_hist_with_by_df):
    # GH 15079, test if error is raised when invalid layout is given

    # layout too small for all 3 plots
    msg = "larger than required size"
    with pytest.raises(ValueError, match=msg):
        test_hist_with_by_df.plot.hist(column=["A", "B"], by="C", layout=(1, 1))

    # invalid format for layout
    msg = re.escape("Layout must be a tuple of (rows, columns)")
    with pytest.raises(ValueError, match=msg):
        test_hist_with_by_df.plot.hist(column=["A", "B"], by="C", layout=(1,))

    msg = "At least one dimension of layout must be positive"
    with pytest.raises(ValueError, match=msg):
        test_hist_with_by_df.plot.hist(column=["A", "B"], by="C", layout=(-1, -1))


@pytest.mark.slow
def test_axis_share_x_with_by(test_hist_with_by_df):
    # GH 15079
    ax1, ax2, ax3 = test_hist_with_by_df.plot.hist(column="A", by="C", sharex=True)

    # share x
    assert ax1._shared_x_axes.joined(ax1, ax2)
    assert ax2._shared_x_axes.joined(ax1, ax2)
    assert ax3._shared_x_axes.joined(ax1, ax3)
    assert ax3._shared_x_axes.joined(ax2, ax3)

    # don't share y
    assert not ax1._shared_y_axes.joined(ax1, ax2)
    assert not ax2._shared_y_axes.joined(ax1, ax2)
    assert not ax3._shared_y_axes.joined(ax1, ax3)
    assert not ax3._shared_y_axes.joined(ax2, ax3)


@pytest.mark.slow
def test_axis_share_y_with_by(test_hist_with_by_df):
    # GH 15079
    ax1, ax2, ax3 = test_hist_with_by_df.plot.hist(column="A", by="C", sharey=True)

    # share y
    assert ax1._shared_y_axes.joined(ax1, ax2)
    assert ax2._shared_y_axes.joined(ax1, ax2)
    assert ax3._shared_y_axes.joined(ax1, ax3)
    assert ax3._shared_y_axes.joined(ax2, ax3)

    # don't share x
    assert not ax1._shared_x_axes.joined(ax1, ax2)
    assert not ax2._shared_x_axes.joined(ax1, ax2)
    assert not ax3._shared_x_axes.joined(ax1, ax3)
    assert not ax3._shared_x_axes.joined(ax2, ax3)


@pytest.mark.parametrize("figsize", [(12, 8), (20, 10)])
def test_figure_shape_hist_with_by(figsize, test_hist_with_by_df):
    # GH 15079
    axes = test_hist_with_by_df.plot.hist(column="A", by="C", figsize=figsize)
    _check_axes_shape(axes, axes_num=3, figsize=figsize)