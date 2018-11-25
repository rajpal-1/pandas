from warnings import catch_warnings, simplefilter

import numpy as np
from numpy.random import randn
import pytest

import pandas._libs.index as _index
from pandas.compat import (
    StringIO, lrange, lzip, product as cart_product, range, u, zip)
from pandas.errors import PerformanceWarning

import pandas as pd
from pandas import (
    DataFrame, Index, MultiIndex, Series, Timestamp, concat, date_range, isna,
    notna, read_csv)
import pandas.core.common as com
from pandas.util import testing as tm


@pytest.fixture
def single_level_multiindex():
    """single level MultiIndex"""
    return MultiIndex(levels=[['foo', 'bar', 'baz', 'qux']],
                      labels=[[0, 1, 2, 3]], names=['first'])


@pytest.mark.filterwarnings("ignore:\\n.ix:DeprecationWarning")
class TestMultiIndexBasic(object):

    def test_setitem_multiindex(self):
        with catch_warnings(record=True):

            for index_fn in ('ix', 'loc'):

                def assert_equal(a, b):
                    assert a == b

                def check(target, indexers, value, compare_fn, expected=None):
                    fn = getattr(target, index_fn)
                    fn.__setitem__(indexers, value)
                    result = fn.__getitem__(indexers)
                    if expected is None:
                        expected = value
                    compare_fn(result, expected)
                # GH7190
                index = MultiIndex.from_product([np.arange(0, 100),
                                                 np.arange(0, 80)],
                                                names=['time', 'firm'])
                t, n = 0, 2
                df = DataFrame(np.nan, columns=['A', 'w', 'l', 'a', 'x',
                                                'X', 'd', 'profit'],
                               index=index)
                check(target=df, indexers=((t, n), 'X'), value=0,
                      compare_fn=assert_equal)

                df = DataFrame(-999, columns=['A', 'w', 'l', 'a', 'x',
                                              'X', 'd', 'profit'],
                               index=index)
                check(target=df, indexers=((t, n), 'X'), value=1,
                      compare_fn=assert_equal)

                df = DataFrame(columns=['A', 'w', 'l', 'a', 'x',
                                        'X', 'd', 'profit'],
                               index=index)
                check(target=df, indexers=((t, n), 'X'), value=2,
                      compare_fn=assert_equal)

                # gh-7218: assigning with 0-dim arrays
                df = DataFrame(-999, columns=['A', 'w', 'l', 'a', 'x',
                                              'X', 'd', 'profit'],
                               index=index)
                check(target=df,
                      indexers=((t, n), 'X'),
                      value=np.array(3),
                      compare_fn=assert_equal,
                      expected=3, )

                # GH5206
                df = DataFrame(np.arange(25).reshape(5, 5),
                               columns='A,B,C,D,E'.split(','), dtype=float)
                df['F'] = 99
                row_selection = df['A'] % 2 == 0
                col_selection = ['B', 'C']
                with catch_warnings(record=True):
                    df.ix[row_selection, col_selection] = df['F']
                output = DataFrame(99., index=[0, 2, 4], columns=['B', 'C'])
                with catch_warnings(record=True):
                    tm.assert_frame_equal(df.ix[row_selection, col_selection],
                                          output)
                check(target=df,
                      indexers=(row_selection, col_selection),
                      value=df['F'],
                      compare_fn=tm.assert_frame_equal,
                      expected=output, )

                # GH11372
                idx = MultiIndex.from_product([
                    ['A', 'B', 'C'],
                    date_range('2015-01-01', '2015-04-01', freq='MS')])
                cols = MultiIndex.from_product([
                    ['foo', 'bar'],
                    date_range('2016-01-01', '2016-02-01', freq='MS')])

                df = DataFrame(np.random.random((12, 4)),
                               index=idx, columns=cols)

                subidx = MultiIndex.from_tuples(
                    [('A', Timestamp('2015-01-01')),
                     ('A', Timestamp('2015-02-01'))])
                subcols = MultiIndex.from_tuples(
                    [('foo', Timestamp('2016-01-01')),
                     ('foo', Timestamp('2016-02-01'))])

                vals = DataFrame(np.random.random((2, 2)),
                                 index=subidx, columns=subcols)
                check(target=df,
                      indexers=(subidx, subcols),
                      value=vals,
                      compare_fn=tm.assert_frame_equal, )
                # set all columns
                vals = DataFrame(
                    np.random.random((2, 4)), index=subidx, columns=cols)
                check(target=df,
                      indexers=(subidx, slice(None, None, None)),
                      value=vals,
                      compare_fn=tm.assert_frame_equal, )
                # identity
                copy = df.copy()
                check(target=df, indexers=(df.index, df.columns), value=df,
                      compare_fn=tm.assert_frame_equal, expected=copy)

    def test_multiindex_perf_warn(self):

        df = DataFrame({'jim': [0, 0, 1, 1],
                        'joe': ['x', 'x', 'z', 'y'],
                        'jolie': np.random.rand(4)}).set_index(['jim', 'joe'])

        with tm.assert_produces_warning(PerformanceWarning,
                                        clear=[pd.core.index]):
            df.loc[(1, 'z')]

        df = df.iloc[[2, 1, 3, 0]]
        with tm.assert_produces_warning(PerformanceWarning):
            df.loc[(0, )]

    def test_series_getitem_multiindex(self):

        # GH 6018
        # series regression getitem with a multi-index

        s = Series([1, 2, 3])
        s.index = MultiIndex.from_tuples([(0, 0), (1, 1), (2, 1)])

        result = s[:, 0]
        expected = Series([1], index=[0])
        tm.assert_series_equal(result, expected)

        result = s.loc[:, 1]
        expected = Series([2, 3], index=[1, 2])
        tm.assert_series_equal(result, expected)

        # xs
        result = s.xs(0, level=0)
        expected = Series([1], index=[0])
        tm.assert_series_equal(result, expected)

        result = s.xs(1, level=1)
        expected = Series([2, 3], index=[1, 2])
        tm.assert_series_equal(result, expected)

        # GH6258
        dt = list(date_range('20130903', periods=3))
        idx = MultiIndex.from_product([list('AB'), dt])
        s = Series([1, 3, 4, 1, 3, 4], index=idx)

        result = s.xs('20130903', level=1)
        expected = Series([1, 1], index=list('AB'))
        tm.assert_series_equal(result, expected)

        # GH5684
        idx = MultiIndex.from_tuples([('a', 'one'), ('a', 'two'), ('b', 'one'),
                                      ('b', 'two')])
        s = Series([1, 2, 3, 4], index=idx)
        s.index.set_names(['L1', 'L2'], inplace=True)
        result = s.xs('one', level='L2')
        expected = Series([1, 3], index=['a', 'b'])
        expected.index.set_names(['L1'], inplace=True)
        tm.assert_series_equal(result, expected)

    def test_xs_multiindex(self):

        # GH2903
        columns = MultiIndex.from_tuples(
            [('a', 'foo'), ('a', 'bar'), ('b', 'hello'),
             ('b', 'world')], names=['lvl0', 'lvl1'])
        df = DataFrame(np.random.randn(4, 4), columns=columns)
        df.sort_index(axis=1, inplace=True)
        result = df.xs('a', level='lvl0', axis=1)
        expected = df.iloc[:, 0:2].loc[:, 'a']
        tm.assert_frame_equal(result, expected)

        result = df.xs('foo', level='lvl1', axis=1)
        expected = df.iloc[:, 1:2].copy()
        expected.columns = expected.columns.droplevel('lvl1')
        tm.assert_frame_equal(result, expected)

    def test_multiindex_setitem(self):

        # GH 3738
        # setting with a multi-index right hand side
        arrays = [np.array(['bar', 'bar', 'baz', 'qux', 'qux', 'bar']),
                  np.array(['one', 'two', 'one', 'one', 'two', 'one']),
                  np.arange(0, 6, 1)]

        df_orig = DataFrame(np.random.randn(6, 3), index=arrays,
                            columns=['A', 'B', 'C']).sort_index()

        expected = df_orig.loc[['bar']] * 2
        df = df_orig.copy()
        df.loc[['bar']] *= 2
        tm.assert_frame_equal(df.loc[['bar']], expected)

        # raise because these have differing levels
        def f():
            df.loc['bar'] *= 2

        pytest.raises(TypeError, f)

        # from SO
        # http://stackoverflow.com/questions/24572040/pandas-access-the-level-of-multiindex-for-inplace-operation
        df_orig = DataFrame.from_dict({'price': {
            ('DE', 'Coal', 'Stock'): 2,
            ('DE', 'Gas', 'Stock'): 4,
            ('DE', 'Elec', 'Demand'): 1,
            ('FR', 'Gas', 'Stock'): 5,
            ('FR', 'Solar', 'SupIm'): 0,
            ('FR', 'Wind', 'SupIm'): 0
        }})
        df_orig.index = MultiIndex.from_tuples(df_orig.index,
                                               names=['Sit', 'Com', 'Type'])

        expected = df_orig.copy()
        expected.iloc[[0, 2, 3]] *= 2

        idx = pd.IndexSlice
        df = df_orig.copy()
        df.loc[idx[:, :, 'Stock'], :] *= 2
        tm.assert_frame_equal(df, expected)

        df = df_orig.copy()
        df.loc[idx[:, :, 'Stock'], 'price'] *= 2
        tm.assert_frame_equal(df, expected)

    def test_getitem_duplicates_multiindex(self):
        # GH 5725 the 'A' happens to be a valid Timestamp so the doesn't raise
        # the appropriate error, only in PY3 of course!

        index = MultiIndex(levels=[['D', 'B', 'C'],
                                   [0, 26, 27, 37, 57, 67, 75, 82]],
                           labels=[[0, 0, 0, 1, 2, 2, 2, 2, 2, 2],
                                   [1, 3, 4, 6, 0, 2, 2, 3, 5, 7]],
                           names=['tag', 'day'])
        arr = np.random.randn(len(index), 1)
        df = DataFrame(arr, index=index, columns=['val'])
        result = df.val['D']
        expected = Series(arr.ravel()[0:3], name='val', index=Index(
            [26, 37, 57], name='day'))
        tm.assert_series_equal(result, expected)

        def f():
            df.val['A']

        pytest.raises(KeyError, f)

        def f():
            df.val['X']

        pytest.raises(KeyError, f)

        # A is treated as a special Timestamp
        index = MultiIndex(levels=[['A', 'B', 'C'],
                                   [0, 26, 27, 37, 57, 67, 75, 82]],
                           labels=[[0, 0, 0, 1, 2, 2, 2, 2, 2, 2],
                                   [1, 3, 4, 6, 0, 2, 2, 3, 5, 7]],
                           names=['tag', 'day'])
        df = DataFrame(arr, index=index, columns=['val'])
        result = df.val['A']
        expected = Series(arr.ravel()[0:3], name='val', index=Index(
            [26, 37, 57], name='day'))
        tm.assert_series_equal(result, expected)

        def f():
            df.val['X']

        pytest.raises(KeyError, f)

        # GH 7866
        # multi-index slicing with missing indexers
        idx = MultiIndex.from_product([['A', 'B', 'C'],
                                       ['foo', 'bar', 'baz']],
                                      names=['one', 'two'])
        s = Series(np.arange(9, dtype='int64'), index=idx).sort_index()

        exp_idx = MultiIndex.from_product([['A'], ['foo', 'bar', 'baz']],
                                          names=['one', 'two'])
        expected = Series(np.arange(3, dtype='int64'),
                          index=exp_idx).sort_index()

        result = s.loc[['A']]
        tm.assert_series_equal(result, expected)
        result = s.loc[['A', 'D']]
        tm.assert_series_equal(result, expected)

        # not any values found
        pytest.raises(KeyError, lambda: s.loc[['D']])

        # empty ok
        result = s.loc[[]]
        expected = s.iloc[[]]
        tm.assert_series_equal(result, expected)

        idx = pd.IndexSlice
        expected = Series([0, 3, 6], index=MultiIndex.from_product(
            [['A', 'B', 'C'], ['foo']], names=['one', 'two'])).sort_index()

        result = s.loc[idx[:, ['foo']]]
        tm.assert_series_equal(result, expected)
        result = s.loc[idx[:, ['foo', 'bah']]]
        tm.assert_series_equal(result, expected)

        # GH 8737
        # empty indexer
        multi_index = MultiIndex.from_product((['foo', 'bar', 'baz'],
                                               ['alpha', 'beta']))
        df = DataFrame(
            np.random.randn(5, 6), index=range(5), columns=multi_index)
        df = df.sort_index(level=0, axis=1)

        expected = DataFrame(index=range(5),
                             columns=multi_index.reindex([])[0])
        result1 = df.loc[:, ([], slice(None))]
        result2 = df.loc[:, (['foo'], [])]
        tm.assert_frame_equal(result1, expected)
        tm.assert_frame_equal(result2, expected)

        # regression from < 0.14.0
        # GH 7914
        df = DataFrame([[np.mean, np.median], ['mean', 'median']],
                       columns=MultiIndex.from_tuples([('functs', 'mean'),
                                                       ('functs', 'median')]),
                       index=['function', 'name'])
        result = df.loc['function', ('functs', 'mean')]
        assert result == np.mean

    def test_multiindex_assignment(self):

        # GH3777 part 2

        # mixed dtype
        df = DataFrame(np.random.randint(5, 10, size=9).reshape(3, 3),
                       columns=list('abc'),
                       index=[[4, 4, 8], [8, 10, 12]])
        df['d'] = np.nan
        arr = np.array([0., 1.])

        with catch_warnings(record=True):
            df.ix[4, 'd'] = arr
            tm.assert_series_equal(df.ix[4, 'd'],
                                   Series(arr, index=[8, 10], name='d'))

        # single dtype
        df = DataFrame(np.random.randint(5, 10, size=9).reshape(3, 3),
                       columns=list('abc'),
                       index=[[4, 4, 8], [8, 10, 12]])

        with catch_warnings(record=True):
            df.ix[4, 'c'] = arr
            exp = Series(arr, index=[8, 10], name='c', dtype='float64')
            tm.assert_series_equal(df.ix[4, 'c'], exp)

        # scalar ok
        with catch_warnings(record=True):
            df.ix[4, 'c'] = 10
            exp = Series(10, index=[8, 10], name='c', dtype='float64')
            tm.assert_series_equal(df.ix[4, 'c'], exp)

        # invalid assignments
        def f():
            with catch_warnings(record=True):
                df.ix[4, 'c'] = [0, 1, 2, 3]

        pytest.raises(ValueError, f)

        def f():
            with catch_warnings(record=True):
                df.ix[4, 'c'] = [0]

        pytest.raises(ValueError, f)

        # groupby example
        NUM_ROWS = 100
        NUM_COLS = 10
        col_names = ['A' + num for num in
                     map(str, np.arange(NUM_COLS).tolist())]
        index_cols = col_names[:5]

        df = DataFrame(np.random.randint(5, size=(NUM_ROWS, NUM_COLS)),
                       dtype=np.int64, columns=col_names)
        df = df.set_index(index_cols).sort_index()
        grp = df.groupby(level=index_cols[:4])
        df['new_col'] = np.nan

        f_index = np.arange(5)

        def f(name, df2):
            return Series(np.arange(df2.shape[0]),
                          name=df2.index.values[0]).reindex(f_index)

        # TODO(wesm): unused?
        # new_df = pd.concat([f(name, df2) for name, df2 in grp], axis=1).T

        # we are actually operating on a copy here
        # but in this case, that's ok
        for name, df2 in grp:
            new_vals = np.arange(df2.shape[0])
            with catch_warnings(record=True):
                df.ix[name, 'new_col'] = new_vals

    def test_multiindex_label_slicing_with_negative_step(self):
        s = Series(np.arange(20),
                   MultiIndex.from_product([list('abcde'), np.arange(4)]))
        SLC = pd.IndexSlice

        def assert_slices_equivalent(l_slc, i_slc):
            tm.assert_series_equal(s.loc[l_slc], s.iloc[i_slc])
            tm.assert_series_equal(s[l_slc], s.iloc[i_slc])
            with catch_warnings(record=True):
                tm.assert_series_equal(s.ix[l_slc], s.iloc[i_slc])

        assert_slices_equivalent(SLC[::-1], SLC[::-1])

        assert_slices_equivalent(SLC['d'::-1], SLC[15::-1])
        assert_slices_equivalent(SLC[('d', )::-1], SLC[15::-1])

        assert_slices_equivalent(SLC[:'d':-1], SLC[:11:-1])
        assert_slices_equivalent(SLC[:('d', ):-1], SLC[:11:-1])

        assert_slices_equivalent(SLC['d':'b':-1], SLC[15:3:-1])
        assert_slices_equivalent(SLC[('d', ):'b':-1], SLC[15:3:-1])
        assert_slices_equivalent(SLC['d':('b', ):-1], SLC[15:3:-1])
        assert_slices_equivalent(SLC[('d', ):('b', ):-1], SLC[15:3:-1])
        assert_slices_equivalent(SLC['b':'d':-1], SLC[:0])

        assert_slices_equivalent(SLC[('c', 2)::-1], SLC[10::-1])
        assert_slices_equivalent(SLC[:('c', 2):-1], SLC[:9:-1])
        assert_slices_equivalent(SLC[('e', 0):('c', 2):-1], SLC[16:9:-1])

    def test_multiindex_slice_first_level(self):
        # GH 12697
        freq = ['a', 'b', 'c', 'd']
        idx = MultiIndex.from_product([freq, np.arange(500)])
        df = DataFrame(list(range(2000)), index=idx, columns=['Test'])
        df_slice = df.loc[pd.IndexSlice[:, 30:70], :]
        result = df_slice.loc['a']
        expected = DataFrame(list(range(30, 71)),
                             columns=['Test'], index=range(30, 71))
        tm.assert_frame_equal(result, expected)
        result = df_slice.loc['d']
        expected = DataFrame(list(range(1530, 1571)),
                             columns=['Test'], index=range(30, 71))
        tm.assert_frame_equal(result, expected)

    def test_multiindex_symmetric_difference(self):
        # GH 13490
        idx = MultiIndex.from_product([['a', 'b'], ['A', 'B']],
                                      names=['a', 'b'])
        result = idx ^ idx
        assert result.names == idx.names

        idx2 = idx.copy().rename(['A', 'B'])
        result = idx ^ idx2
        assert result.names == [None, None]

    def test_multiindex_contains_dropped(self):
        # GH 19027
        # test that dropped MultiIndex levels are not in the MultiIndex
        # despite continuing to be in the MultiIndex's levels
        idx = MultiIndex.from_product([[1, 2], [3, 4]])
        assert 2 in idx
        idx = idx.drop(2)

        # drop implementation keeps 2 in the levels
        assert 2 in idx.levels[0]
        # but it should no longer be in the index itself
        assert 2 not in idx

        # also applies to strings
        idx = MultiIndex.from_product([['a', 'b'], ['c', 'd']])
        assert 'a' in idx
        idx = idx.drop('a')
        assert 'a' in idx.levels[0]
        assert 'a' not in idx

    @pytest.mark.parametrize("data, expected", [
        (MultiIndex.from_product([(), ()]), True),
        (MultiIndex.from_product([(1, 2), (3, 4)]), True),
        (MultiIndex.from_product([('a', 'b'), (1, 2)]), False),
    ])
    def test_multiindex_is_homogeneous_type(self, data, expected):
        assert data._is_homogeneous_type is expected

    def test_getitem_simple(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T

        col = df['foo', 'one']
        tm.assert_almost_equal(col.values, df.values[:, 0])
        with pytest.raises(KeyError):
            df[('foo', 'four')]
        with pytest.raises(KeyError):
            df['foobar']

    def test_series_getitem(
            self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data
        s = ymd['A']

        result = s[2000, 3]

        # TODO(wesm): unused?
        # result2 = s.loc[2000, 3]

        expected = s.reindex(s.index[42:65])
        expected.index = expected.index.droplevel(0).droplevel(0)
        tm.assert_series_equal(result, expected)

        result = s[2000, 3, 10]
        expected = s[49]
        assert result == expected

        # fancy
        expected = s.reindex(s.index[49:51])
        result = s.loc[[(2000, 3, 10), (2000, 3, 13)]]
        tm.assert_series_equal(result, expected)

        with catch_warnings(record=True):
            simplefilter("ignore", DeprecationWarning)
            result = s.ix[[(2000, 3, 10), (2000, 3, 13)]]
        tm.assert_series_equal(result, expected)

        # key error
        pytest.raises(KeyError, s.__getitem__, (2000, 3, 4))

    def test_series_getitem_corner(
            self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data
        s = ymd['A']

        # don't segfault, GH #495
        # out of bounds access
        pytest.raises(IndexError, s.__getitem__, len(ymd))

        # generator
        result = s[(x > 0 for x in s)]
        expected = s[s > 0]
        tm.assert_series_equal(result, expected)

    def test_series_setitem(
            self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data
        s = ymd['A']

        s[2000, 3] = np.nan
        assert isna(s.values[42:65]).all()
        assert notna(s.values[:42]).all()
        assert notna(s.values[65:]).all()

        s[2000, 3, 10] = np.nan
        assert isna(s[49])

    def test_frame_getitem_setitem_boolean(
            self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T.copy()
        values = df.values

        result = df[df > 0]
        expected = df.where(df > 0)
        tm.assert_frame_equal(result, expected)

        df[df > 0] = 5
        values[values > 0] = 5
        tm.assert_almost_equal(df.values, values)

        df[df == 5] = 0
        values[values == 5] = 0
        tm.assert_almost_equal(df.values, values)

        # a df that needs alignment first
        df[df[:-1] < 0] = 2
        np.putmask(values[:-1], values[:-1] < 0, 2)
        tm.assert_almost_equal(df.values, values)

        with pytest.raises(TypeError, match='boolean values only'):
            df[df * 0] = 2

    def test_frame_getitem_setitem_multislice(self):
        levels = [['t1', 't2'], ['a', 'b', 'c']]
        labels = [[0, 0, 0, 1, 1], [0, 1, 2, 0, 1]]
        midx = MultiIndex(labels=labels, levels=levels, names=[None, 'id'])
        df = DataFrame({'value': [1, 2, 3, 7, 8]}, index=midx)

        result = df.loc[:, 'value']
        tm.assert_series_equal(df['value'], result)

        with catch_warnings(record=True):
            simplefilter("ignore", DeprecationWarning)
            result = df.ix[:, 'value']
        tm.assert_series_equal(df['value'], result)

        result = df.loc[df.index[1:3], 'value']
        tm.assert_series_equal(df['value'][1:3], result)

        result = df.loc[:, :]
        tm.assert_frame_equal(df, result)

        result = df
        df.loc[:, 'value'] = 10
        result['value'] = 10
        tm.assert_frame_equal(df, result)

        df.loc[:, :] = 10
        tm.assert_frame_equal(df, result)

    def test_frame_getitem_multicolumn_empty_level(self):
        f = DataFrame({'a': ['1', '2', '3'], 'b': ['2', '3', '4']})
        f.columns = [['level1 item1', 'level1 item2'], ['', 'level2 item2'],
                     ['level3 item1', 'level3 item2']]

        result = f['level1 item1']
        expected = DataFrame([['1'], ['2'], ['3']], index=f.index,
                             columns=['level3 item1'])
        tm.assert_frame_equal(result, expected)

    def test_frame_setitem_multi_column(self):
        df = DataFrame(randn(10, 4), columns=[['a', 'a', 'b', 'b'],
                                              [0, 1, 0, 1]])

        cp = df.copy()
        cp['a'] = cp['b']
        tm.assert_frame_equal(cp['a'], cp['b'])

        # set with ndarray
        cp = df.copy()
        cp['a'] = cp['b'].values
        tm.assert_frame_equal(cp['a'], cp['b'])

        # ---------------------------------------
        # #1803
        columns = MultiIndex.from_tuples([('A', '1'), ('A', '2'), ('B', '1')])
        df = DataFrame(index=[1, 3, 5], columns=columns)

        # Works, but adds a column instead of updating the two existing ones
        df['A'] = 0.0  # Doesn't work
        assert (df['A'].values == 0).all()

        # it broadcasts
        df['B', '1'] = [1, 2, 3]
        df['A'] = df['B', '1']

        sliced_a1 = df['A', '1']
        sliced_a2 = df['A', '2']
        sliced_b1 = df['B', '1']
        tm.assert_series_equal(sliced_a1, sliced_b1, check_names=False)
        tm.assert_series_equal(sliced_a2, sliced_b1, check_names=False)
        assert sliced_a1.name == ('A', '1')
        assert sliced_a2.name == ('A', '2')
        assert sliced_b1.name == ('B', '1')

    def test_getitem_tuple_plus_slice(self):
        # GH #671
        df = DataFrame({'a': lrange(10),
                        'b': lrange(10),
                        'c': np.random.randn(10),
                        'd': np.random.randn(10)})

        idf = df.set_index(['a', 'b'])

        result = idf.loc[(0, 0), :]
        expected = idf.loc[0, 0]
        expected2 = idf.xs((0, 0))
        with catch_warnings(record=True):
            simplefilter("ignore", DeprecationWarning)
            expected3 = idf.ix[0, 0]

        tm.assert_series_equal(result, expected)
        tm.assert_series_equal(result, expected2)
        tm.assert_series_equal(result, expected3)

    def test_getitem_setitem_tuple_plus_columns(
            self, multiindex_year_month_day_dataframe_random_data):
        # GH #1013
        ymd = multiindex_year_month_day_dataframe_random_data
        df = ymd[:5]

        result = df.loc[(2000, 1, 6), ['A', 'B', 'C']]
        expected = df.loc[2000, 1, 6][['A', 'B', 'C']]
        tm.assert_series_equal(result, expected)

    def test_xs(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        xs = frame.xs(('bar', 'two'))
        xs2 = frame.loc[('bar', 'two')]

        tm.assert_series_equal(xs, xs2)
        tm.assert_almost_equal(xs.values, frame.values[4])

        # GH 6574
        # missing values in returned index should be preserrved
        acc = [
            ('a', 'abcde', 1),
            ('b', 'bbcde', 2),
            ('y', 'yzcde', 25),
            ('z', 'xbcde', 24),
            ('z', None, 26),
            ('z', 'zbcde', 25),
            ('z', 'ybcde', 26),
        ]
        df = DataFrame(acc,
                       columns=['a1', 'a2', 'cnt']).set_index(['a1', 'a2'])
        expected = DataFrame({'cnt': [24, 26, 25, 26]}, index=Index(
            ['xbcde', np.nan, 'zbcde', 'ybcde'], name='a2'))

        result = df.xs('z', level='a1')
        tm.assert_frame_equal(result, expected)

    def test_xs_with_duplicates(self, multiindex_dataframe_random_data):
        # Issue #13719
        frame = multiindex_dataframe_random_data
        df_dup = concat([frame] * 2)
        assert df_dup.index.is_unique is False
        expected = concat([frame.xs('one', level='second')] * 2)
        tm.assert_frame_equal(df_dup.xs('one', level='second'), expected)
        tm.assert_frame_equal(df_dup.xs(['one'], level=['second']), expected)

    def test_xs_level(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        result = frame.xs('two', level='second')
        expected = frame[frame.index.get_level_values(1) == 'two']
        expected.index = expected.index.droplevel(1)

        tm.assert_frame_equal(result, expected)

        index = MultiIndex.from_tuples([('x', 'y', 'z'), ('a', 'b', 'c'), (
            'p', 'q', 'r')])
        df = DataFrame(np.random.randn(3, 5), index=index)
        result = df.xs('c', level=2)
        expected = df[1:2]
        expected.index = expected.index.droplevel(2)
        tm.assert_frame_equal(result, expected)

        # this is a copy in 0.14
        result = frame.xs('two', level='second')

        # setting this will give a SettingWithCopyError
        # as we are trying to write a view
        def f(x):
            x[:] = 10

        pytest.raises(com.SettingWithCopyError, f, result)

    def test_xs_level_multiple(self):
        text = """                      A       B       C       D        E
one two three   four
a   b   10.0032 5    -0.5109 -2.3358 -0.4645  0.05076  0.3640
a   q   20      4     0.4473  1.4152  0.2834  1.00661  0.1744
x   q   30      3    -0.6662 -0.5243 -0.3580  0.89145  2.5838"""

        df = read_csv(StringIO(text), sep=r'\s+', engine='python')

        result = df.xs(('a', 4), level=['one', 'four'])
        expected = df.xs('a').xs(4, level='four')
        tm.assert_frame_equal(result, expected)

        # this is a copy in 0.14
        result = df.xs(('a', 4), level=['one', 'four'])

        # setting this will give a SettingWithCopyError
        # as we are trying to write a view
        def f(x):
            x[:] = 10

        pytest.raises(com.SettingWithCopyError, f, result)

        # GH2107
        dates = lrange(20111201, 20111205)
        ids = 'abcde'
        idx = MultiIndex.from_tuples([x for x in cart_product(dates, ids)])
        idx.names = ['date', 'secid']
        df = DataFrame(np.random.randn(len(idx), 3), idx, ['X', 'Y', 'Z'])

        rs = df.xs(20111201, level='date')
        xp = df.loc[20111201, :]
        tm.assert_frame_equal(rs, xp)

    def test_xs_level0(self):
        text = """                      A       B       C       D        E
one two three   four
a   b   10.0032 5    -0.5109 -2.3358 -0.4645  0.05076  0.3640
a   q   20      4     0.4473  1.4152  0.2834  1.00661  0.1744
x   q   30      3    -0.6662 -0.5243 -0.3580  0.89145  2.5838"""

        df = read_csv(StringIO(text), sep=r'\s+', engine='python')

        result = df.xs('a', level=0)
        expected = df.xs('a')
        assert len(result) == 2
        tm.assert_frame_equal(result, expected)

    def test_xs_level_series(self, multiindex_dataframe_random_data,
                             multiindex_year_month_day_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        ymd = multiindex_year_month_day_dataframe_random_data
        s = frame['A']
        result = s[:, 'two']
        expected = frame.xs('two', level=1)['A']
        tm.assert_series_equal(result, expected)

        s = ymd['A']
        result = s[2000, 5]
        expected = ymd.loc[2000, 5]['A']
        tm.assert_series_equal(result, expected)

        # not implementing this for now

        pytest.raises(TypeError, s.__getitem__, (2000, slice(3, 4)))

        # result = s[2000, 3:4]
        # lv =s.index.get_level_values(1)
        # expected = s[(lv == 3) | (lv == 4)]
        # expected.index = expected.index.droplevel(0)
        # tm.assert_series_equal(result, expected)

        # can do this though

    def test_get_loc_single_level(self, single_level_multiindex):
        single_level = single_level_multiindex
        s = Series(np.random.randn(len(single_level)),
                   index=single_level)
        for k in single_level.values:
            s[k]

    def test_getitem_toplevel(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T

        result = df['foo']
        expected = df.reindex(columns=df.columns[:3])
        expected.columns = expected.columns.droplevel(0)
        tm.assert_frame_equal(result, expected)

        result = df['bar']
        result2 = df.loc[:, 'bar']

        expected = df.reindex(columns=df.columns[3:5])
        expected.columns = expected.columns.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result, result2)

    def test_getitem_setitem_slice_integers(self):
        index = MultiIndex(levels=[[0, 1, 2], [0, 2]],
                           labels=[[0, 0, 1, 1, 2, 2], [0, 1, 0, 1, 0, 1]])

        frame = DataFrame(np.random.randn(len(index), 4), index=index,
                          columns=['a', 'b', 'c', 'd'])
        res = frame.loc[1:2]
        exp = frame.reindex(frame.index[2:])
        tm.assert_frame_equal(res, exp)

        frame.loc[1:2] = 7
        assert (frame.loc[1:2] == 7).values.all()

        series = Series(np.random.randn(len(index)), index=index)

        res = series.loc[1:2]
        exp = series.reindex(series.index[2:])
        tm.assert_series_equal(res, exp)

        series.loc[1:2] = 7
        assert (series.loc[1:2] == 7).values.all()

    def test_getitem_int(self, multiindex_dataframe_random_data):
        levels = [[0, 1], [0, 1, 2]]
        labels = [[0, 0, 0, 1, 1, 1], [0, 1, 2, 0, 1, 2]]
        index = MultiIndex(levels=levels, labels=labels)

        frame = DataFrame(np.random.randn(6, 2), index=index)

        result = frame.loc[1]
        expected = frame[-3:]
        expected.index = expected.index.droplevel(0)
        tm.assert_frame_equal(result, expected)

        # raises exception
        pytest.raises(KeyError, frame.loc.__getitem__, 3)

        # however this will work
        frame = multiindex_dataframe_random_data
        result = frame.iloc[2]
        expected = frame.xs(frame.index[2])
        tm.assert_series_equal(result, expected)

    def test_setitem_change_dtype(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        dft = frame.T
        s = dft['foo', 'two']
        dft['foo', 'two'] = s > s.median()
        tm.assert_series_equal(dft['foo', 'two'], s > s.median())
        # assert isinstance(dft._data.blocks[1].items, MultiIndex)

        reindexed = dft.reindex(columns=[('foo', 'two')])
        tm.assert_series_equal(reindexed['foo', 'two'], s > s.median())

    def test_frame_getitem_view(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T.copy()

        # this works because we are modifying the underlying array
        # really a no-no
        df['foo'].values[:] = 0
        assert (df['foo'].values == 0).all()

        # but not if it's mixed-type
        df['foo', 'four'] = 'foo'
        df = df.sort_index(level=0, axis=1)

        # this will work, but will raise/warn as its chained assignment
        def f():
            df['foo']['one'] = 2
            return df

        pytest.raises(com.SettingWithCopyError, f)

        try:
            df = f()
        except ValueError:
            pass
        assert (df['foo', 'one'] == 0).all()

    def test_getitem_lowerdim_corner(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        pytest.raises(KeyError, frame.loc.__getitem__,
                      (('bar', 'three'), 'B'))

        # in theory should be inserting in a sorted space????
        frame.loc[('bar', 'three'), 'B'] = 0
        assert frame.sort_index().loc[('bar', 'three'), 'B'] == 0

    def test_int_series_slicing(
            self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data
        s = ymd['A']
        result = s[5:]
        expected = s.reindex(s.index[5:])
        tm.assert_series_equal(result, expected)

        exp = ymd['A'].copy()
        s[5:] = 0
        exp.values[5:] = 0
        tm.assert_numpy_array_equal(s.values, exp.values)

        result = ymd[5:]
        expected = ymd.reindex(s.index[5:])
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize('unicode_strings', [True, False])
    def test_mixed_depth_get(self, unicode_strings):
        # If unicode_strings is True, the column labels in dataframe
        # construction will use unicode strings in Python 2 (pull request
        # #17099).

        arrays = [['a', 'top', 'top', 'routine1', 'routine1', 'routine2'],
                  ['', 'OD', 'OD', 'result1', 'result2', 'result1'],
                  ['', 'wx', 'wy', '', '', '']]

        if unicode_strings:
            arrays = [[u(s) for s in arr] for arr in arrays]

        tuples = sorted(zip(*arrays))
        index = MultiIndex.from_tuples(tuples)
        df = DataFrame(np.random.randn(4, 6), columns=index)

        result = df['a']
        expected = df['a', '', ''].rename('a')
        tm.assert_series_equal(result, expected)

        result = df['routine1', 'result1']
        expected = df['routine1', 'result1', '']
        expected = expected.rename(('routine1', 'result1'))
        tm.assert_series_equal(result, expected)

    def test_mixed_depth_insert(self):
        arrays = [['a', 'top', 'top', 'routine1', 'routine1', 'routine2'],
                  ['', 'OD', 'OD', 'result1', 'result2', 'result1'],
                  ['', 'wx', 'wy', '', '', '']]

        tuples = sorted(zip(*arrays))
        index = MultiIndex.from_tuples(tuples)
        df = DataFrame(randn(4, 6), columns=index)

        result = df.copy()
        expected = df.copy()
        result['b'] = [1, 2, 3, 4]
        expected['b', '', ''] = [1, 2, 3, 4]
        tm.assert_frame_equal(result, expected)

    def test_dataframe_insert_column_all_na(self):
        # GH #1534
        mix = MultiIndex.from_tuples([('1a', '2a'), ('1a', '2b'), ('1a', '2c')
                                      ])
        df = DataFrame([[1, 2], [3, 4], [5, 6]], index=mix)
        s = Series({(1, 1): 1, (1, 2): 2})
        df['new'] = s
        assert df['new'].isna().all()

    def test_set_column_scalar_with_ix(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        subset = frame.index[[1, 4, 5]]

        frame.loc[subset] = 99
        assert (frame.loc[subset].values == 99).all()

        col = frame['B']
        col[subset] = 97
        assert (frame.loc[subset, 'B'] == 97).all()

    def test_nonunique_assignment_1750(self):
        df = DataFrame([[1, 1, "x", "X"], [1, 1, "y", "Y"], [1, 2, "z", "Z"]],
                       columns=list("ABCD"))

        df = df.set_index(['A', 'B'])
        ix = MultiIndex.from_tuples([(1, 1)])

        df.loc[ix, "C"] = '_'

        assert (df.xs((1, 1))['C'] == '_').all()

    def test_indexing_over_hashtable_size_cutoff(self):
        n = 10000

        old_cutoff = _index._SIZE_CUTOFF
        _index._SIZE_CUTOFF = 20000

        s = Series(np.arange(n),
                   MultiIndex.from_arrays((["a"] * n, np.arange(n))))

        # hai it works!
        assert s[("a", 5)] == 5
        assert s[("a", 6)] == 6
        assert s[("a", 7)] == 7

        _index._SIZE_CUTOFF = old_cutoff

    def test_getitem_multilevel_index_tuple_not_sorted(self):
        index_columns = list("abc")
        df = DataFrame([[0, 1, 0, "x"], [0, 0, 1, "y"]],
                       columns=index_columns + ["data"])
        df = df.set_index(index_columns)
        query_index = df.index[:1]
        rs = df.loc[query_index, "data"]

        xp_idx = MultiIndex.from_tuples([(0, 1, 0)], names=['a', 'b', 'c'])
        xp = Series(['x'], index=xp_idx, name='data')
        tm.assert_series_equal(rs, xp)

    def test_getitem_slice_not_sorted(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.sort_index(level=1).T

        # buglet with int typechecking
        result = df.iloc[:, :np.int32(3)]
        expected = df.reindex(columns=df.columns[:3])
        tm.assert_frame_equal(result, expected)

    def test_frame_getitem_not_sorted2(self):
        # 13431
        df = DataFrame({'col1': ['b', 'd', 'b', 'a'],
                        'col2': [3, 1, 1, 2],
                        'data': ['one', 'two', 'three', 'four']})

        df2 = df.set_index(['col1', 'col2'])
        df2_original = df2.copy()

        df2.index.set_levels(['b', 'd', 'a'], level='col1', inplace=True)
        df2.index.set_labels([0, 1, 0, 2], level='col1', inplace=True)
        assert not df2.index.is_lexsorted()
        assert not df2.index.is_monotonic

        assert df2_original.index.equals(df2.index)
        expected = df2.sort_index()
        assert expected.index.is_lexsorted()
        assert expected.index.is_monotonic

        result = df2.sort_index(level=0)
        assert result.index.is_lexsorted()
        assert result.index.is_monotonic
        tm.assert_frame_equal(result, expected)

    def test_frame_getitem_not_sorted(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T
        df['foo', 'four'] = 'foo'

        arrays = [np.array(x) for x in zip(*df.columns.values)]

        result = df['foo']
        result2 = df.loc[:, 'foo']
        expected = df.reindex(columns=df.columns[arrays[0] == 'foo'])
        expected.columns = expected.columns.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

        df = df.T
        result = df.xs('foo')
        result2 = df.loc['foo']
        expected = df.reindex(df.index[arrays[0] == 'foo'])
        expected.index = expected.index.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

    def test_series_getitem_not_sorted(self):
        arrays = [['bar', 'bar', 'baz', 'baz', 'qux', 'qux', 'foo', 'foo'],
                  ['one', 'two', 'one', 'two', 'one', 'two', 'one', 'two']]
        tuples = lzip(*arrays)
        index = MultiIndex.from_tuples(tuples)
        s = Series(randn(8), index=index)

        arrays = [np.array(x) for x in zip(*index.values)]

        result = s['qux']
        result2 = s.loc['qux']
        expected = s[arrays[0] == 'qux']
        expected.index = expected.index.droplevel(0)
        tm.assert_series_equal(result, expected)
        tm.assert_series_equal(result2, expected)
