import dataclasses
from datetime import datetime, timedelta, tzinfo
from io import BufferedIOBase, RawIOBase, TextIOBase, TextIOWrapper
from mmap import mmap
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    Callable,
    Collection,
    Dict,
    Generic,
    Hashable,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

import numpy as np

# To prevent import cycles place any internal imports in the branch below
# and use a string literal forward reference to it in subsequent types
# https://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from typing import final

    from pandas._libs import Period, Timedelta, Timestamp

    from pandas.core.dtypes.dtypes import ExtensionDtype

    from pandas import Interval
    from pandas.core.arrays.base import ExtensionArray  # noqa: F401
    from pandas.core.frame import DataFrame
    from pandas.core.generic import NDFrame  # noqa: F401
    from pandas.core.groupby.generic import DataFrameGroupBy, SeriesGroupBy
    from pandas.core.indexes.base import Index
    from pandas.core.resample import Resampler
    from pandas.core.series import Series
    from pandas.core.window.rolling import BaseWindow

    from pandas.io.formats.format import EngFormatter
else:
    # typing.final does not exist until py38
    final = lambda x: x


# array-like

AnyArrayLike = TypeVar("AnyArrayLike", "ExtensionArray", "Index", "Series", np.ndarray)
ArrayLike = TypeVar("ArrayLike", "ExtensionArray", np.ndarray)

# scalars

PythonScalar = Union[str, int, float, bool]
DatetimeLikeScalar = TypeVar("DatetimeLikeScalar", "Period", "Timestamp", "Timedelta")
PandasScalar = Union["Period", "Timestamp", "Timedelta", "Interval"]
Scalar = Union[PythonScalar, PandasScalar]

# timestamp and timedelta convertible types

TimestampConvertibleTypes = Union[
    "Timestamp", datetime, np.datetime64, int, np.int64, float, str
]
TimedeltaConvertibleTypes = Union[
    "Timedelta", timedelta, np.timedelta64, int, np.int64, float, str
]
Timezone = Union[str, tzinfo]

# other

Dtype = Union[
    "ExtensionDtype", str, np.dtype, Type[Union[str, float, int, complex, bool, object]]
]
DtypeObj = Union[np.dtype, "ExtensionDtype"]

# FrameOrSeriesUnion  means either a DataFrame or a Series. E.g.
# `def func(a: FrameOrSeriesUnion) -> FrameOrSeriesUnion: ...` means that if a Series
# is passed in, either a Series or DataFrame is returned, and if a DataFrame is passed
# in, either a DataFrame or a Series is returned.
FrameOrSeriesUnion = Union["DataFrame", "Series"]

# FrameOrSeries is stricter and ensures that the same subclass of NDFrame always is
# used. E.g. `def func(a: FrameOrSeries) -> FrameOrSeries: ...` means that if a
# Series is passed into a function, a Series is always returned and if a DataFrame is
# passed in, a DataFrame is always returned.
FrameOrSeries = TypeVar("FrameOrSeries", bound="NDFrame")

Axis = Union[str, int]
Label = Optional[Hashable]
IndexLabel = Union[Label, Sequence[Label]]
Level = Union[Label, int]
Ordered = Optional[bool]
JSONSerializable = Optional[Union[PythonScalar, List, Dict]]
Axes = Collection

# For functions like rename that convert one label to another
Renamer = Union[Mapping[Label, Any], Callable[[Label], Label]]

# to maintain type information across generic functions and parametrization
T = TypeVar("T")

# used in decorators to preserve the signature of the function it decorates
# see https://mypy.readthedocs.io/en/stable/generics.html#declaring-decorators
FuncType = Callable[..., Any]
F = TypeVar("F", bound=FuncType)

# types of vectorized key functions for DataFrame::sort_values and
# DataFrame::sort_index, among others
ValueKeyFunc = Optional[Callable[["Series"], Union["Series", AnyArrayLike]]]
IndexKeyFunc = Optional[Callable[["Index"], Union["Index", AnyArrayLike]]]

# types of `func` kwarg for DataFrame.aggregate and Series.aggregate
AggFuncTypeBase = Union[Callable, str]
AggFuncTypeDict = Dict[Label, Union[AggFuncTypeBase, List[AggFuncTypeBase]]]
AggFuncType = Union[
    AggFuncTypeBase,
    List[AggFuncTypeBase],
    AggFuncTypeDict,
]
AggObjType = Union[
    "Series",
    "DataFrame",
    "SeriesGroupBy",
    "DataFrameGroupBy",
    "BaseWindow",
    "Resampler",
]

# filenames and file-like-objects
Buffer = Union[IO[AnyStr], RawIOBase, BufferedIOBase, TextIOBase, TextIOWrapper, mmap]
FileOrBuffer = Union[str, Buffer[T]]
FilePathOrBuffer = Union[Path, FileOrBuffer[T]]

# for arbitrary kwargs passed during reading/writing files
StorageOptions = Optional[Dict[str, Any]]


# compression keywords and compression
CompressionDict = Dict[str, Any]
CompressionOptions = Optional[Union[str, CompressionDict]]


# let's bind types
ModeVar = TypeVar("ModeVar", str, None, Optional[str])
EncodingVar = TypeVar("EncodingVar", str, None, Optional[str])


# type of float formatter in DataFrameFormatter
FloatFormatType = Union[str, Callable, "EngFormatter"]


@dataclasses.dataclass
class IOArgs(Generic[ModeVar, EncodingVar]):
    """
    Return value of io/common.py:get_filepath_or_buffer.

    This is used to easily close created fsspec objects.

    Note (copy&past from io/parsers):
    filepath_or_buffer can be Union[FilePathOrBuffer, s3fs.S3File, gcsfs.GCSFile]
    though mypy handling of conditional imports is difficult.
    See https://github.com/python/mypy/issues/1297
    """

    filepath_or_buffer: FileOrBuffer
    encoding: EncodingVar
    mode: Union[ModeVar, str]
    compression: CompressionDict
    should_close: bool = False

    def close(self) -> None:
        """
        Close the buffer if it was created by get_filepath_or_buffer.
        """
        if self.should_close:
            assert not isinstance(self.filepath_or_buffer, str)
            self.filepath_or_buffer.close()
        self.should_close = False


@dataclasses.dataclass
class IOHandles:
    """
    Return value of io/common.py:get_handle

    This is used to easily close created buffers and to handle corner cases when
    TextIOWrapper is inserted.

    handle: The file handle to be used.
    created_handles: All file handles that are created by get_handle
    is_wrapped: Whether a TextIOWrapper needs to be detached.
    """

    handle: Buffer
    created_handles: List[Buffer] = dataclasses.field(default_factory=list)
    is_wrapped: bool = False

    def close(self) -> None:
        """
        Close all created buffers.

        Note: If a TextIOWrapper was inserted, it is flushed and detached to
        avoid closing the potentially user-created buffer.
        """
        if self.is_wrapped:
            assert isinstance(self.handle, TextIOWrapper)
            self.handle.flush()
            self.handle.detach()
            self.created_handles.remove(self.handle)
        for handle in self.created_handles:
            handle.close()
        self.created_handles = []
        self.is_wrapped = False
