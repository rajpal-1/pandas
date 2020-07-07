import numpy as np

import pandas as pd
from pandas import _testing as tm


class TestTranspose:
    def test_transpose_tzaware_1col_single_tz(self):
        # GH#26825
        dti = pd.date_range("2016-04-05 04:30", periods=3, tz="UTC")

        df = pd.DataFrame(dti)
        assert (df.dtypes == dti.dtype).all()
        res = df.T
        assert (res.dtypes == dti.dtype).all()

    def test_transpose_tzaware_2col_single_tz(self):
        # GH#26825
        dti = pd.date_range("2016-04-05 04:30", periods=3, tz="UTC")

        df3 = pd.DataFrame({"A": dti, "B": dti})
        assert (df3.dtypes == dti.dtype).all()
        res3 = df3.T
        assert (res3.dtypes == dti.dtype).all()

    def test_transpose_tzaware_2col_mixed_tz(self):
        # GH#26825
        dti = pd.date_range("2016-04-05 04:30", periods=3, tz="UTC")
        dti2 = dti.tz_convert("US/Pacific")

        df4 = pd.DataFrame({"A": dti, "B": dti2})
        assert (df4.dtypes == [dti.dtype, dti2.dtype]).all()
        assert (df4.T.dtypes == object).all()
        tm.assert_frame_equal(df4.T.T, df4)

    def test_transpose_object_to_tzaware_mixed_tz(self):
        # GH#26825
        dti = pd.date_range("2016-04-05 04:30", periods=3, tz="UTC")
        dti2 = dti.tz_convert("US/Pacific")

        # mixed all-tzaware dtypes
        df2 = pd.DataFrame([dti, dti2])
        assert (df2.dtypes == object).all()
        res2 = df2.T
        assert (res2.dtypes == [dti.dtype, dti2.dtype]).all()

    def test_transpose_uint64(self, uint64_frame):

        result = uint64_frame.T
        expected = pd.DataFrame(uint64_frame.values.T)
        expected.index = ["A", "B"]
        tm.assert_frame_equal(result, expected)

    def test_transpose_float(self, float_frame):
        frame = float_frame
        dft = frame.T
        for idx, series in dft.items():
            for col, value in series.items():
                if np.isnan(value):
                    assert np.isnan(frame[col][idx])
                else:
                    assert value == frame[col][idx]

        # mixed type
        index, data = tm.getMixedTypeDict()
        mixed = pd.DataFrame(data, index=index)

        mixed_T = mixed.T
        for col, s in mixed_T.items():
            assert s.dtype == np.object_

    def test_transpose_get_view(self, float_frame):
        dft = float_frame.T
        dft.values[:, 5:10] = 5

        assert (float_frame.values[5:10] == 5).all()
