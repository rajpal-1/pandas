"""
missing types & inference
"""
import numpy as np

from pandas._config import get_option

from pandas._libs import lib
import pandas._libs.missing as libmissing
from pandas._libs.tslibs import NaT, iNaT
from pandas._typing import DtypeObj

from pandas.core.dtypes.common import (
    DT64NS_DTYPE,
    TD64NS_DTYPE,
    ensure_object,
    is_bool_dtype,
    is_complex_dtype,
    is_datetimelike_v_numeric,
    is_dtype_equal,
    is_extension_array_dtype,
    is_float_dtype,
    is_integer_dtype,
    is_object_dtype,
    is_scalar,
    is_string_dtype,
    is_string_like_dtype,
    needs_i8_conversion,
    pandas_dtype,
)
from pandas.core.dtypes.generic import (
    ABCDataFrame,
    ABCExtensionArray,
    ABCIndexClass,
    ABCMultiIndex,
    ABCSeries,
)
from pandas.core.dtypes.inference import is_list_like

isposinf_scalar = libmissing.isposinf_scalar
isneginf_scalar = libmissing.isneginf_scalar


def isna(obj):
    """
    Detect missing values for an array-like object.

    This function takes a scalar or array-like object and indicates
    whether values are missing (``NaN`` in numeric arrays, ``None`` or ``NaN``
    in object arrays, ``NaT`` in datetimelike).

    Parameters
    ----------
    obj : scalar or array-like
        Object to check for null or missing values.

    Returns
    -------
    bool or array-like of bool
        For scalar input, returns a scalar boolean.
        For array input, returns an array of boolean indicating whether each
        corresponding element is missing.

    See Also
    --------
    notna : Boolean inverse of pandas.isna.
    Series.isna : Detect missing values in a Series.
    DataFrame.isna : Detect missing values in a DataFrame.
    Index.isna : Detect missing values in an Index.

    Examples
    --------
    Scalar arguments (including strings) result in a scalar boolean.

    >>> pd.isna('dog')
    False

    >>> pd.isna(pd.NA)
    True

    >>> pd.isna(np.nan)
    True

    ndarrays result in an ndarray of booleans.

    >>> array = np.array([[1, np.nan, 3], [4, 5, np.nan]])
    >>> array
    array([[ 1., nan,  3.],
           [ 4.,  5., nan]])
    >>> pd.isna(array)
    array([[False,  True, False],
           [False, False,  True]])

    For indexes, an ndarray of booleans is returned.

    >>> index = pd.DatetimeIndex(["2017-07-05", "2017-07-06", None,
    ...                           "2017-07-08"])
    >>> index
    DatetimeIndex(['2017-07-05', '2017-07-06', 'NaT', '2017-07-08'],
                  dtype='datetime64[ns]', freq=None)
    >>> pd.isna(index)
    array([False, False,  True, False])

    For Series and DataFrame, the same type is returned, containing booleans.

    >>> df = pd.DataFrame([['ant', 'bee', 'cat'], ['dog', None, 'fly']])
    >>> df
         0     1    2
    0  ant   bee  cat
    1  dog  None  fly
    >>> pd.isna(df)
           0      1      2
    0  False  False  False
    1  False   True  False

    >>> pd.isna(df[1])
    0    False
    1     True
    Name: 1, dtype: bool
    """
    return _isna(obj)


isnull = isna


def _isna_new(obj):

    if is_scalar(obj):
        return libmissing.checknull(obj)
    # hack (for now) because MI registers as ndarray
    elif isinstance(obj, ABCMultiIndex):
        raise NotImplementedError("isna is not defined for MultiIndex")
    elif isinstance(obj, type):
        return False
    elif isinstance(obj, (ABCSeries, np.ndarray, ABCIndexClass, ABCExtensionArray)):
        return _isna_ndarraylike(obj, old=False)
    elif isinstance(obj, ABCDataFrame):
        return obj.isna()
    elif isinstance(obj, list):
        return _isna_ndarraylike(np.asarray(obj, dtype=object), old=False)
    elif hasattr(obj, "__array__"):
        return _isna_ndarraylike(np.asarray(obj), old=False)
    else:
        return False


def _isna_old(obj):
    """
    Detect missing values, treating None, NaN, INF, -INF as null.

    Parameters
    ----------
    arr: ndarray or object value

    Returns
    -------
    boolean ndarray or boolean
    """
    if is_scalar(obj):
        return libmissing.checknull_old(obj)
    # hack (for now) because MI registers as ndarray
    elif isinstance(obj, ABCMultiIndex):
        raise NotImplementedError("isna is not defined for MultiIndex")
    elif isinstance(obj, type):
        return False
    elif isinstance(obj, (ABCSeries, np.ndarray, ABCIndexClass, ABCExtensionArray)):
        return _isna_ndarraylike(obj, old=True)
    elif isinstance(obj, ABCDataFrame):
        return obj.isna()
    elif isinstance(obj, list):
        return _isna_ndarraylike(np.asarray(obj, dtype=object), old=True)
    elif hasattr(obj, "__array__"):
        return _isna_ndarraylike(np.asarray(obj), old=True)
    else:
        return False


_isna = _isna_new


def _use_inf_as_na(key):
    """
    Option change callback for na/inf behaviour.

    Choose which replacement for numpy.isnan / -numpy.isfinite is used.

    Parameters
    ----------
    flag: bool
        True means treat None, NaN, INF, -INF as null (old way),
        False means None and NaN are null, but INF, -INF are not null
        (new way).

    Notes
    -----
    This approach to setting global module values is discussed and
    approved here:

    * https://stackoverflow.com/questions/4859217/
      programmatically-creating-variables-in-python/4859312#4859312
    """
    flag = get_option(key)
    if flag:
        globals()["_isna"] = _isna_old
    else:
        globals()["_isna"] = _isna_new


def _isna_ndarraylike(obj, old: bool = False):
    """
    Return an array indicating which values of the input
    array are NaN / NA.

    Parameters
    ----------
    obj: array-like
        The input array whose elements are to be checked.
    old: bool
        Whether or not to treat infinite values as NA.

    Returns
    -------
    array-like
        Array of boolean values denoting the NA status of
        each element.
    """
    values = getattr(obj, "_values", obj)
    dtype = values.dtype

    if is_extension_array_dtype(dtype):
        if old:
            result = values.isna() | (values == -np.inf) | (values == np.inf)
        else:
            result = values.isna()
    elif is_string_dtype(dtype):
        result = _isna_string_dtype(values, dtype, old=old)
    elif needs_i8_conversion(dtype):
        # this is the NaT pattern
        result = values.view("i8") == iNaT
    else:
        if old:
            result = ~np.isfinite(values)
        else:
            result = np.isnan(values)

    # box
    if isinstance(obj, ABCSeries):
        result = obj._constructor(result, index=obj.index, name=obj.name, copy=False)

    return result


def _isna_string_dtype(values: np.ndarray, dtype: np.dtype, old: bool) -> np.ndarray:
    # Working around NumPy ticket 1542
    shape = values.shape

    if is_string_like_dtype(dtype):
        result = np.zeros(values.shape, dtype=bool)
    else:
        result = np.empty(shape, dtype=bool)
        if old:
            vec = libmissing.isnaobj_old(values.ravel())
        else:
            vec = libmissing.isnaobj(values.ravel())

        result[...] = vec.reshape(shape)

    return result


def notna(obj):
    """
    Detect non-missing values for an array-like object.

    This function takes a scalar or array-like object and indicates
    whether values are valid (not missing, which is ``NaN`` in numeric
    arrays, ``None`` or ``NaN`` in object arrays, ``NaT`` in datetimelike).

    Parameters
    ----------
    obj : array-like or object value
        Object to check for *not* null or *non*-missing values.

    Returns
    -------
    bool or array-like of bool
        For scalar input, returns a scalar boolean.
        For array input, returns an array of boolean indicating whether each
        corresponding element is valid.

    See Also
    --------
    isna : Boolean inverse of pandas.notna.
    Series.notna : Detect valid values in a Series.
    DataFrame.notna : Detect valid values in a DataFrame.
    Index.notna : Detect valid values in an Index.

    Examples
    --------
    Scalar arguments (including strings) result in a scalar boolean.

    >>> pd.notna('dog')
    True

    >>> pd.notna(pd.NA)
    False

    >>> pd.notna(np.nan)
    False

    ndarrays result in an ndarray of booleans.

    >>> array = np.array([[1, np.nan, 3], [4, 5, np.nan]])
    >>> array
    array([[ 1., nan,  3.],
           [ 4.,  5., nan]])
    >>> pd.notna(array)
    array([[ True, False,  True],
           [ True,  True, False]])

    For indexes, an ndarray of booleans is returned.

    >>> index = pd.DatetimeIndex(["2017-07-05", "2017-07-06", None,
    ...                          "2017-07-08"])
    >>> index
    DatetimeIndex(['2017-07-05', '2017-07-06', 'NaT', '2017-07-08'],
                  dtype='datetime64[ns]', freq=None)
    >>> pd.notna(index)
    array([ True,  True, False,  True])

    For Series and DataFrame, the same type is returned, containing booleans.

    >>> df = pd.DataFrame([['ant', 'bee', 'cat'], ['dog', None, 'fly']])
    >>> df
         0     1    2
    0  ant   bee  cat
    1  dog  None  fly
    >>> pd.notna(df)
          0      1     2
    0  True   True  True
    1  True  False  True

    >>> pd.notna(df[1])
    0     True
    1    False
    Name: 1, dtype: bool
    """
    res = isna(obj)
    if is_scalar(res):
        return not res
    return ~res


notnull = notna


def _isna_compat(arr, fill_value=np.nan) -> bool:
    """
    Parameters
    ----------
    arr: a numpy array
    fill_value: fill value, default to np.nan

    Returns
    -------
    True if we can fill using this fill_value
    """
    dtype = arr.dtype
    if isna(fill_value):
        return not (is_bool_dtype(dtype) or is_integer_dtype(dtype))
    return True


def array_equivalent(left, right, strict_nan: bool = False) -> bool:
    """
    True if two arrays, left and right, have equal non-NaN elements, and NaNs
    in corresponding locations.  False otherwise. It is assumed that left and
    right are NumPy arrays of the same dtype. The behavior of this function
    (particularly with respect to NaNs) is not defined if the dtypes are
    different.

    Parameters
    ----------
    left, right : ndarrays
    strict_nan : bool, default False
        If True, consider NaN and None to be different.

    Returns
    -------
    b : bool
        Returns True if the arrays are equivalent.

    Examples
    --------
    >>> array_equivalent(
    ...     np.array([1, 2, np.nan]),
    ...     np.array([1, 2, np.nan]))
    True
    >>> array_equivalent(
    ...     np.array([1, np.nan, 2]),
    ...     np.array([1, 2, np.nan]))
    False
    """
    left, right = np.asarray(left), np.asarray(right)

    # shape compat
    if left.shape != right.shape:
        return False

    # Object arrays can contain None, NaN and NaT.
    # string dtypes must be come to this path for NumPy 1.7.1 compat
    if is_string_dtype(left) or is_string_dtype(right):

        if not strict_nan:
            # isna considers NaN and None to be equivalent.
            return lib.array_equivalent_object(
                ensure_object(left.ravel()), ensure_object(right.ravel())
            )

        for left_value, right_value in zip(left, right):
            if left_value is NaT and right_value is not NaT:
                return False

            elif left_value is libmissing.NA and right_value is not libmissing.NA:
                return False

            elif isinstance(left_value, float) and np.isnan(left_value):
                if not isinstance(right_value, float) or not np.isnan(right_value):
                    return False
            else:
                try:
                    if np.any(np.asarray(left_value != right_value)):
                        return False
                except TypeError as err:
                    if "Cannot compare tz-naive" in str(err):
                        # tzawareness compat failure, see GH#28507
                        return False
                    elif "boolean value of NA is ambiguous" in str(err):
                        return False
                    raise
        return True

    # NaNs can occur in float and complex arrays.
    if is_float_dtype(left) or is_complex_dtype(left):

        # empty
        if not (np.prod(left.shape) and np.prod(right.shape)):
            return True
        return ((left == right) | (isna(left) & isna(right))).all()

    elif is_datetimelike_v_numeric(left, right):
        # GH#29553 avoid numpy deprecation warning
        return False

    elif needs_i8_conversion(left) or needs_i8_conversion(right):
        # datetime64, timedelta64, Period
        if not is_dtype_equal(left.dtype, right.dtype):
            return False

        left = left.view("i8")
        right = right.view("i8")

    # if we have structured dtypes, compare first
    if left.dtype.type is np.void or right.dtype.type is np.void:
        if left.dtype != right.dtype:
            return False

    return np.array_equal(left, right)


def _infer_fill_value(val):
    """
    infer the fill value for the nan/NaT from the provided
    scalar/ndarray/list-like if we are a NaT, return the correct dtyped
    element to provide proper block construction
    """
    if not is_list_like(val):
        val = [val]
    val = np.array(val, copy=False)
    if needs_i8_conversion(val):
        return np.array("NaT", dtype=val.dtype)
    elif is_object_dtype(val.dtype):
        dtype = lib.infer_dtype(ensure_object(val), skipna=False)
        if dtype in ["datetime", "datetime64"]:
            return np.array("NaT", dtype=DT64NS_DTYPE)
        elif dtype in ["timedelta", "timedelta64"]:
            return np.array("NaT", dtype=TD64NS_DTYPE)
    return np.nan


def _maybe_fill(arr, fill_value=np.nan):
    """
    if we have a compatible fill_value and arr dtype, then fill
    """
    if _isna_compat(arr, fill_value):
        arr.fill(fill_value)
    return arr


def na_value_for_dtype(dtype, compat: bool = True):
    """
    Return a dtype compat na value

    Parameters
    ----------
    dtype : string / dtype
    compat : bool, default True

    Returns
    -------
    np.dtype or a pandas dtype

    Examples
    --------
    >>> na_value_for_dtype(np.dtype('int64'))
    0
    >>> na_value_for_dtype(np.dtype('int64'), compat=False)
    nan
    >>> na_value_for_dtype(np.dtype('float64'))
    nan
    >>> na_value_for_dtype(np.dtype('bool'))
    False
    >>> na_value_for_dtype(np.dtype('datetime64[ns]'))
    NaT
    """
    dtype = pandas_dtype(dtype)

    if is_extension_array_dtype(dtype):
        return dtype.na_value
    if needs_i8_conversion(dtype):
        return NaT
    elif is_float_dtype(dtype):
        return np.nan
    elif is_integer_dtype(dtype):
        if compat:
            return 0
        return np.nan
    elif is_bool_dtype(dtype):
        return False
    return np.nan


def remove_na_arraylike(arr):
    """
    Return array-like containing only true/non-NaN values, possibly empty.
    """
    if is_extension_array_dtype(arr):
        return arr[notna(arr)]
    else:
        return arr[notna(np.asarray(arr))]


def is_valid_nat_for_dtype(obj, dtype: DtypeObj) -> bool:
    """
    isna check that excludes incompatible dtypes

    Parameters
    ----------
    obj : object
    dtype : np.datetime64, np.timedelta64, DatetimeTZDtype, or PeriodDtype

    Returns
    -------
    bool
    """
    if not lib.is_scalar(obj) or not isna(obj):
        return False
    if dtype.kind == "M":
        return not isinstance(obj, np.timedelta64)
    if dtype.kind == "m":
        return not isinstance(obj, np.datetime64)

    # must be PeriodDType
    return not isinstance(obj, (np.datetime64, np.timedelta64))
