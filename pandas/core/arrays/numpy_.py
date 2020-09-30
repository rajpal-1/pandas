import numbers
from typing import Tuple, Type, Union

import numpy as np
from numpy.lib.mixins import NDArrayOperatorsMixin

from pandas._libs import lib
from pandas._typing import Scalar
from pandas.compat.numpy import function as nv

from pandas.core.dtypes.dtypes import ExtensionDtype
from pandas.core.dtypes.missing import isna

from pandas import compat
from pandas.core import nanops, ops
from pandas.core.array_algos import masked_reductions
from pandas.core.arrays._mixins import NDArrayBackedExtensionArray
from pandas.core.arrays.base import ExtensionOpsMixin
from pandas.core.strings.object_array import ObjectStringArrayMixin


class PandasDtype(ExtensionDtype):
    """
    A Pandas ExtensionDtype for NumPy dtypes.

    .. versionadded:: 0.24.0

    This is mostly for internal compatibility, and is not especially
    useful on its own.

    Parameters
    ----------
    dtype : object
        Object to be converted to a NumPy data type object.

    See Also
    --------
    numpy.dtype
    """

    _metadata = ("_dtype",)

    def __init__(self, dtype: object):
        self._dtype = np.dtype(dtype)

    def __repr__(self) -> str:
        return f"PandasDtype({repr(self.name)})"

    @property
    def numpy_dtype(self) -> np.dtype:
        """
        The NumPy dtype this PandasDtype wraps.
        """
        return self._dtype

    @property
    def name(self) -> str:
        """
        A bit-width name for this data-type.
        """
        return self._dtype.name

    @property
    def type(self) -> Type[np.generic]:
        """
        The type object used to instantiate a scalar of this NumPy data-type.
        """
        return self._dtype.type

    @property
    def _is_numeric(self) -> bool:
        # exclude object, str, unicode, void.
        return self.kind in set("biufc")

    @property
    def _is_boolean(self) -> bool:
        return self.kind == "b"

    @classmethod
    def construct_from_string(cls, string: str) -> "PandasDtype":
        try:
            dtype = np.dtype(string)
        except TypeError as err:
            if not isinstance(string, str):
                msg = f"'construct_from_string' expects a string, got {type(string)}"
            else:
                msg = f"Cannot construct a 'PandasDtype' from '{string}'"
            raise TypeError(msg) from err
        return cls(dtype)

    @classmethod
    def construct_array_type(cls) -> Type["PandasArray"]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        return PandasArray

    @property
    def kind(self) -> str:
        """
        A character code (one of 'biufcmMOSUV') identifying the general kind of data.
        """
        return self._dtype.kind

    @property
    def itemsize(self) -> int:
        """
        The element size of this data-type object.
        """
        return self._dtype.itemsize


class PandasArray(
    NDArrayBackedExtensionArray,
    ExtensionOpsMixin,
    NDArrayOperatorsMixin,
    ObjectStringArrayMixin,
):
    """
    A pandas ExtensionArray for NumPy data.

    .. versionadded:: 0.24.0

    This is mostly for internal compatibility, and is not especially
    useful on its own.

    Parameters
    ----------
    values : ndarray
        The NumPy ndarray to wrap. Must be 1-dimensional.
    copy : bool, default False
        Whether to copy `values`.

    Attributes
    ----------
    None

    Methods
    -------
    None
    """

    # If you're wondering why pd.Series(cls) doesn't put the array in an
    # ExtensionBlock, search for `ABCPandasArray`. We check for
    # that _typ to ensure that that users don't unnecessarily use EAs inside
    # pandas internals, which turns off things like block consolidation.
    _typ = "npy_extension"
    __array_priority__ = 1000
    _ndarray: np.ndarray

    # ------------------------------------------------------------------------
    # Constructors

    def __init__(self, values: Union[np.ndarray, "PandasArray"], copy: bool = False):
        if isinstance(values, type(self)):
            values = values._ndarray
        if not isinstance(values, np.ndarray):
            raise ValueError(
                f"'values' must be a NumPy array, not {type(values).__name__}"
            )

        if values.ndim != 1:
            raise ValueError("PandasArray must be 1-dimensional.")

        if copy:
            values = values.copy()

        self._ndarray = values
        self._dtype = PandasDtype(values.dtype)

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy: bool = False) -> "PandasArray":
        if isinstance(dtype, PandasDtype):
            dtype = dtype._dtype

        result = np.asarray(scalars, dtype=dtype)
        if copy and result is scalars:
            result = result.copy()
        return cls(result)

    @classmethod
    def _from_factorized(cls, values, original) -> "PandasArray":
        return cls(values)

    def _from_backing_data(self, arr: np.ndarray) -> "PandasArray":
        return type(self)(arr)

    # ------------------------------------------------------------------------
    # Data

    @property
    def dtype(self) -> PandasDtype:
        return self._dtype

    # ------------------------------------------------------------------------
    # NumPy Array Interface

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self._ndarray, dtype=dtype)

    _HANDLED_TYPES = (np.ndarray, numbers.Number)

    def __array_ufunc__(self, ufunc, method: str, *inputs, **kwargs):
        # Lightly modified version of
        # https://numpy.org/doc/stable/reference/generated/numpy.lib.mixins.NDArrayOperatorsMixin.html
        # The primary modification is not boxing scalar return values
        # in PandasArray, since pandas' ExtensionArrays are 1-d.
        out = kwargs.get("out", ())
        for x in inputs + out:
            # Only support operations with instances of _HANDLED_TYPES.
            # Use PandasArray instead of type(self) for isinstance to
            # allow subclasses that don't override __array_ufunc__ to
            # handle PandasArray objects.
            if not isinstance(x, self._HANDLED_TYPES + (PandasArray,)):
                return NotImplemented

        # Defer to the implementation of the ufunc on unwrapped values.
        inputs = tuple(x._ndarray if isinstance(x, PandasArray) else x for x in inputs)
        if out:
            kwargs["out"] = tuple(
                x._ndarray if isinstance(x, PandasArray) else x for x in out
            )
        result = getattr(ufunc, method)(*inputs, **kwargs)

        if type(result) is tuple and len(result):
            # multiple return values
            if not lib.is_scalar(result[0]):
                # re-box array-like results
                return tuple(type(self)(x) for x in result)
            else:
                # but not scalar reductions
                return result
        elif method == "at":
            # no return value
            return None
        else:
            # one return value
            if not lib.is_scalar(result):
                # re-box array-like results, but not scalar reductions
                result = type(self)(result)
            return result

    # ------------------------------------------------------------------------
    # Pandas ExtensionArray Interface

    def isna(self) -> np.ndarray:
        return isna(self._ndarray)

    def _validate_fill_value(self, fill_value):
        if fill_value is None:
            # Primarily for subclasses
            fill_value = self.dtype.na_value
        return fill_value

    def _values_for_factorize(self) -> Tuple[np.ndarray, int]:
        return self._ndarray, -1

    # ------------------------------------------------------------------------
    # Reductions

    def any(self, axis=None, out=None, keepdims=False, skipna=True):
        nv.validate_any((), dict(out=out, keepdims=keepdims))
        return nanops.nanany(self._ndarray, axis=axis, skipna=skipna)

    def all(self, axis=None, out=None, keepdims=False, skipna=True):
        nv.validate_all((), dict(out=out, keepdims=keepdims))
        return nanops.nanall(self._ndarray, axis=axis, skipna=skipna)

    def min(self, skipna: bool = True, **kwargs) -> Scalar:
        nv.validate_min((), kwargs)
        result = masked_reductions.min(
            values=self.to_numpy(), mask=self.isna(), skipna=skipna
        )
        return result

    def max(self, skipna: bool = True, **kwargs) -> Scalar:
        nv.validate_max((), kwargs)
        result = masked_reductions.max(
            values=self.to_numpy(), mask=self.isna(), skipna=skipna
        )
        return result

    def sum(self, axis=None, skipna=True, min_count=0, **kwargs) -> Scalar:
        nv.validate_sum((), kwargs)
        return nanops.nansum(
            self._ndarray, axis=axis, skipna=skipna, min_count=min_count
        )

    def prod(self, axis=None, skipna=True, min_count=0, **kwargs) -> Scalar:
        nv.validate_prod((), kwargs)
        return nanops.nanprod(
            self._ndarray, axis=axis, skipna=skipna, min_count=min_count
        )

    def mean(self, axis=None, dtype=None, out=None, keepdims=False, skipna=True):
        nv.validate_mean((), dict(dtype=dtype, out=out, keepdims=keepdims))
        return nanops.nanmean(self._ndarray, axis=axis, skipna=skipna)

    def median(
        self, axis=None, out=None, overwrite_input=False, keepdims=False, skipna=True
    ):
        nv.validate_median(
            (), dict(out=out, overwrite_input=overwrite_input, keepdims=keepdims)
        )
        return nanops.nanmedian(self._ndarray, axis=axis, skipna=skipna)

    def std(self, axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True):
        nv.validate_stat_ddof_func(
            (), dict(dtype=dtype, out=out, keepdims=keepdims), fname="std"
        )
        return nanops.nanstd(self._ndarray, axis=axis, skipna=skipna, ddof=ddof)

    def var(self, axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True):
        nv.validate_stat_ddof_func(
            (), dict(dtype=dtype, out=out, keepdims=keepdims), fname="var"
        )
        return nanops.nanvar(self._ndarray, axis=axis, skipna=skipna, ddof=ddof)

    def sem(self, axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True):
        nv.validate_stat_ddof_func(
            (), dict(dtype=dtype, out=out, keepdims=keepdims), fname="sem"
        )
        return nanops.nansem(self._ndarray, axis=axis, skipna=skipna, ddof=ddof)

    def kurt(self, axis=None, dtype=None, out=None, keepdims=False, skipna=True):
        nv.validate_stat_ddof_func(
            (), dict(dtype=dtype, out=out, keepdims=keepdims), fname="kurt"
        )
        return nanops.nankurt(self._ndarray, axis=axis, skipna=skipna)

    def skew(self, axis=None, dtype=None, out=None, keepdims=False, skipna=True):
        nv.validate_stat_ddof_func(
            (), dict(dtype=dtype, out=out, keepdims=keepdims), fname="skew"
        )
        return nanops.nanskew(self._ndarray, axis=axis, skipna=skipna)

    # ------------------------------------------------------------------------
    # Additional Methods

    def to_numpy(
        self, dtype=None, copy: bool = False, na_value=lib.no_default
    ) -> np.ndarray:
        result = np.asarray(self._ndarray, dtype=dtype)

        if (copy or na_value is not lib.no_default) and result is self._ndarray:
            result = result.copy()

        if na_value is not lib.no_default:
            result[self.isna()] = na_value

        return result

    # ------------------------------------------------------------------------
    # Ops

    def __invert__(self):
        return type(self)(~self._ndarray)

    @classmethod
    def _create_arithmetic_method(cls, op):
        @ops.unpack_zerodim_and_defer(op.__name__)
        def arithmetic_method(self, other):
            if isinstance(other, cls):
                other = other._ndarray

            with np.errstate(all="ignore"):
                result = op(self._ndarray, other)

            if op is divmod:
                a, b = result
                return cls(a), cls(b)

            return cls(result)

        return compat.set_function_name(arithmetic_method, f"__{op.__name__}__", cls)

    _create_comparison_method = _create_arithmetic_method

    # ------------------------------------------------------------------------
    # String methods interface
    _str_na_value = np.nan


PandasArray._add_arithmetic_ops()
PandasArray._add_comparison_ops()
