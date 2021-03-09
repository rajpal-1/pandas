import numpy as np
import pytest

from pandas import (
    DataFrame,
    IndexSlice,
    Series,
)

pytest.importorskip("matplotlib")
pytest.importorskip("jinja2")


class TestStylerMatplotlibDep:
    def test_background_gradient(self):
        df = DataFrame([[1, 2], [2, 4]], columns=["A", "B"])

        for c_map in [None, "YlOrRd"]:
            result = df.style.background_gradient(cmap=c_map)._compute().ctx
            assert all("#" in x[0][1] for x in result.values())
            assert result[(0, 0)] == result[(0, 1)]
            assert result[(1, 0)] == result[(1, 1)]

        result = df.style.background_gradient(subset=IndexSlice[1, "A"])._compute().ctx

        assert result[(1, 0)] == [("background-color", "#fff7fb"), ("color", "#000000")]

    @pytest.mark.parametrize(
        "cmap, expected",
        [
            (
                "PuBu",
                {
                    (4, 5): [("background-color", "#86b0d3"), ("color", "#000000")],
                    (4, 6): [("background-color", "#83afd3"), ("color", "#f1f1f1")],
                },
            ),
            (
                "YlOrRd",
                {
                    (4, 8): [("background-color", "#fd913e"), ("color", "#000000")],
                    (4, 9): [("background-color", "#fd8f3d"), ("color", "#f1f1f1")],
                },
            ),
            (
                None,
                {
                    (7, 0): [("background-color", "#48c16e"), ("color", "#f1f1f1")],
                    (7, 1): [("background-color", "#4cc26c"), ("color", "#000000")],
                },
            ),
        ],
    )
    def test_text_color_threshold(self, cmap, expected):
        df = DataFrame(np.arange(100).reshape(10, 10))
        result = df.style.background_gradient(cmap=cmap, axis=None)._compute().ctx
        for k in expected.keys():
            assert result[k] == expected[k]

    def test_background_gradient_axis(self):
        df = DataFrame([[1, 2], [2, 4]], columns=["A", "B"])

        low = [("background-color", "#f7fbff"), ("color", "#000000")]
        high = [("background-color", "#08306b"), ("color", "#f1f1f1")]
        mid = [("background-color", "#abd0e6"), ("color", "#000000")]
        result = df.style.background_gradient(cmap="Blues", axis=0)._compute().ctx
        assert result[(0, 0)] == low
        assert result[(0, 1)] == low
        assert result[(1, 0)] == high
        assert result[(1, 1)] == high

        result = df.style.background_gradient(cmap="Blues", axis=1)._compute().ctx
        assert result[(0, 0)] == low
        assert result[(0, 1)] == high
        assert result[(1, 0)] == low
        assert result[(1, 1)] == high

        result = df.style.background_gradient(cmap="Blues", axis=None)._compute().ctx
        assert result[(0, 0)] == low
        assert result[(0, 1)] == mid
        assert result[(1, 0)] == mid
        assert result[(1, 1)] == high

    def test_background_gradient_vmin_vmax(self):
        # GH 12145
        df = DataFrame(range(5))
        ctx = df.style.background_gradient(vmin=1, vmax=3)._compute().ctx
        assert ctx[(0, 0)] == ctx[(1, 0)]
        assert ctx[(4, 0)] == ctx[(3, 0)]

    def test_background_gradient_int64(self):
        # GH 28869
        df1 = Series(range(3)).to_frame()
        df2 = Series(range(3), dtype="Int64").to_frame()
        ctx1 = df1.style.background_gradient()._compute().ctx
        ctx2 = df2.style.background_gradient()._compute().ctx
        assert ctx2[(0, 0)] == ctx1[(0, 0)]
        assert ctx2[(1, 0)] == ctx1[(1, 0)]
        assert ctx2[(2, 0)] == ctx1[(2, 0)]

    @pytest.mark.parametrize(
        "axis, gmap, expected",
        [
            (
                0,
                [1, 2],
                {
                    (0, 0): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (1, 0): [("background-color", "#023858"), ("color", "#f1f1f1")],
                    (0, 1): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (1, 1): [("background-color", "#023858"), ("color", "#f1f1f1")],
                },
            ),
            (
                1,
                [1, 2],
                {
                    (0, 0): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (1, 0): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (0, 1): [("background-color", "#023858"), ("color", "#f1f1f1")],
                    (1, 1): [("background-color", "#023858"), ("color", "#f1f1f1")],
                },
            ),
            (
                None,
                np.array([[2, 1], [1, 2]]),
                {
                    (0, 0): [("background-color", "#023858"), ("color", "#f1f1f1")],
                    (1, 0): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (0, 1): [("background-color", "#fff7fb"), ("color", "#000000")],
                    (1, 1): [("background-color", "#023858"), ("color", "#f1f1f1")],
                },
            ),
        ],
    )
    def test_background_gradient_gmap_array(self, axis, gmap, expected):
        # tests when gmap is given as a sequence and converted to ndarray
        df = DataFrame([[0, 0], [0, 0]])
        result = df.style.background_gradient(axis=axis, gmap=gmap)._compute().ctx
        assert result == expected

    @pytest.mark.parametrize(
        "gmap, axis", [([1, 2, 3], 0), ([1, 2], 1), (np.array([[1, 2], [1, 2]]), None)]
    )
    def test_background_gradient_gmap_array_raises(self, gmap, axis):
        # test when gmap as converted ndarray is bad shape
        df = DataFrame([[0, 0, 0], [0, 0, 0]])
        msg = "supplied 'gmap' is not right shape"
        with pytest.raises(ValueError, match=msg):
            df.style.background_gradient(gmap=gmap, axis=axis)._compute()

    @pytest.mark.parametrize(
        "gmap",
        [
            DataFrame(  # reverse the columns
                [[2, 1], [1, 2]], columns=["B", "A"], index=["X", "Y"]
            ),
            DataFrame(  # reverse the index
                [[2, 1], [1, 2]], columns=["A", "B"], index=["Y", "X"]
            ),
            DataFrame(  # reverse the index and columns
                [[1, 2], [2, 1]], columns=["B", "A"], index=["Y", "X"]
            ),
            DataFrame(  # add unnecessary columns
                [[1, 2, 3], [2, 1, 3]], columns=["A", "B", "C"], index=["X", "Y"]
            ),
            DataFrame(  # add unnecessary index
                [[1, 2], [2, 1], [3, 3]], columns=["A", "B"], index=["X", "Y", "Z"]
            ),
        ],
    )
    @pytest.mark.parametrize(
        "subset, exp_gmap",  # exp_gmap is underlying map DataFrame should conform to
        [
            (None, [[1, 2], [2, 1]]),
            (["A"], [[1], [2]]),  # slice only column "A" in data and gmap
            (["B", "A"], [[2, 1], [1, 2]]),  # reverse the columns in data
            (IndexSlice["X", :], [[1, 2]]),  # slice only index "X" in data and gmap
            (IndexSlice[["Y", "X"], :], [[2, 1], [1, 2]]),  # reverse the index in data
        ],
    )
    def test_background_gradient_gmap_dataframe_align(self, gmap, subset, exp_gmap):
        # test gmap given as DataFrame that it aligns to the the data including subset
        df = DataFrame([[0, 0], [0, 0]], columns=["A", "B"], index=["X", "Y"])

        expected = df.style.background_gradient(axis=None, gmap=exp_gmap, subset=subset)
        result = df.style.background_gradient(axis=None, gmap=gmap, subset=subset)
        assert expected._compute().ctx == result._compute().ctx

    @pytest.mark.parametrize(
        "gmap, axis, exp_gmap",
        [
            (Series([2, 1], index=["Y", "X"]), 0, [[1, 1], [2, 2]]),  # revrse the index
            (Series([2, 1], index=["B", "A"]), 1, [[1, 2], [1, 2]]),  # revrse the cols
            (Series([1, 2, 3], index=["X", "Y", "Z"]), 0, [[1, 1], [2, 2]]),  # add idx
            (Series([1, 2, 3], index=["A", "B", "C"]), 1, [[1, 2], [1, 2]]),  # add col
        ],
    )
    def test_background_gradient_gmap_series_align(self, gmap, axis, exp_gmap):
        # test gmap given as Series that it aligns to the the data including subset
        df = DataFrame([[0, 0], [0, 0]], columns=["A", "B"], index=["X", "Y"])

        expected = df.style.background_gradient(axis=None, gmap=exp_gmap)._compute()
        result = df.style.background_gradient(axis=axis, gmap=gmap)._compute()
        assert expected.ctx == result.ctx

    def test_background_gradient_gmap_dataframe_raises(self):
        df = DataFrame([[0, 0, 0], [0, 0, 0]], columns=["A", "B", "C"])

        msg = "`gmap` as DataFrame must contain at least the columns"
        gmap = DataFrame([[1, 2, 3], [1, 2, 3]], columns=["A", "B", "X"])
        with pytest.raises(KeyError, match=msg):
            df.style.background_gradient(gmap=gmap, axis=None)._compute()

        msg = "`gmap` as DataFrame can only be used with `axis` is `None`"
        with pytest.raises(ValueError, match=msg):
            df.style.background_gradient(gmap=gmap, axis=1)._compute()
        with pytest.raises(ValueError, match=msg):
            df.style.background_gradient(gmap=gmap, axis=0)._compute()
