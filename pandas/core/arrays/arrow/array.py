from __future__ import annotations

import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Sequence,
    TypeVar,
    cast,
)

import numpy as np

from pandas._libs import (
    lib,
    missing as libmissing,
)
from pandas._typing import (
    ArrayLike,
    AxisInt,
    Dtype,
    FillnaOptions,
    Iterator,
    NpDtype,
    PositionalIndexer,
    Scalar,
    SortKind,
    TakeIndexer,
    npt,
)
from pandas.compat import (
    pa_version_under6p0,
    pa_version_under7p0,
    pa_version_under9p0,
)
from pandas.util._decorators import doc
from pandas.util._validators import validate_fillna_kwargs

from pandas.core.dtypes.common import (
    is_array_like,
    is_bool_dtype,
    is_integer,
    is_integer_dtype,
    is_object_dtype,
    is_scalar,
)
from pandas.core.dtypes.missing import isna

from pandas.core.arraylike import OpsMixin
from pandas.core.arrays.base import ExtensionArray
import pandas.core.common as com
from pandas.core.indexers import (
    check_array_indexer,
    unpack_tuple_and_ellipses,
    validate_indices,
)
from pandas.core.strings.object_array import ObjectStringArrayMixin

if not pa_version_under6p0:
    import pyarrow as pa
    import pyarrow.compute as pc

    from pandas.core.arrays.arrow._arrow_utils import fallback_performancewarning
    from pandas.core.arrays.arrow.dtype import ArrowDtype

    ARROW_CMP_FUNCS = {
        "eq": pc.equal,
        "ne": pc.not_equal,
        "lt": pc.less,
        "gt": pc.greater,
        "le": pc.less_equal,
        "ge": pc.greater_equal,
    }

    ARROW_LOGICAL_FUNCS = {
        "and": pc.and_kleene,
        "rand": lambda x, y: pc.and_kleene(y, x),
        "or": pc.or_kleene,
        "ror": lambda x, y: pc.or_kleene(y, x),
        "xor": pc.xor,
        "rxor": lambda x, y: pc.xor(y, x),
    }

    def cast_for_truediv(
        arrow_array: pa.ChunkedArray, pa_object: pa.Array | pa.Scalar
    ) -> pa.ChunkedArray:
        # Ensure int / int -> float mirroring Python/Numpy behavior
        # as pc.divide_checked(int, int) -> int
        if pa.types.is_integer(arrow_array.type) and pa.types.is_integer(
            pa_object.type
        ):
            return arrow_array.cast(pa.float64())
        return arrow_array

    def floordiv_compat(
        left: pa.ChunkedArray | pa.Array | pa.Scalar,
        right: pa.ChunkedArray | pa.Array | pa.Scalar,
    ) -> pa.ChunkedArray:
        # Ensure int // int -> int mirroring Python/Numpy behavior
        # as pc.floor(pc.divide_checked(int, int)) -> float
        result = pc.floor(pc.divide_checked(left, right))
        if pa.types.is_integer(left.type) and pa.types.is_integer(right.type):
            result = result.cast(left.type)
        return result

    ARROW_ARITHMETIC_FUNCS = {
        "add": pc.add_checked,
        "radd": lambda x, y: pc.add_checked(y, x),
        "sub": pc.subtract_checked,
        "rsub": lambda x, y: pc.subtract_checked(y, x),
        "mul": pc.multiply_checked,
        "rmul": lambda x, y: pc.multiply_checked(y, x),
        "truediv": lambda x, y: pc.divide_checked(cast_for_truediv(x, y), y),
        "rtruediv": lambda x, y: pc.divide_checked(y, cast_for_truediv(x, y)),
        "floordiv": lambda x, y: floordiv_compat(x, y),
        "rfloordiv": lambda x, y: floordiv_compat(y, x),
        "mod": NotImplemented,
        "rmod": NotImplemented,
        "divmod": NotImplemented,
        "rdivmod": NotImplemented,
        "pow": pc.power_checked,
        "rpow": lambda x, y: pc.power_checked(y, x),
    }

if TYPE_CHECKING:
    from pandas import Series

ArrowExtensionArrayT = TypeVar("ArrowExtensionArrayT", bound="ArrowExtensionArray")


def to_pyarrow_type(
    dtype: ArrowDtype | pa.DataType | Dtype | None,
) -> pa.DataType | None:
    """
    Convert dtype to a pyarrow type instance.
    """
    if isinstance(dtype, ArrowDtype):
        pa_dtype = dtype.pyarrow_dtype
    elif isinstance(dtype, pa.DataType):
        pa_dtype = dtype
    elif dtype:
        # Accepts python types too
        pa_dtype = pa.from_numpy_dtype(dtype)
    else:
        pa_dtype = None
    return pa_dtype


class ArrowExtensionArray(OpsMixin, ObjectStringArrayMixin, ExtensionArray):
    """
    Pandas ExtensionArray backed by a PyArrow ChunkedArray.

    .. warning::

       ArrowExtensionArray is considered experimental. The implementation and
       parts of the API may change without warning.

    Parameters
    ----------
    values : pyarrow.Array or pyarrow.ChunkedArray

    Attributes
    ----------
    None

    Methods
    -------
    None

    Returns
    -------
    ArrowExtensionArray

    Notes
    -----
    Most methods are implemented using `pyarrow compute functions. <https://arrow.apache.org/docs/python/api/compute.html>`__
    Some methods may either raise an exception or raise a ``PerformanceWarning`` if an
    associated compute function is not available based on the installed version of PyArrow.

    Please install the latest version of PyArrow to enable the best functionality and avoid
    potential bugs in prior versions of PyArrow.

    Examples
    --------
    Create an ArrowExtensionArray with :func:`pandas.array`:

    >>> pd.array([1, 1, None], dtype="int64[pyarrow]")
    <ArrowExtensionArray>
    [1, 1, <NA>]
    Length: 3, dtype: int64[pyarrow]
    """  # noqa: E501 (http link too long)

    _data: pa.ChunkedArray
    _dtype: ArrowDtype

    def __init__(self, values: pa.Array | pa.ChunkedArray) -> None:
        if pa_version_under6p0:
            msg = "pyarrow>=6.0.0 is required for PyArrow backed ArrowExtensionArray."
            raise ImportError(msg)
        if isinstance(values, pa.Array):
            self._data = pa.chunked_array([values])
        elif isinstance(values, pa.ChunkedArray):
            self._data = values
        else:
            raise ValueError(
                f"Unsupported type '{type(values)}' for ArrowExtensionArray"
            )
        self._dtype = ArrowDtype(self._data.type)
        assert self._dtype.na_value is self._str_na_value

    @classmethod
    def _from_sequence(cls, scalars, *, dtype: Dtype | None = None, copy: bool = False):
        """
        Construct a new ExtensionArray from a sequence of scalars.
        """
        pa_dtype = to_pyarrow_type(dtype)
        is_cls = isinstance(scalars, cls)
        if is_cls or isinstance(scalars, (pa.Array, pa.ChunkedArray)):
            if is_cls:
                scalars = scalars._data
            if pa_dtype:
                scalars = scalars.cast(pa_dtype)
            return cls(scalars)
        else:
            return cls(
                pa.chunked_array(pa.array(scalars, type=pa_dtype, from_pandas=True))
            )

    @classmethod
    def _from_sequence_of_strings(
        cls, strings, *, dtype: Dtype | None = None, copy: bool = False
    ):
        """
        Construct a new ExtensionArray from a sequence of strings.
        """
        pa_type = to_pyarrow_type(dtype)
        if (
            pa_type is None
            or pa.types.is_binary(pa_type)
            or pa.types.is_string(pa_type)
        ):
            # pa_type is None: Let pa.array infer
            # pa_type is string/binary: scalars already correct type
            scalars = strings
        elif pa.types.is_timestamp(pa_type):
            from pandas.core.tools.datetimes import to_datetime

            scalars = to_datetime(strings, errors="raise")
        elif pa.types.is_date(pa_type):
            from pandas.core.tools.datetimes import to_datetime

            scalars = to_datetime(strings, errors="raise").date
        elif pa.types.is_duration(pa_type):
            from pandas.core.tools.timedeltas import to_timedelta

            scalars = to_timedelta(strings, errors="raise")
        elif pa.types.is_time(pa_type):
            from pandas.core.tools.times import to_time

            # "coerce" to allow "null times" (None) to not raise
            scalars = to_time(strings, errors="coerce")
        elif pa.types.is_boolean(pa_type):
            from pandas.core.arrays import BooleanArray

            scalars = BooleanArray._from_sequence_of_strings(strings).to_numpy()
        elif (
            pa.types.is_integer(pa_type)
            or pa.types.is_floating(pa_type)
            or pa.types.is_decimal(pa_type)
        ):
            from pandas.core.tools.numeric import to_numeric

            scalars = to_numeric(strings, errors="raise")
        else:
            raise NotImplementedError(
                f"Converting strings to {pa_type} is not implemented."
            )
        return cls._from_sequence(scalars, dtype=pa_type, copy=copy)

    def __getitem__(self, item: PositionalIndexer):
        """Select a subset of self.

        Parameters
        ----------
        item : int, slice, or ndarray
            * int: The position in 'self' to get.
            * slice: A slice object, where 'start', 'stop', and 'step' are
              integers or None
            * ndarray: A 1-d boolean NumPy ndarray the same length as 'self'

        Returns
        -------
        item : scalar or ExtensionArray

        Notes
        -----
        For scalar ``item``, return a scalar value suitable for the array's
        type. This should be an instance of ``self.dtype.type``.
        For slice ``key``, return an instance of ``ExtensionArray``, even
        if the slice is length 0 or 1.
        For a boolean mask, return an instance of ``ExtensionArray``, filtered
        to the values where ``item`` is True.
        """
        item = check_array_indexer(self, item)

        if isinstance(item, np.ndarray):
            if not len(item):
                # Removable once we migrate StringDtype[pyarrow] to ArrowDtype[string]
                if self._dtype.name == "string" and self._dtype.storage == "pyarrow":
                    pa_dtype = pa.string()
                else:
                    pa_dtype = self._dtype.pyarrow_dtype
                return type(self)(pa.chunked_array([], type=pa_dtype))
            elif is_integer_dtype(item.dtype):
                return self.take(item)
            elif is_bool_dtype(item.dtype):
                return type(self)(self._data.filter(item))
            else:
                raise IndexError(
                    "Only integers, slices and integer or "
                    "boolean arrays are valid indices."
                )
        elif isinstance(item, tuple):
            item = unpack_tuple_and_ellipses(item)

        # error: Non-overlapping identity check (left operand type:
        # "Union[Union[int, integer[Any]], Union[slice, List[int],
        # ndarray[Any, Any]]]", right operand type: "ellipsis")
        if item is Ellipsis:  # type: ignore[comparison-overlap]
            # TODO: should be handled by pyarrow?
            item = slice(None)

        if is_scalar(item) and not is_integer(item):
            # e.g. "foo" or 2.5
            # exception message copied from numpy
            raise IndexError(
                r"only integers, slices (`:`), ellipsis (`...`), numpy.newaxis "
                r"(`None`) and integer or boolean arrays are valid indices"
            )
        # We are not an array indexer, so maybe e.g. a slice or integer
        # indexer. We dispatch to pyarrow.
        value = self._data[item]
        if isinstance(value, pa.ChunkedArray):
            return type(self)(value)
        else:
            scalar = value.as_py()
            if scalar is None:
                return self._dtype.na_value
            else:
                return scalar

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over elements of the array.
        """
        na_value = self._dtype.na_value
        for value in self._data:
            val = value.as_py()
            if val is None:
                yield na_value
            else:
                yield val

    def __arrow_array__(self, type=None):
        """Convert myself to a pyarrow ChunkedArray."""
        return self._data

    def __array__(self, dtype: NpDtype | None = None) -> np.ndarray:
        """Correctly construct numpy arrays when passed to `np.asarray()`."""
        return self.to_numpy(dtype=dtype)

    def __invert__(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        return type(self)(pc.invert(self._data))

    def __neg__(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        return type(self)(pc.negate_checked(self._data))

    def __pos__(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        return type(self)(self._data)

    def __abs__(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        return type(self)(pc.abs_checked(self._data))

    # GH 42600: __getstate__/__setstate__ not necessary once
    # https://issues.apache.org/jira/browse/ARROW-10739 is addressed
    def __getstate__(self):
        state = self.__dict__.copy()
        state["_data"] = self._data.combine_chunks()
        return state

    def __setstate__(self, state) -> None:
        state["_data"] = pa.chunked_array(state["_data"])
        self.__dict__.update(state)

    def _cmp_method(self, other, op):
        from pandas.arrays import BooleanArray

        pc_func = ARROW_CMP_FUNCS[op.__name__]
        if isinstance(other, ArrowExtensionArray):
            result = pc_func(self._data, other._data)
        elif isinstance(other, (np.ndarray, list)):
            result = pc_func(self._data, other)
        elif is_scalar(other):
            try:
                result = pc_func(self._data, pa.scalar(other))
            except (pa.lib.ArrowNotImplementedError, pa.lib.ArrowInvalid):
                mask = isna(self) | isna(other)
                valid = ~mask
                result = np.zeros(len(self), dtype="bool")
                result[valid] = op(np.array(self)[valid], other)
                return BooleanArray(result, mask)
        else:
            raise NotImplementedError(
                f"{op.__name__} not implemented for {type(other)}"
            )

        result = result.to_numpy()
        return BooleanArray._from_sequence(result)

    def _evaluate_op_method(self, other, op, arrow_funcs):
        pc_func = arrow_funcs[op.__name__]
        if pc_func is NotImplemented:
            raise NotImplementedError(f"{op.__name__} not implemented.")
        if isinstance(other, ArrowExtensionArray):
            result = pc_func(self._data, other._data)
        elif isinstance(other, (np.ndarray, list)):
            result = pc_func(self._data, pa.array(other, from_pandas=True))
        elif is_scalar(other):
            result = pc_func(self._data, pa.scalar(other))
        else:
            raise NotImplementedError(
                f"{op.__name__} not implemented for {type(other)}"
            )
        return type(self)(result)

    def _logical_method(self, other, op):
        return self._evaluate_op_method(other, op, ARROW_LOGICAL_FUNCS)

    def _arith_method(self, other, op):
        return self._evaluate_op_method(other, op, ARROW_ARITHMETIC_FUNCS)

    def equals(self, other) -> bool:
        if not isinstance(other, ArrowExtensionArray):
            return False
        # I'm told that pyarrow makes __eq__ behave like pandas' equals;
        #  TODO: is this documented somewhere?
        return self._data == other._data

    @property
    def dtype(self) -> ArrowDtype:
        """
        An instance of 'ExtensionDtype'.
        """
        return self._dtype

    @property
    def nbytes(self) -> int:
        """
        The number of bytes needed to store this object in memory.
        """
        return self._data.nbytes

    def __len__(self) -> int:
        """
        Length of this array.

        Returns
        -------
        length : int
        """
        return len(self._data)

    @property
    def _hasna(self) -> bool:
        return self._data.null_count > 0

    def isna(self) -> npt.NDArray[np.bool_]:
        """
        Boolean NumPy array indicating if each value is missing.

        This should return a 1-D array the same length as 'self'.
        """
        return self._data.is_null().to_numpy()

    def argsort(
        self,
        *,
        ascending: bool = True,
        kind: SortKind = "quicksort",
        na_position: str = "last",
        **kwargs,
    ) -> np.ndarray:
        order = "ascending" if ascending else "descending"
        null_placement = {"last": "at_end", "first": "at_start"}.get(na_position, None)
        if null_placement is None or pa_version_under7p0:
            # Although pc.array_sort_indices exists in version 6
            # there's a bug that affects the pa.ChunkedArray backing
            # https://issues.apache.org/jira/browse/ARROW-12042
            fallback_performancewarning("7")
            return super().argsort(
                ascending=ascending, kind=kind, na_position=na_position
            )

        result = pc.array_sort_indices(
            self._data, order=order, null_placement=null_placement
        )
        np_result = result.to_numpy()
        return np_result.astype(np.intp, copy=False)

    def _argmin_max(self, skipna: bool, method: str) -> int:
        if self._data.length() in (0, self._data.null_count) or (
            self._hasna and not skipna
        ):
            # For empty or all null, pyarrow returns -1 but pandas expects TypeError
            # For skipna=False and data w/ null, pandas expects NotImplementedError
            # let ExtensionArray.arg{max|min} raise
            return getattr(super(), f"arg{method}")(skipna=skipna)

        if pa_version_under6p0:
            raise NotImplementedError(
                f"arg{method} only implemented for pyarrow version >= 6.0"
            )

        value = getattr(pc, method)(self._data, skip_nulls=skipna)
        return pc.index(self._data, value).as_py()

    def argmin(self, skipna: bool = True) -> int:
        return self._argmin_max(skipna, "min")

    def argmax(self, skipna: bool = True) -> int:
        return self._argmin_max(skipna, "max")

    def copy(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        """
        Return a shallow copy of the array.

        Underlying ChunkedArray is immutable, so a deep copy is unnecessary.

        Returns
        -------
        type(self)
        """
        return type(self)(self._data)

    def dropna(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        """
        Return ArrowExtensionArray without NA values.

        Returns
        -------
        ArrowExtensionArray
        """
        if pa_version_under6p0:
            fallback_performancewarning(version="6")
            return super().dropna()
        else:
            return type(self)(pc.drop_null(self._data))

    @doc(ExtensionArray.fillna)
    def fillna(
        self: ArrowExtensionArrayT,
        value: object | ArrayLike | None = None,
        method: FillnaOptions | None = None,
        limit: int | None = None,
    ) -> ArrowExtensionArrayT:

        value, method = validate_fillna_kwargs(value, method)

        if limit is not None:
            return super().fillna(value=value, method=method, limit=limit)

        if method is not None and pa_version_under7p0:
            # fill_null_{forward|backward} added in pyarrow 7.0
            fallback_performancewarning(version="7")
            return super().fillna(value=value, method=method, limit=limit)

        if is_array_like(value):
            value = cast(ArrayLike, value)
            if len(value) != len(self):
                raise ValueError(
                    f"Length of 'value' does not match. Got ({len(value)}) "
                    f" expected {len(self)}"
                )

        def convert_fill_value(value, pa_type, dtype):
            if value is None:
                return value
            if isinstance(value, (pa.Scalar, pa.Array, pa.ChunkedArray)):
                return value
            if is_array_like(value):
                pa_box = pa.array
            else:
                pa_box = pa.scalar
            try:
                value = pa_box(value, type=pa_type, from_pandas=True)
            except pa.ArrowTypeError as err:
                msg = f"Invalid value '{str(value)}' for dtype {dtype}"
                raise TypeError(msg) from err
            return value

        fill_value = convert_fill_value(value, self._data.type, self.dtype)

        try:
            if method is None:
                return type(self)(pc.fill_null(self._data, fill_value=fill_value))
            elif method == "pad":
                return type(self)(pc.fill_null_forward(self._data))
            elif method == "backfill":
                return type(self)(pc.fill_null_backward(self._data))
        except pa.ArrowNotImplementedError:
            # ArrowNotImplementedError: Function 'coalesce' has no kernel
            #   matching input types (duration[ns], duration[ns])
            # TODO: remove try/except wrapper if/when pyarrow implements
            #   a kernel for duration types.
            pass

        return super().fillna(value=value, method=method, limit=limit)

    def isin(self, values) -> npt.NDArray[np.bool_]:
        # short-circuit to return all False array.
        if not len(values):
            return np.zeros(len(self), dtype=bool)

        result = pc.is_in(self._data, value_set=pa.array(values, from_pandas=True))
        # pyarrow 2.0.0 returned nulls, so we explicitly specify dtype to convert nulls
        # to False
        return np.array(result, dtype=np.bool_)

    def _values_for_factorize(self) -> tuple[np.ndarray, Any]:
        """
        Return an array and missing value suitable for factorization.

        Returns
        -------
        values : ndarray
        na_value : pd.NA

        Notes
        -----
        The values returned by this method are also used in
        :func:`pandas.util.hash_pandas_object`.
        """
        values = self._data.to_numpy()
        return values, self.dtype.na_value

    @doc(ExtensionArray.factorize)
    def factorize(
        self,
        use_na_sentinel: bool = True,
    ) -> tuple[np.ndarray, ExtensionArray]:
        null_encoding = "mask" if use_na_sentinel else "encode"
        encoded = self._data.dictionary_encode(null_encoding=null_encoding)
        if encoded.length() == 0:
            indices = np.array([], dtype=np.intp)
            uniques = type(self)(pa.chunked_array([], type=encoded.type.value_type))
        else:
            pa_indices = encoded.combine_chunks().indices
            if pa_indices.null_count > 0:
                pa_indices = pc.fill_null(pa_indices, -1)
            indices = pa_indices.to_numpy(zero_copy_only=False, writable=True).astype(
                np.intp, copy=False
            )
            uniques = type(self)(encoded.chunk(0).dictionary)
        return indices, uniques

    def reshape(self, *args, **kwargs):
        raise NotImplementedError(
            f"{type(self)} does not support reshape "
            f"as backed by a 1D pyarrow.ChunkedArray."
        )

    def take(
        self,
        indices: TakeIndexer,
        allow_fill: bool = False,
        fill_value: Any = None,
    ) -> ArrowExtensionArray:
        """
        Take elements from an array.

        Parameters
        ----------
        indices : sequence of int or one-dimensional np.ndarray of int
            Indices to be taken.
        allow_fill : bool, default False
            How to handle negative values in `indices`.

            * False: negative values in `indices` indicate positional indices
              from the right (the default). This is similar to
              :func:`numpy.take`.

            * True: negative values in `indices` indicate
              missing values. These values are set to `fill_value`. Any other
              other negative values raise a ``ValueError``.

        fill_value : any, optional
            Fill value to use for NA-indices when `allow_fill` is True.
            This may be ``None``, in which case the default NA value for
            the type, ``self.dtype.na_value``, is used.

            For many ExtensionArrays, there will be two representations of
            `fill_value`: a user-facing "boxed" scalar, and a low-level
            physical NA value. `fill_value` should be the user-facing version,
            and the implementation should handle translating that to the
            physical version for processing the take if necessary.

        Returns
        -------
        ExtensionArray

        Raises
        ------
        IndexError
            When the indices are out of bounds for the array.
        ValueError
            When `indices` contains negative values other than ``-1``
            and `allow_fill` is True.

        See Also
        --------
        numpy.take
        api.extensions.take

        Notes
        -----
        ExtensionArray.take is called by ``Series.__getitem__``, ``.loc``,
        ``iloc``, when `indices` is a sequence of values. Additionally,
        it's called by :meth:`Series.reindex`, or any other method
        that causes realignment, with a `fill_value`.
        """
        # TODO: Remove once we got rid of the (indices < 0) check
        if not is_array_like(indices):
            indices_array = np.asanyarray(indices)
        else:
            # error: Incompatible types in assignment (expression has type
            # "Sequence[int]", variable has type "ndarray")
            indices_array = indices  # type: ignore[assignment]

        if len(self._data) == 0 and (indices_array >= 0).any():
            raise IndexError("cannot do a non-empty take")
        if indices_array.size > 0 and indices_array.max() >= len(self._data):
            raise IndexError("out of bounds value in 'indices'.")

        if allow_fill:
            fill_mask = indices_array < 0
            if fill_mask.any():
                validate_indices(indices_array, len(self._data))
                # TODO(ARROW-9433): Treat negative indices as NULL
                indices_array = pa.array(indices_array, mask=fill_mask)
                result = self._data.take(indices_array)
                if isna(fill_value):
                    return type(self)(result)
                # TODO: ArrowNotImplementedError: Function fill_null has no
                # kernel matching input types (array[string], scalar[string])
                result = type(self)(result)
                result[fill_mask] = fill_value
                return result
                # return type(self)(pc.fill_null(result, pa.scalar(fill_value)))
            else:
                # Nothing to fill
                return type(self)(self._data.take(indices))
        else:  # allow_fill=False
            # TODO(ARROW-9432): Treat negative indices as indices from the right.
            if (indices_array < 0).any():
                # Don't modify in-place
                indices_array = np.copy(indices_array)
                indices_array[indices_array < 0] += len(self._data)
            return type(self)(self._data.take(indices_array))

    @doc(ExtensionArray.to_numpy)
    def to_numpy(
        self,
        dtype: npt.DTypeLike | None = None,
        copy: bool = False,
        na_value: object = lib.no_default,
    ) -> np.ndarray:
        if dtype is None and self._hasna:
            dtype = object
        if na_value is lib.no_default:
            na_value = self.dtype.na_value

        pa_type = self._data.type
        if (
            is_object_dtype(dtype)
            or pa.types.is_timestamp(pa_type)
            or pa.types.is_duration(pa_type)
        ):
            result = np.array(list(self), dtype=dtype)
        else:
            result = np.asarray(self._data, dtype=dtype)
            if copy or self._hasna:
                result = result.copy()
        if self._hasna:
            result[self.isna()] = na_value
        return result

    def unique(self: ArrowExtensionArrayT) -> ArrowExtensionArrayT:
        """
        Compute the ArrowExtensionArray of unique values.

        Returns
        -------
        ArrowExtensionArray
        """
        return type(self)(pc.unique(self._data))

    def value_counts(self, dropna: bool = True) -> Series:
        """
        Return a Series containing counts of each unique value.

        Parameters
        ----------
        dropna : bool, default True
            Don't include counts of missing values.

        Returns
        -------
        counts : Series

        See Also
        --------
        Series.value_counts
        """
        from pandas import (
            Index,
            Series,
        )

        vc = self._data.value_counts()

        values = vc.field(0)
        counts = vc.field(1)
        if dropna and self._data.null_count > 0:
            mask = values.is_valid()
            values = values.filter(mask)
            counts = counts.filter(mask)

        # No missing values so we can adhere to the interface and return a numpy array.
        counts = np.array(counts)

        index = Index(type(self)(values))

        return Series(counts, index=index).astype("Int64")

    @classmethod
    def _concat_same_type(
        cls: type[ArrowExtensionArrayT], to_concat
    ) -> ArrowExtensionArrayT:
        """
        Concatenate multiple ArrowExtensionArrays.

        Parameters
        ----------
        to_concat : sequence of ArrowExtensionArrays

        Returns
        -------
        ArrowExtensionArray
        """
        chunks = [array for ea in to_concat for array in ea._data.iterchunks()]
        arr = pa.chunked_array(chunks)
        return cls(arr)

    def _reduce(self, name: str, *, skipna: bool = True, **kwargs):
        """
        Return a scalar result of performing the reduction operation.

        Parameters
        ----------
        name : str
            Name of the function, supported values are:
            { any, all, min, max, sum, mean, median, prod,
            std, var, sem, kurt, skew }.
        skipna : bool, default True
            If True, skip NaN values.
        **kwargs
            Additional keyword arguments passed to the reduction function.
            Currently, `ddof` is the only supported kwarg.

        Returns
        -------
        scalar

        Raises
        ------
        TypeError : subclass does not define reductions
        """
        if name == "sem":

            def pyarrow_meth(data, skip_nulls, **kwargs):
                numerator = pc.stddev(data, skip_nulls=skip_nulls, **kwargs)
                denominator = pc.sqrt_checked(pc.count(self._data))
                return pc.divide_checked(numerator, denominator)

        else:
            pyarrow_name = {
                "median": "approximate_median",
                "prod": "product",
                "std": "stddev",
                "var": "variance",
            }.get(name, name)
            # error: Incompatible types in assignment
            # (expression has type "Optional[Any]", variable has type
            # "Callable[[Any, Any, KwArg(Any)], Any]")
            pyarrow_meth = getattr(pc, pyarrow_name, None)  # type: ignore[assignment]
            if pyarrow_meth is None:
                # Let ExtensionArray._reduce raise the TypeError
                return super()._reduce(name, skipna=skipna, **kwargs)
        try:
            result = pyarrow_meth(self._data, skip_nulls=skipna, **kwargs)
        except (AttributeError, NotImplementedError, TypeError) as err:
            msg = (
                f"'{type(self).__name__}' with dtype {self.dtype} "
                f"does not support reduction '{name}' with pyarrow "
                f"version {pa.__version__}. '{name}' may be supported by "
                f"upgrading pyarrow."
            )
            raise TypeError(msg) from err
        if pc.is_null(result).as_py():
            return self.dtype.na_value
        return result.as_py()

    def __setitem__(self, key: int | slice | np.ndarray, value: Any) -> None:
        """Set one or more values inplace.

        Parameters
        ----------
        key : int, ndarray, or slice
            When called from, e.g. ``Series.__setitem__``, ``key`` will be
            one of

            * scalar int
            * ndarray of integers.
            * boolean ndarray
            * slice object

        value : ExtensionDtype.type, Sequence[ExtensionDtype.type], or object
            value or values to be set of ``key``.

        Returns
        -------
        None
        """
        key = check_array_indexer(self, key)
        value = self._maybe_convert_setitem_value(value)

        # fast path (GH50248)
        if com.is_null_slice(key):
            if is_scalar(value):
                fill_value = pa.scalar(value, type=self._data.type, from_pandas=True)
                try:
                    self._data = pc.if_else(True, fill_value, self._data)
                    return
                except pa.ArrowNotImplementedError:
                    # ArrowNotImplementedError: Function 'if_else' has no kernel
                    #   matching input types (bool, duration[ns], duration[ns])
                    # TODO: remove try/except wrapper if/when pyarrow implements
                    #   a kernel for duration types.
                    pass
            elif len(value) == len(self):
                if isinstance(value, type(self)) and value.dtype == self.dtype:
                    self._data = value._data
                else:
                    arr = pa.array(value, type=self._data.type, from_pandas=True)
                    self._data = pa.chunked_array([arr])
                return

        indices = self._indexing_key_to_indices(key)

        argsort = np.argsort(indices)
        indices = indices[argsort]

        if is_scalar(value):
            value = np.broadcast_to(value, len(self))
        elif len(indices) != len(value):
            raise ValueError("Length of indexer and values mismatch")
        else:
            value = np.asarray(value)[argsort]

        self._data = self._set_via_chunk_iteration(indices=indices, value=value)

    def _indexing_key_to_indices(
        self, key: int | slice | np.ndarray
    ) -> npt.NDArray[np.intp]:
        """
        Convert indexing key for self into positional indices.

        Parameters
        ----------
        key : int | slice | np.ndarray

        Returns
        -------
        npt.NDArray[np.intp]
        """
        n = len(self)
        if isinstance(key, slice):
            indices = np.arange(n)[key]
        elif is_integer(key):
            # error: Invalid index type "List[Union[int, ndarray[Any, Any]]]"
            # for "ndarray[Any, dtype[signedinteger[Any]]]"; expected type
            # "Union[SupportsIndex, _SupportsArray[dtype[Union[bool_,
            # integer[Any]]]], _NestedSequence[_SupportsArray[dtype[Union
            # [bool_, integer[Any]]]]], _NestedSequence[Union[bool, int]]
            # , Tuple[Union[SupportsIndex, _SupportsArray[dtype[Union[bool_
            # , integer[Any]]]], _NestedSequence[_SupportsArray[dtype[Union
            # [bool_, integer[Any]]]]], _NestedSequence[Union[bool, int]]], ...]]"
            indices = np.arange(n)[[key]]  # type: ignore[index]
        elif is_bool_dtype(key):
            key = np.asarray(key)
            if len(key) != n:
                raise ValueError("Length of indexer and values mismatch")
            indices = key.nonzero()[0]
        else:
            key = np.asarray(key)
            indices = np.arange(n)[key]
        return indices

    def _rank(
        self,
        *,
        axis: AxisInt = 0,
        method: str = "average",
        na_option: str = "keep",
        ascending: bool = True,
        pct: bool = False,
    ):
        """
        See Series.rank.__doc__.
        """
        if pa_version_under9p0 or axis != 0:
            ranked = super()._rank(
                axis=axis,
                method=method,
                na_option=na_option,
                ascending=ascending,
                pct=pct,
            )
            # keep dtypes consistent with the implementation below
            if method == "average" or pct:
                pa_type = pa.float64()
            else:
                pa_type = pa.uint64()
            result = pa.array(ranked, type=pa_type, from_pandas=True)
            return type(self)(result)

        data = self._data.combine_chunks()
        sort_keys = "ascending" if ascending else "descending"
        null_placement = "at_start" if na_option == "top" else "at_end"
        tiebreaker = "min" if method == "average" else method

        result = pc.rank(
            data,
            sort_keys=sort_keys,
            null_placement=null_placement,
            tiebreaker=tiebreaker,
        )

        if na_option == "keep":
            mask = pc.is_null(self._data)
            null = pa.scalar(None, type=result.type)
            result = pc.if_else(mask, null, result)

        if method == "average":
            result_max = pc.rank(
                data,
                sort_keys=sort_keys,
                null_placement=null_placement,
                tiebreaker="max",
            )
            result_max = result_max.cast(pa.float64())
            result_min = result.cast(pa.float64())
            result = pc.divide(pc.add(result_min, result_max), 2)

        if pct:
            if not pa.types.is_floating(result.type):
                result = result.cast(pa.float64())
            if method == "dense":
                divisor = pc.max(result)
            else:
                divisor = pc.count(result)
            result = pc.divide(result, divisor)

        return type(self)(result)

    def _quantile(
        self: ArrowExtensionArrayT, qs: npt.NDArray[np.float64], interpolation: str
    ) -> ArrowExtensionArrayT:
        """
        Compute the quantiles of self for each quantile in `qs`.

        Parameters
        ----------
        qs : np.ndarray[float64]
        interpolation: str

        Returns
        -------
        same type as self
        """
        result = pc.quantile(self._data, q=qs, interpolation=interpolation)
        return type(self)(result)

    def _mode(self: ArrowExtensionArrayT, dropna: bool = True) -> ArrowExtensionArrayT:
        """
        Returns the mode(s) of the ExtensionArray.

        Always returns `ExtensionArray` even if only one value.

        Parameters
        ----------
        dropna : bool, default True
            Don't consider counts of NA values.
            Not implemented by pyarrow.

        Returns
        -------
        same type as self
            Sorted, if possible.
        """
        if pa_version_under6p0:
            raise NotImplementedError("mode only supported for pyarrow version >= 6.0")
        modes = pc.mode(self._data, pc.count_distinct(self._data).as_py())
        values = modes.field(0)
        counts = modes.field(1)
        # counts sorted descending i.e counts[0] = max
        mask = pc.equal(counts, counts[0])
        most_common = values.filter(mask)
        return type(self)(most_common)

    def _maybe_convert_setitem_value(self, value):
        """Maybe convert value to be pyarrow compatible."""
        # TODO: Make more robust like ArrowStringArray._maybe_convert_setitem_value
        return value

    def _set_via_chunk_iteration(
        self, indices: npt.NDArray[np.intp], value: npt.NDArray[Any]
    ) -> pa.ChunkedArray:
        """
        Loop through the array chunks and set the new values while
        leaving the chunking layout unchanged.

        Parameters
        ----------
        indices : npt.NDArray[np.intp]
            Position indices for the underlying ChunkedArray.

        value : ExtensionDtype.type, Sequence[ExtensionDtype.type], or object
            value or values to be set of ``key``.

        Notes
        -----
        Assumes that indices is sorted. Caller is responsible for sorting.
        """
        new_data = []
        stop = 0
        for chunk in self._data.iterchunks():
            start, stop = stop, stop + len(chunk)
            if len(indices) == 0 or stop <= indices[0]:
                new_data.append(chunk)
            else:
                n = int(np.searchsorted(indices, stop, side="left"))
                c_ind = indices[:n] - start
                indices = indices[n:]
                n = len(c_ind)
                c_value, value = value[:n], value[n:]
                new_data.append(self._replace_with_indices(chunk, c_ind, c_value))
        return pa.chunked_array(new_data)

    @classmethod
    def _replace_with_indices(
        cls,
        chunk: pa.Array,
        indices: npt.NDArray[np.intp],
        value: npt.NDArray[Any],
    ) -> pa.Array:
        """
        Replace items selected with a set of positional indices.

        Analogous to pyarrow.compute.replace_with_mask, except that replacement
        positions are identified via indices rather than a mask.

        Parameters
        ----------
        chunk : pa.Array
        indices : npt.NDArray[np.intp]
        value : npt.NDArray[Any]
            Replacement value(s).

        Returns
        -------
        pa.Array
        """
        n = len(indices)

        if n == 0:
            return chunk

        start, stop = indices[[0, -1]]

        if (stop - start) == (n - 1):
            # fast path for a contiguous set of indices
            arrays = [
                chunk[:start],
                pa.array(value, type=chunk.type, from_pandas=True),
                chunk[stop + 1 :],
            ]
            arrays = [arr for arr in arrays if len(arr)]
            if len(arrays) == 1:
                return arrays[0]
            return pa.concat_arrays(arrays)

        mask = np.zeros(len(chunk), dtype=np.bool_)
        mask[indices] = True

        if pa_version_under6p0:
            arr = chunk.to_numpy(zero_copy_only=False)
            arr[mask] = value
            return pa.array(arr, type=chunk.type)

        if isna(value).all():
            return pc.if_else(mask, None, chunk)

        return pc.replace_with_mask(chunk, mask, value)

    # ------------------------------------------------------------------------
    # String methods interface  (Series.str.<method>)

    # asserted to match self._dtype.na_value
    _str_na_value = libmissing.NA

    def _str_count(self, pat: str, flags: int = 0):
        if flags:
            fallback_performancewarning()
            return super()._str_count(pat, flags)
        return type(self)(pc.count_substring_regex(self._data, pat))

    def _str_pad(
        self,
        width: int,
        side: Literal["left", "right", "both"] = "left",
        fillchar: str = " ",
    ):
        if side == "left":
            pa_pad = pc.utf8_lpad
        elif side == "right":
            pa_pad = pc.utf8_rpad
        elif side == "both":
            # https://github.com/apache/arrow/issues/15053
            # pa_pad = pc.utf8_center
            return super()._str_pad(width, side, fillchar)
        else:
            raise ValueError(
                f"Invalid side: {side}. Side must be one of 'left', 'right', 'both'"
            )
        return type(self)(pa_pad(self._data, width, padding=fillchar))

    def _str_map(
        self, f, na_value=None, dtype: Dtype | None = None, convert: bool = True
    ):
        if na_value is None:
            na_value = self.dtype.na_value

        mask = self.isna()
        arr = np.asarray(self)

        np_result = lib.map_infer_mask(
            arr, f, mask.view("uint8"), convert=False, na_value=na_value
        )
        try:
            return type(self)(pa.array(np_result, mask=mask, from_pandas=True))
        except pa.ArrowInvalid:
            return np_result

    def _str_contains(
        self, pat, case: bool = True, flags: int = 0, na=None, regex: bool = True
    ):
        if flags:
            fallback_performancewarning()
            return super()._str_contains(pat, case, flags, na, regex)

        if regex:
            pa_contains = pc.match_substring_regex
        else:
            pa_contains = pc.match_substring
        result = pa_contains(self._data, pat, ignore_case=not case)
        if not isna(na):
            result = result.fill_null(na)
        return type(self)(result)

    def _str_startswith(self, pat: str, na=None):
        result = pc.starts_with(self._data, pat)
        if na is not None:
            result = result.fill_null(na)
        return type(self)(result)

    def _str_endswith(self, pat: str, na=None):
        result = pc.ends_with(self._data, pat)
        if na is not None:
            result = result.fill_null(na)
        return type(self)(result)

    def _str_replace(
        self,
        pat: str | re.Pattern,
        repl: str | Callable,
        n: int = -1,
        case: bool = True,
        flags: int = 0,
        regex: bool = True,
    ):
        if isinstance(pat, re.Pattern) or callable(repl) or not case or flags:
            fallback_performancewarning()
            return super()._str_replace(pat, repl, n, case, flags, regex)

        func = pc.replace_substring_regex if regex else pc.replace_substring
        result = func(self._data, pattern=pat, replacement=repl, max_replacements=n)
        return type(self)(result)

    def _str_repeat(self, repeats: int | Sequence[int]):
        if not isinstance(repeats, int):
            fallback_performancewarning()
            return super()._str_repeat(repeats)
        elif pa_version_under7p0:
            fallback_performancewarning("7")
            return super()._str_repeat(repeats)
        else:
            return type(self)(pc.binary_repeat(self._data, repeats))

    def _str_match(
        self, pat: str, case: bool = True, flags: int = 0, na: Scalar | None = None
    ):
        if not pat.startswith("^"):
            pat = f"^{pat}"
        return self._str_contains(pat, case, flags, na, regex=True)

    def _str_fullmatch(
        self, pat, case: bool = True, flags: int = 0, na: Scalar | None = None
    ):
        if not pat.endswith("$") or pat.endswith("//$"):
            pat = f"{pat}$"
        return self._str_match(pat, case, flags, na)

    def _str_find(self, sub: str, start: int = 0, end: int | None = None):
        if start != 0 and end is not None:
            slices = pc.utf8_slice_codeunits(self._data, start, stop=end)
            result = pc.find_substring(slices, sub)
            not_found = pc.equal(result, -1)
            offset_result = pc.add(result, end - start)
            result = pc.if_else(not_found, result, offset_result)
        elif start == 0 and end is None:
            slices = self._data
            result = pc.find_substring(slices, sub)
        else:
            fallback_performancewarning()
            return super()._str_find(sub, start, end)
        return type(self)(result)

    def _str_get(self, i: int):
        lengths = pc.utf8_length(self._data)
        if i >= 0:
            out_of_bounds = pc.greater_equal(i, lengths)
            start = i
            stop = i + 1
            step = 1
        else:
            out_of_bounds = pc.greater(-i, lengths)
            start = i
            stop = i - 1
            step = -1
        not_out_of_bounds = pc.invert(out_of_bounds.fill_null(True))
        selected = pc.utf8_slice_codeunits(self._data, start, stop=stop, step=step)
        result = pa.array([None] * self._data.length(), type=self._data.type)
        result = pc.if_else(not_out_of_bounds, selected, result)
        return type(self)(result)

    def _str_join(self, sep: str):
        if isinstance(self._dtype, ArrowDtype) and pa.types.is_list(
            self.dtype.pyarrow_dtype
        ):
            # Check ArrowDtype as ArrowString inherits and uses StringDtype
            return type(self)(pc.binary_join(self._data, sep))
        else:
            return super()._str_join(sep)

    def _str_partition(self, sep: str, expand: bool):
        result = super()._str_partition(sep, expand)
        if expand and isinstance(result, type(self)):
            # StringMethods._wrap_result needs numpy-like nested object
            result = result.to_numpy(dtype=object)
        return result

    def _str_rpartition(self, sep: str, expand: bool):
        result = super()._str_rpartition(sep, expand)
        if expand and isinstance(result, type(self)):
            # StringMethods._wrap_result needs numpy-like nested object
            result = result.to_numpy(dtype=object)
        return result

    def _str_slice(
        self, start: int | None = None, stop: int | None = None, step: int | None = None
    ):
        if stop is None:
            # TODO: TODO: Should work once https://github.com/apache/arrow/issues/14991
            #  is fixed
            return super()._str_slice(start, stop, step)
        if start is None:
            start = 0
        if step is None:
            step = 1
        return type(self)(
            pc.utf8_slice_codeunits(self._data, start, stop=stop, step=step)
        )

    def _str_slice_replace(
        self, start: int | None = None, stop: int | None = None, repl: str | None = None
    ):
        if stop is None:
            # Not implemented as of pyarrow=10
            fallback_performancewarning()
            return super()._str_slice_replace(start, stop, repl)
        if repl is None:
            repl = ""
        if start is None:
            start = 0
        return type(self)(pc.utf8_replace_slice(self._data, start, stop, repl))

    def _str_isalnum(self):
        return type(self)(pc.utf8_is_alnum(self._data))

    def _str_isalpha(self):
        return type(self)(pc.utf8_is_alpha(self._data))

    def _str_isdecimal(self):
        return type(self)(pc.utf8_is_decimal(self._data))

    def _str_isdigit(self):
        return type(self)(pc.utf8_is_digit(self._data))

    def _str_islower(self):
        return type(self)(pc.utf8_is_lower(self._data))

    def _str_isnumeric(self):
        return type(self)(pc.utf8_is_numeric(self._data))

    def _str_isspace(self):
        return type(self)(pc.utf8_is_space(self._data))

    def _str_istitle(self):
        return type(self)(pc.utf8_is_title(self._data))

    def _str_capitalize(self):
        return type(self)(pc.utf8_capitalize(self._data))

    def _str_title(self):
        return type(self)(pc.utf8_title(self._data))

    def _str_isupper(self):
        return type(self)(pc.utf8_is_upper(self._data))

    def _str_swapcase(self):
        return type(self)(pc.utf8_swapcase(self._data))

    def _str_len(self):
        return type(self)(pc.utf8_length(self._data))

    def _str_lower(self):
        return type(self)(pc.utf8_lower(self._data))

    def _str_upper(self):
        return type(self)(pc.utf8_upper(self._data))

    def _str_strip(self, to_strip=None):
        if to_strip is None:
            result = pc.utf8_trim_whitespace(self._data)
        else:
            result = pc.utf8_trim(self._data, characters=to_strip)
        return type(self)(result)

    def _str_lstrip(self, to_strip=None):
        if to_strip is None:
            result = pc.utf8_ltrim_whitespace(self._data)
        else:
            result = pc.utf8_ltrim(self._data, characters=to_strip)
        return type(self)(result)

    def _str_rstrip(self, to_strip=None):
        if to_strip is None:
            result = pc.utf8_rtrim_whitespace(self._data)
        else:
            result = pc.utf8_rtrim(self._data, characters=to_strip)
        return type(self)(result)

    # TODO: Should work once https://github.com/apache/arrow/issues/14991 is fixed
    # def _str_removeprefix(self, prefix: str) -> Series:
    #     starts_with = pc.starts_with(self._data, prefix)
    #     removed = pc.utf8_slice_codeunits(self._data, len(prefix))
    #     result = pc.if_else(starts_with, removed, self._data)
    #     return type(self)(result)

    def _str_removesuffix(self, suffix: str) -> Series:
        ends_with = pc.ends_with(self._data, suffix)
        removed = pc.utf8_slice_codeunits(self._data, 0, stop=-len(suffix))
        result = pc.if_else(ends_with, removed, self._data)
        return type(self)(result)
