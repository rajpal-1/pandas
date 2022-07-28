from __future__ import annotations

import ctypes
import re
from typing import Any

import numpy as np

import pandas as pd
from pandas.core.exchange.dataframe_protocol import (
    Buffer,
    Column,
    ColumnNullType,
    DataFrame as DataFrameXchg,
    DtypeKind,
)
from pandas.core.exchange.utils import (
    ArrowCTypes,
    Endianness,
)

_NP_DTYPES: dict[DtypeKind, dict[int, Any]] = {
    DtypeKind.INT: {8: np.int8, 16: np.int16, 32: np.int32, 64: np.int64},
    DtypeKind.UINT: {8: np.uint8, 16: np.uint16, 32: np.uint32, 64: np.uint64},
    DtypeKind.FLOAT: {32: np.float32, 64: np.float64},
    DtypeKind.BOOL: {8: bool},
}


def from_dataframe(df, allow_copy=True) -> pd.DataFrame:
    """
    Build a ``pd.DataFrame`` from any DataFrame supporting the interchange protocol.

    Parameters
    ----------
    df : DataFrameXchg
        Object supporting the exchange protocol, i.e. `__dataframe__` method.
    allow_copy : bool, default: True
        Whether to allow copying the memory to perform the conversion
        (if false then zero-copy approach is requested).

    Returns
    -------
    pd.DataFrame
    """
    if isinstance(df, pd.DataFrame):
        return df

    if not hasattr(df, "__dataframe__"):
        raise ValueError("`df` does not support __dataframe__")

    return _from_dataframe(df.__dataframe__(allow_copy=allow_copy))


def _from_dataframe(df: DataFrameXchg, allow_copy=True):
    """
    Build a ``pd.DataFrame`` from the DataFrame exchange object.

    Parameters
    ----------
    df : DataFrameXchg
        Object supporting the exchange protocol, i.e. `__dataframe__` method.
    allow_copy : bool, default: True
        Whether to allow copying the memory to perform the conversion
        (if false then zero-copy approach is requested).

    Returns
    -------
    pd.DataFrame
    """
    pandas_dfs = []
    for chunk in df.get_chunks():
        pandas_df = protocol_df_chunk_to_pandas(chunk)
        pandas_dfs.append(pandas_df)

    if not allow_copy and len(pandas_dfs) > 1:
        raise RuntimeError(
            "To join chunks a copy is required which is forbidden by allow_copy=False"
        )
    if len(pandas_dfs) == 1:
        pandas_df = pandas_dfs[0]
    else:
        pandas_df = pd.concat(pandas_dfs, axis=0, ignore_index=True, copy=False)

    index_obj = df.metadata.get("pandas.index", None)
    if index_obj is not None:
        pandas_df.index = index_obj

    return pandas_df


def protocol_df_chunk_to_pandas(df: DataFrameXchg) -> pd.DataFrame:
    """
    Convert exchange protocol chunk to ``pd.DataFrame``.

    Parameters
    ----------
    df : DataFrameXchg

    Returns
    -------
    pd.DataFrame
    """
    # We need a dict of columns here, with each column being a NumPy array (at
    # least for now, deal with non-NumPy dtypes later).
    columns: dict[str, Any] = {}
    buffers = []  # hold on to buffers, keeps memory alive
    for name in df.column_names():
        if not isinstance(name, str):
            raise ValueError(f"Column {name} is not a string")
        if name in columns:
            raise ValueError(f"Column {name} is not unique")
        col = df.get_column_by_name(name)
        dtype = col.dtype[0]
        if dtype in (
            DtypeKind.INT,
            DtypeKind.UINT,
            DtypeKind.FLOAT,
            DtypeKind.BOOL,
        ):
            columns[name], buf = primitive_column_to_ndarray(col)
        elif dtype == DtypeKind.CATEGORICAL:
            columns[name], buf = categorical_column_to_series(col)
        elif dtype == DtypeKind.STRING:
            columns[name], buf = string_column_to_ndarray(col)
        elif dtype == DtypeKind.DATETIME:
            columns[name], buf = datetime_column_to_ndarray(col)
        else:
            raise NotImplementedError(f"Data type {dtype} not handled yet")

        buffers.append(buf)

    pandas_df = pd.DataFrame(columns)
    pandas_df.attrs["_EXCHANGE_PROTOCOL_BUFFERS"] = buffers
    return pandas_df


def primitive_column_to_ndarray(col: Column) -> tuple[np.ndarray, Any]:
    """
    Convert a column holding one of the primitive dtypes to a NumPy array.

    A primitive type is one of: int, uint, float, bool.

    Parameters
    ----------
    col : Column

    Returns
    -------
    tuple
        Tuple of np.ndarray holding the data and the memory owner object
        that keeps the memory alive.
    """
    buffers = col.get_buffers()

    data_buff, data_dtype = buffers["data"]
    data = buffer_to_ndarray(data_buff, data_dtype, col.offset, col.size)

    data = set_nulls(data, col, buffers["validity"])
    return data, buffers


def categorical_column_to_series(col: Column) -> tuple[pd.Series, Any]:
    """
    Convert a column holding categorical data to a pandas Series.

    Parameters
    ----------
    col : Column

    Returns
    -------
    tuple
        Tuple of pd.Series holding the data and the memory owner object
        that keeps the memory alive.
    """
    categorical = col.describe_categorical

    if not categorical["is_dictionary"]:
        raise NotImplementedError("Non-dictionary categoricals not supported yet")

    categories = np.array(categorical["categories"]._col)  # type:ignore[union-attr]
    buffers = col.get_buffers()

    codes_buff, codes_dtype = buffers["data"]
    codes = buffer_to_ndarray(codes_buff, codes_dtype, col.offset, col.size)

    # Doing module in order to not get ``IndexError`` for
    # out-of-bounds sentinel values in `codes`
    values = categories[codes % len(categories)]

    cat = pd.Categorical(
        values, categories=categories, ordered=categorical["is_ordered"]
    )
    data = pd.Series(cat)

    data = set_nulls(data, col, buffers["validity"])
    return data, buffers


def string_column_to_ndarray(col: Column) -> tuple[np.ndarray, Any]:
    """
    Convert a column holding string data to a NumPy array.

    Parameters
    ----------
    col : Column

    Returns
    -------
    tuple
        Tuple of np.ndarray holding the data and the memory owner object
        that keeps the memory alive.
    """
    null_kind, sentinel_val = col.describe_null

    if null_kind not in (
        ColumnNullType.NON_NULLABLE,
        ColumnNullType.USE_BITMASK,
        ColumnNullType.USE_BYTEMASK,
    ):
        raise NotImplementedError(
            f"{null_kind} null kind is not yet supported for string columns."
        )

    buffers = col.get_buffers()

    assert buffers["offsets"], "String buffers must contain offsets"
    # Retrieve the data buffer containing the UTF-8 code units
    data_buff, protocol_data_dtype = buffers["data"]
    # We're going to reinterpret the buffer as uint8, so make sure we can do it safely
    assert protocol_data_dtype[1] == 8  # bitwidth == 8
    assert protocol_data_dtype[2] == ArrowCTypes.STRING  # format_str == utf-8
    # Convert the buffers to NumPy arrays. In order to go from STRING to
    # an equivalent ndarray, we claim that the buffer is uint8 (i.e., a byte array)
    data_dtype = (
        DtypeKind.UINT,
        8,
        ArrowCTypes.UINT8,
        Endianness.NATIVE,
    )
    # Specify zero offset as we don't want to chunk the string data
    data = buffer_to_ndarray(data_buff, data_dtype, offset=0, length=col.size)

    # Retrieve the offsets buffer containing the index offsets demarcating
    # the beginning and the ending of each string
    offset_buff, offset_dtype = buffers["offsets"]
    # Offsets buffer contains start-stop positions of strings in the data buffer,
    # meaning that it has more elements than in the data buffer, do `col.size + 1` here
    # to pass a proper offsets buffer size
    offsets = buffer_to_ndarray(
        offset_buff, offset_dtype, col.offset, length=col.size + 1
    )

    null_pos = None
    if null_kind in (ColumnNullType.USE_BITMASK, ColumnNullType.USE_BYTEMASK):
        assert buffers["validity"], "Validity buffers cannot be empty for masks"
        valid_buff, valid_dtype = buffers["validity"]
        null_pos = buffer_to_ndarray(valid_buff, valid_dtype, col.offset, col.size)
        if sentinel_val == 0:
            null_pos = ~null_pos

    # Assemble the strings from the code units
    str_list: list[None | float | str] = [None] * col.size
    for i in range(col.size):
        # Check for missing values
        if null_pos is not None and null_pos[i]:
            str_list[i] = np.nan
            continue

        # Extract a range of code units
        units = data[offsets[i] : offsets[i + 1]]

        # Convert the list of code units to bytes
        str_bytes = bytes(units)

        # Create the string
        string = str_bytes.decode(encoding="utf-8")

        # Add to our list of strings
        str_list[i] = string

    # Convert the string list to a NumPy array
    return np.asarray(str_list, dtype="object"), buffers


def parse_datetime_format_str(format_str, data):
    """Parse datetime `format_str` to interpret the `data`."""
    # timestamp 'ts{unit}:tz'
    timestamp_meta = re.match(r"ts([smun]):(.*)", format_str)
    if timestamp_meta:
        unit, tz = timestamp_meta.group(1), timestamp_meta.group(2)
        if tz != "":
            raise NotImplementedError("Timezones are not supported yet")
        if unit != "s":
            # the format string describes only a first letter of the unit, so
            # add one extra letter to convert the unit to numpy-style:
            # 'm' -> 'ms', 'u' -> 'us', 'n' -> 'ns'
            unit += "s"
        data = data.astype(f"datetime64[{unit}]")
        return data

    # date 'td{Days/Ms}'
    date_meta = re.match(r"td([Dm])", format_str)
    if date_meta:
        unit = date_meta.group(1)
        if unit == "D":
            # NumPy doesn't support DAY unit, so converting days to seconds
            # (converting to uint64 to avoid overflow)
            data = (data.astype(np.uint64) * (24 * 60 * 60)).astype("datetime64[s]")
        elif unit == "m":
            data = data.astype("datetime64[ms]")
        else:
            raise NotImplementedError(f"Date unit is not supported: {unit}")
        return data

    raise NotImplementedError(f"DateTime kind is not supported: {format_str}")


def datetime_column_to_ndarray(col: Column) -> tuple[np.ndarray, Any]:
    """
    Convert a column holding DateTime data to a NumPy array.

    Parameters
    ----------
    col : Column

    Returns
    -------
    tuple
        Tuple of np.ndarray holding the data and the memory owner object
        that keeps the memory alive.
    """
    buffers = col.get_buffers()

    _, _, format_str, _ = col.dtype
    dbuf, dtype = buffers["data"]
    # Consider dtype being `uint` to get number of units passed since the 01.01.1970
    data = buffer_to_ndarray(
        dbuf,
        (
            DtypeKind.UINT,
            dtype[1],
            getattr(ArrowCTypes, f"UINT{dtype[1]}"),
            Endianness.NATIVE,
        ),
        col.offset,
        col.size,
    )

    data = parse_datetime_format_str(format_str, data)
    data = set_nulls(data, col, buffers["validity"])
    return data, buffers


def buffer_to_ndarray(
    buffer: Buffer,
    dtype: tuple[DtypeKind, int, str, str],
    offset: int = 0,
    length: int | None = None,
) -> np.ndarray:
    """
    Build a NumPy array from the passed buffer.

    Parameters
    ----------
    buffer : Buffer
        Buffer to build a NumPy array from.
    dtype : tuple
        Data type of the buffer conforming protocol dtypes format.
    offset : int, default: 0
        Number of elements to offset from the start of the buffer.
    length : int, optional
        If the buffer is a bit-mask, specifies a number of bits to read
        from the buffer. Has no effect otherwise.

    Returns
    -------
    np.ndarray

    Notes
    -----
    The returned array doesn't own the memory. The caller of this function is
    responsible for keeping the memory owner object alive as long as
    the returned NumPy array is being used.
    """
    kind, bit_width, _, _ = dtype

    column_dtype = _NP_DTYPES.get(kind, {}).get(bit_width, None)
    if column_dtype is None:
        raise NotImplementedError(f"Conversion for {dtype} is not yet supported.")

    # TODO: No DLPack yet, so need to construct a new ndarray from the data pointer
    # and size in the buffer plus the dtype on the column. Use DLPack as NumPy supports
    # it since https://github.com/numpy/numpy/pull/19083
    ctypes_type = np.ctypeslib.as_ctypes_type(column_dtype)
    data_pointer = ctypes.cast(
        buffer.ptr + (offset * bit_width // 8), ctypes.POINTER(ctypes_type)
    )

    if bit_width == 1:
        assert length is not None, "`length` must be specified for a bit-mask buffer."
        arr = np.ctypeslib.as_array(data_pointer, shape=(buffer.bufsize,))
        return bitmask_to_bool_ndarray(arr, length, first_byte_offset=offset % 8)
    else:
        return np.ctypeslib.as_array(
            data_pointer, shape=(buffer.bufsize // (bit_width // 8),)
        )


def bitmask_to_bool_ndarray(
    bitmask: np.ndarray, mask_length: int, first_byte_offset: int = 0
) -> np.ndarray:
    """
    Convert bit-mask to a boolean NumPy array.

    Parameters
    ----------
    bitmask : np.ndarray[uint8]
        NumPy array of uint8 dtype representing the bitmask.
    mask_length : int
        Number of elements in the mask to interpret.
    first_byte_offset : int, default: 0
        Number of elements to offset from the start of the first byte.

    Returns
    -------
    np.ndarray[bool]
    """
    bytes_to_skip = first_byte_offset // 8
    bitmask = bitmask[bytes_to_skip:]
    first_byte_offset %= 8

    bool_mask = np.zeros(mask_length, dtype=bool)

    # Processing the first byte separately as it has its own offset
    val = bitmask[0]
    mask_idx = 0
    bits_in_first_byte = min(8 - first_byte_offset, mask_length)
    for j in range(bits_in_first_byte):
        if val & (1 << (j + first_byte_offset)):
            bool_mask[mask_idx] = True
        mask_idx += 1

    # `mask_length // 8` describes how many full bytes to process
    for i in range((mask_length - bits_in_first_byte) // 8):
        # doing `+ 1` as we already processed the first byte
        val = bitmask[i + 1]
        for j in range(8):
            if val & (1 << j):
                bool_mask[mask_idx] = True
            mask_idx += 1

    if len(bitmask) > 1:
        # Processing reminder of last byte
        val = bitmask[-1]
        for j in range(len(bool_mask) - mask_idx):
            if val & (1 << j):
                bool_mask[mask_idx] = True
            mask_idx += 1

    return bool_mask


def set_nulls(
    data: np.ndarray | pd.Series,
    col: Column,
    validity: tuple[Buffer, tuple[DtypeKind, int, str, str]] | None,
    allow_modify_inplace: bool = True,
):
    """
    Set null values for the data according to the column null kind.

    Parameters
    ----------
    data : np.ndarray or pd.Series
        Data to set nulls in.
    col : Column
        Column object that describes the `data`.
    validity : tuple(Buffer, dtype) or None
        The return value of ``col.buffers()``. We do not access the ``col.buffers()``
        here to not take the ownership of the memory of buffer objects.
    allow_modify_inplace : bool, default: True
        Whether to modify the `data` inplace when zero-copy is possible (True) or always
        modify a copy of the `data` (False).

    Returns
    -------
    np.ndarray or pd.Series
        Data with the nulls being set.
    """
    null_kind, sentinel_val = col.describe_null
    null_pos = None

    if null_kind == ColumnNullType.USE_SENTINEL:
        null_pos = data == sentinel_val
    elif null_kind in (ColumnNullType.USE_BITMASK, ColumnNullType.USE_BYTEMASK):
        assert validity, "Expected to have a validity buffer for the mask"
        valid_buff, valid_dtype = validity
        null_pos = buffer_to_ndarray(valid_buff, valid_dtype, col.offset, col.size)
        if sentinel_val == 0:
            null_pos = ~null_pos
    elif null_kind in (ColumnNullType.NON_NULLABLE, ColumnNullType.USE_NAN):
        pass
    else:
        raise NotImplementedError(f"Null kind {null_kind} is not yet supported.")

    if null_pos is not None and np.any(null_pos):
        if not allow_modify_inplace:
            data = data.copy()
        try:
            data[null_pos] = None
        except TypeError:
            # TypeError happens if the `data` dtype appears to be non-nullable
            # in numpy notation (bool, int, uint). If this happens,
            # cast the `data` to nullable float dtype.
            data = data.astype(float)
            data[null_pos] = None

    return data
