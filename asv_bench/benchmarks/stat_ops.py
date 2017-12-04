import random
import numpy as np

import pandas as pd
from pandas import DataFrame, Series, MultiIndex

from .pandas_vb_common import (rolling_min, rolling_mean, rolling_median,
                               rolling_max, rolling_sum,
                               rolling_var, rolling_std,
                               rolling_kurt, rolling_skew)


def _set_use_bottleneck_False():
    try:
        pd.options.compute.use_bottleneck = False
    except:
        from pandas.core import nanops
        nanops._USE_BOTTLENECK = False


class FrameOps(object):
    goal_time = 0.2

    param_names = ['op', 'use_bottleneck', 'dtype', 'axis']
    params = [['mean', 'sum', 'median'],
              [True, False],
              ['float', 'int'],
              [0, 1]]

    def setup(self, op, use_bottleneck, dtype, axis):
        if dtype == 'float':
            self.df = DataFrame(np.random.randn(100000, 4))
        elif dtype == 'int':
            self.df = DataFrame(np.random.randint(1000, size=(100000, 4)))

        if not use_bottleneck:
            _set_use_bottleneck_False()

        self.func = getattr(self.df, op)

    def time_op(self, op, use_bottleneck, dtype, axis):
        self.func(axis=axis)


class stat_ops_level_frame_sum(object):
    goal_time = 0.2

    def setup(self):
        self.index = MultiIndex(levels=[np.arange(10),
                                        np.arange(100),
                                        np.arange(100)],
                                labels=[np.arange(10).repeat(10000),
                                        np.tile(np.arange(100).repeat(100),
                                                10),
                                        np.tile(np.tile(np.arange(100), 100),
                                                10)])
        random.shuffle(self.index.values)
        self.df = DataFrame(np.random.randn(len(self.index), 4), index=self.index)
        self.df_level = DataFrame(np.random.randn(100, 4), index=self.index.levels[1])

    def time_stat_ops_level_frame_sum(self):
        self.df.sum(level=1)


class stat_ops_level_frame_sum_multiple(object):
    goal_time = 0.2

    def setup(self):
        self.index = MultiIndex(levels=[np.arange(10),
                                        np.arange(100),
                                        np.arange(100)],
                                labels=[np.arange(10).repeat(10000),
                                        np.tile(np.arange(100).repeat(100),
                                                10),
                                        np.tile(np.tile(np.arange(100),
                                                        100), 10)])
        random.shuffle(self.index.values)
        self.df = DataFrame(np.random.randn(len(self.index), 4),
                            index=self.index)
        self.df_level = DataFrame(np.random.randn(100, 4),
                                  index=self.index.levels[1])

    def time_stat_ops_level_frame_sum_multiple(self):
        self.df.sum(level=[0, 1])


class stat_ops_level_series_sum(object):
    goal_time = 0.2

    def setup(self):
        self.index = MultiIndex(levels=[np.arange(10),
                                        np.arange(100),
                                        np.arange(100)],
                                labels=[np.arange(10).repeat(10000),
                                        np.tile(np.arange(100).repeat(100),
                                                10),
                                        np.tile(np.tile(np.arange(100), 100),
                                                10)])
        random.shuffle(self.index.values)
        self.df = DataFrame(np.random.randn(len(self.index), 4),
                            index=self.index)
        self.df_level = DataFrame(np.random.randn(100, 4),
                                  index=self.index.levels[1])

    def time_stat_ops_level_series_sum(self):
        self.df[1].sum(level=1)


class stat_ops_level_series_sum_multiple(object):
    goal_time = 0.2

    def setup(self):
        self.index = MultiIndex(levels=[np.arange(10),
                                        np.arange(100),
                                        np.arange(100)],
                                labels=[np.arange(10).repeat(10000),
                                        np.tile(np.arange(100).repeat(100),
                                                10),
                                        np.tile(np.tile(np.arange(100),
                                                        100), 10)])
        random.shuffle(self.index.values)
        self.df = DataFrame(np.random.randn(len(self.index), 4),
                            index=self.index)
        self.df_level = DataFrame(np.random.randn(100, 4),
                                  index=self.index.levels[1])

    def time_stat_ops_level_series_sum_multiple(self):
        self.df[1].sum(level=[0, 1])


class stat_ops_series_std(object):
    goal_time = 0.2

    def setup(self):
        self.s = Series(np.random.randn(100000), index=np.arange(100000))
        self.s[::2] = np.nan

    def time_stat_ops_series_std(self):
        self.s.std()


class stats_corr_spearman(object):
    goal_time = 0.2

    def setup(self):
        self.df = DataFrame(np.random.randn(1000, 30))

    def time_stats_corr_spearman(self):
        self.df.corr(method='spearman')


class stats_rank2d_axis0_average(object):
    goal_time = 0.2

    def setup(self):
        self.df = DataFrame(np.random.randn(5000, 50))

    def time_stats_rank2d_axis0_average(self):
        self.df.rank()


class stats_rank2d_axis1_average(object):
    goal_time = 0.2

    def setup(self):
        self.df = DataFrame(np.random.randn(5000, 50))

    def time_stats_rank2d_axis1_average(self):
        self.df.rank(1)


class stats_rank_average(object):
    goal_time = 0.2

    def setup(self):
        self.values = np.concatenate([np.arange(100000),
                                      np.random.randn(100000),
                                      np.arange(100000)])
        self.s = Series(self.values)

    def time_stats_rank_average(self):
        self.s.rank()


class stats_rank_average_int(object):
    goal_time = 0.2

    def setup(self):
        self.values = np.random.randint(0, 100000, size=200000)
        self.s = Series(self.values)

    def time_stats_rank_average_int(self):
        self.s.rank()


class stats_rank_pct_average(object):
    goal_time = 0.2

    def setup(self):
        self.values = np.concatenate([np.arange(100000),
                                      np.random.randn(100000),
                                      np.arange(100000)])
        self.s = Series(self.values)

    def time_stats_rank_pct_average(self):
        self.s.rank(pct=True)


class stats_rank_pct_average_old(object):
    goal_time = 0.2

    def setup(self):
        self.values = np.concatenate([np.arange(100000),
                                      np.random.randn(100000),
                                      np.arange(100000)])
        self.s = Series(self.values)

    def time_stats_rank_pct_average_old(self):
        (self.s.rank() / len(self.s))


class stats_rolling_mean(object):
    goal_time = 0.2

    def setup(self):
        self.arr = np.random.randn(100000)
        self.win = 100

    def time_rolling_mean(self):
        rolling_mean(self.arr, self.win)

    def time_rolling_median(self):
        rolling_median(self.arr, self.win)

    def time_rolling_min(self):
        rolling_min(self.arr, self.win)

    def time_rolling_max(self):
        rolling_max(self.arr, self.win)

    def time_rolling_sum(self):
        rolling_sum(self.arr, self.win)

    def time_rolling_std(self):
        rolling_std(self.arr, self.win)

    def time_rolling_var(self):
        rolling_var(self.arr, self.win)

    def time_rolling_skew(self):
        rolling_skew(self.arr, self.win)

    def time_rolling_kurt(self):
        rolling_kurt(self.arr, self.win)
