# import pandas as pd
import pandas._testing as tm


def test_index_replace():
    index = pd.Index([1, 2, 3])
    expected = pd.Index(["a", 2, "c"])

    result = index.replace([1, 3], ["a", "c"])

    tm.assert_equal(result, expected)


if __name__ == "__main__":
    # %load_ext autoreload
    # %autoreload 2

    import pandas as pd

    index = pd.Index([1, 2, 3])
    index.replace([1, 2], ["a", "b"])
