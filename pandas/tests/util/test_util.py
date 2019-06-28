import os
import sys

import pytest

import pandas.compat as compat
from pandas.compat import raise_with_traceback

import pandas.util.testing as tm


def test_rands():
    r = tm.rands(10)
    assert len(r) == 10


def test_rands_array_1d():
    arr = tm.rands_array(5, size=10)
    assert arr.shape == (10,)
    assert len(arr[0]) == 5


def test_rands_array_2d():
    arr = tm.rands_array(7, size=(10, 10))
    assert arr.shape == (10, 10)
    assert len(arr[1, 1]) == 7


def test_numpy_err_state_is_default():
    expected = {"over": "warn", "divide": "warn",
                "invalid": "warn", "under": "ignore"}
    import numpy as np

    # The error state should be unchanged after that import.
    assert np.geterr() == expected


def test_raise_with_traceback():
    with pytest.raises(LookupError, match="error_text"):
        try:
            raise ValueError("THIS IS AN ERROR")
        except ValueError:
            e = LookupError("error_text")
            raise_with_traceback(e)

    with pytest.raises(LookupError, match="error_text"):
        try:
            raise ValueError("This is another error")
        except ValueError:
            e = LookupError("error_text")
            _, _, traceback = sys.exc_info()
            raise_with_traceback(e, traceback)


def test_convert_rows_list_to_csv_str():
    rows_list = ["aaa", "bbb", "ccc"]
    ret = tm.convert_rows_list_to_csv_str(rows_list)

    if compat.is_platform_windows():
        expected = "aaa\r\nbbb\r\nccc\r\n"
    else:
        expected = "aaa\nbbb\nccc\n"

    assert ret == expected


def test_create_temp_directory():
    with tm.ensure_clean_dir() as path:
        assert os.path.exists(path)
        assert os.path.isdir(path)
    assert not os.path.exists(path)


def test_assert_raises_regex_deprecated():
    # see gh-23592

    with tm.assert_produces_warning(FutureWarning):
        msg = "Not equal!"

        with tm.assert_raises_regex(AssertionError, msg):
            assert 1 == 2, msg


@pytest.mark.parametrize('strict_data_files', [True, False])
def test_datapath_missing(datapath):
    with pytest.raises(ValueError, match="Could not find file"):
        datapath("not_a_file")


def test_datapath(datapath):
    args = ("data", "iris.csv")

    result = datapath(*args)
    expected = os.path.join(os.path.dirname(os.path.dirname(__file__)), *args)

    assert result == expected


def test_rng_context():
    import numpy as np

    expected0 = 1.764052345967664
    expected1 = 1.6243453636632417

    with tm.RNGContext(0):
        with tm.RNGContext(1):
            assert np.random.randn() == expected1
        assert np.random.randn() == expected0
