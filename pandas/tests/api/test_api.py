# -*- coding: utf-8 -*-
import sys
from warnings import catch_warnings

import pytest
import pandas as pd
from pandas import api
from pandas.util import testing as tm


class Base(object):

    def check(self, namespace, expected, ignored=None):
        # see which names are in the namespace, minus optional
        # ignored ones
        # compare vs the expected

        result = sorted([f for f in dir(namespace) if not f.startswith('_')])
        if ignored is not None:
            result = sorted(list(set(result) - set(ignored)))

        expected = sorted(expected)
        tm.assert_almost_equal(result, expected)


class TestPDApi(Base):

    # these are optionally imported based on testing
    # & need to be ignored
    ignored = ['tests', 'locale', 'conftest']

    # top-level sub-packages
    lib = ['api', 'compat', 'core', 'errors', 'pandas',
           'plotting', 'test', 'testing', 'tools', 'tseries',
           'util', 'options', 'io']

    # these are already deprecated; awaiting removal
    deprecated_modules = ['datetools', 'parser', 'json', 'lib', 'tslib']

    # misc
    misc = ['IndexSlice', 'NaT']

    # top-level classes
    classes = ['Categorical', 'CategoricalIndex', 'DataFrame', 'DateOffset',
               'DatetimeIndex', 'ExcelFile', 'ExcelWriter', 'Float64Index',
               'Grouper', 'HDFStore', 'Index', 'Int64Index', 'MultiIndex',
               'Period', 'PeriodIndex', 'RangeIndex', 'UInt64Index',
               'Series', 'SparseArray', 'SparseDataFrame',
               'SparseSeries', 'Timedelta',
               'TimedeltaIndex', 'Timestamp', 'Interval', 'IntervalIndex']

    # these are already deprecated; awaiting removal
    deprecated_classes = ['TimeGrouper', 'Expr', 'Term']

    # these should be deprecated in the future
    deprecated_classes_in_future = ['Panel']

    # external modules exposed in pandas namespace
    modules = ['np', 'datetime']

    # top-level functions
    funcs = ['bdate_range', 'concat', 'crosstab', 'cut',
             'date_range', 'interval_range', 'eval',
             'factorize', 'get_dummies',
             'infer_freq', 'isna', 'isnull', 'lreshape',
             'melt', 'notna', 'notnull', 'offsets',
             'merge', 'merge_ordered', 'merge_asof',
             'period_range',
             'pivot', 'pivot_table', 'qcut',
             'show_versions', 'timedelta_range', 'unique',
             'value_counts', 'wide_to_long']

    # top-level option funcs
    funcs_option = ['reset_option', 'describe_option', 'get_option',
                    'option_context', 'set_option',
                    'set_eng_float_format']

    # top-level read_* funcs
    funcs_read = ['read_clipboard', 'read_csv', 'read_excel', 'read_fwf',
                  'read_gbq', 'read_hdf', 'read_html', 'read_json',
                  'read_msgpack', 'read_pickle', 'read_sas', 'read_sql',
                  'read_sql_query', 'read_sql_table', 'read_stata',
                  'read_table', 'read_feather', 'read_parquet']

    # top-level to_* funcs
    funcs_to = ['to_datetime', 'to_msgpack',
                'to_numeric', 'to_pickle', 'to_timedelta']

    # top-level to deprecate in the future
    deprecated_funcs_in_future = []

    # these are already deprecated; awaiting removal
    deprecated_funcs = ['pnow', 'match', 'groupby', 'get_store',
                        'plot_params', 'scatter_matrix']

    def test_api(self):

        self.check(pd,
                   self.lib + self.misc +
                   self.modules + self.deprecated_modules +
                   self.classes + self.deprecated_classes +
                   self.deprecated_classes_in_future +
                   self.funcs + self.funcs_option +
                   self.funcs_read + self.funcs_to +
                   self.deprecated_funcs_in_future +
                   self.deprecated_funcs,
                   self.ignored)


class TestApi(Base):

    allowed = ['types', 'extensions']

    def test_api(self):

        self.check(api, self.allowed)


class TestTesting(Base):

    funcs = ['assert_frame_equal', 'assert_series_equal',
             'assert_index_equal']

    def test_testing(self):

        from pandas import testing
        self.check(testing, self.funcs)


class TestDatetoolsDeprecation(object):

    def test_deprecation_access_func(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.datetools.to_datetime('2016-01-01')

    def test_deprecation_access_obj(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.datetools.monthEnd


class TestTopLevelDeprecations(object):

    # top-level API deprecations
    # GH 13790

    def test_pnow(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.pnow(freq='M')

    def test_term(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.Term('index>=date')

    def test_expr(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.Expr('2>1')

    def test_match(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.match([1, 2, 3], [1])

    def test_groupby(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.groupby(pd.Series([1, 2, 3]), [1, 1, 1])

    def test_TimeGrouper(self):
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            pd.TimeGrouper(freq='D')

    # GH 15940

    def test_get_store(self):
        pytest.importorskip('tables')
        with tm.ensure_clean() as path:
            with tm.assert_produces_warning(FutureWarning,
                                            check_stacklevel=False):
                s = pd.get_store(path)
                s.close()


class TestJson(object):

    def test_deprecation_access_func(self):
        with catch_warnings(record=True):
            pd.json.dumps([])


class TestParser(object):

    def test_deprecation_access_func(self):
        with catch_warnings(record=True):
            pd.parser.na_values


class TestLib(object):

    def test_deprecation_access_func(self):
        with catch_warnings(record=True):
            pd.lib.infer_dtype('foo')


class TestTSLib(object):

    def test_deprecation_access_func(self):
        with catch_warnings(record=True):
            pd.tslib.Timestamp('20160101')


class TestTypes(object):

    def test_deprecation_access_func(self):
        with tm.assert_produces_warning(
                FutureWarning, check_stacklevel=False):
            from pandas.types.concat import union_categoricals
            c1 = pd.Categorical(list('aabc'))
            c2 = pd.Categorical(list('abcd'))
            union_categoricals(
                [c1, c2],
                sort_categories=True,
                ignore_order=True)


class TestCDateRange(object):

    def test_deprecation_cdaterange(self):
        # GH17596
        from pandas.core.indexes.datetimes import cdate_range
        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            cdate_range('2017-01-01', '2017-12-31')


class TestCategoricalMove(object):

    def test_categorical_move(self):
        # May have been cached by another import, e.g. pickle tests.
        sys.modules.pop("pandas.core.categorical", None)

        with tm.assert_produces_warning(FutureWarning):
            from pandas.core.categorical import Categorical  # noqa

        sys.modules.pop("pandas.core.categorical", None)

        with tm.assert_produces_warning(FutureWarning):
            from pandas.core.categorical import CategoricalDtype  # noqa
