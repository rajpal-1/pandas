import numpy as np
from pandas import Series, Index, DatetimeIndex, Timestamp

from .pandas_vb_common import setup # noqa


class SeriesConstructors(object):

    goal_time = 0.2

    param_names = ["data_fmt", "with_index"]
    params = [[lambda x: x,
               list,
               lambda arr: list(arr.astype(str)),
               lambda arr: dict(zip(range(len(arr)), arr)),
               lambda arr: [(i, -i) for i in arr],
               lambda arr: [[i, -i] for i in arr],
               lambda arr: ([(i, -i) for i in arr][:-1] + [None]),
               lambda arr: ([[i, -i] for i in arr][:-1] + [None])],
              [False, True]]

    def setup(self, data_fmt, with_index):
        N = 10**4
        np.random.seed(1234)
        arr = np.random.randn(N)
        self.data = data_fmt(arr)
        self.index = np.arange(N) if with_index else None

    def time_series_constructor(self, data_fmt, with_index):
        Series(self.data, index=self.index)


class SeriesDtypesConstructors(object):

    goal_time = 0.2

    def setup(self):
        N = 10**2
        self.arr = np.random.randn(N, N)
        self.arr_str = np.array(['foo', 'bar', 'baz'], dtype=object)

        self.data = np.random.randn(N)
        self.index = Index(np.arange(N))

        self.s = Series([Timestamp('20110101'), Timestamp('20120101'),
                         Timestamp('20130101')] * N * 10)

    def time_index_from_array_string(self):
        Index(self.arr_str)

    def time_dtindex_from_series(self):
        DatetimeIndex(self.s)

    def time_dtindex_from_index_with_series(self):
        Index(self.s)
