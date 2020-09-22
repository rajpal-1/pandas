"""
Module for formatting output data into CSV files.
"""

import csv as csvlib
from io import StringIO, TextIOWrapper
import os
from typing import Any, Dict, Iterator, List, Optional, Sequence

import numpy as np

from pandas._libs import writers as libwriters
from pandas._typing import (
    CompressionOptions,
    FilePathOrBuffer,
    IndexLabel,
    Label,
    StorageOptions,
)

from pandas.core.dtypes.generic import (
    ABCDatetimeIndex,
    ABCIndexClass,
    ABCMultiIndex,
    ABCPeriodIndex,
)
from pandas.core.dtypes.missing import notna

from pandas.core.indexes.api import Index

from pandas.io.common import get_filepath_or_buffer, get_handle
from pandas.io.formats.format import DataFrameFormatter


class CSVFormatter:
    def __init__(
        self,
        formatter: DataFrameFormatter,
        path_or_buf: Optional[FilePathOrBuffer[str]] = None,
        sep: str = ",",
        cols: Optional[Sequence[Label]] = None,
        index_label: Optional[IndexLabel] = None,
        mode: str = "w",
        encoding: Optional[str] = None,
        errors: str = "strict",
        compression: CompressionOptions = "infer",
        quoting: Optional[int] = None,
        line_terminator="\n",
        chunksize: Optional[int] = None,
        quotechar: Optional[str] = '"',
        date_format: Optional[str] = None,
        doublequote: bool = True,
        escapechar: Optional[str] = None,
        storage_options: StorageOptions = None,
    ):
        self.fmt = formatter

        self.obj = self.fmt.frame

        self.encoding = encoding or "utf-8"

        if path_or_buf is None:
            path_or_buf = StringIO()

        ioargs = get_filepath_or_buffer(
            path_or_buf,
            encoding=self.encoding,
            compression=compression,
            mode=mode,
            storage_options=storage_options,
        )

        self.compression = ioargs.compression.pop("method")
        self.compression_args = ioargs.compression
        self.path_or_buf = ioargs.filepath_or_buffer
        self.should_close = ioargs.should_close
        self.mode = ioargs.mode

        self.sep = sep
        self.na_rep = self.fmt.na_rep
        self.float_format = self.fmt.float_format
        self.decimal = self.fmt.decimal
        self.header = self.fmt.header
        self.index = self.fmt.index
        self.index_label = index_label
        self.index_label = self._initialize_index_label(index_label)
        self.errors = errors
        self.quoting = quoting or csvlib.QUOTE_MINIMAL
        self.quotechar = self._initialize_quotechar(quotechar)
        self.doublequote = doublequote
        self.escapechar = escapechar
        self.line_terminator = line_terminator or os.linesep
        self.date_format = date_format
        self.cols = self._initialize_columns(cols)
        self.chunksize = self._initialize_chunksize(chunksize)

    @property


    def _initialize_index_label(self, index_label: Optional[IndexLabel]) -> IndexLabel:
        if index_label is not False:
            if index_label is None:
                return self._get_index_label_from_obj()
            elif not isinstance(index_label, (list, tuple, np.ndarray, ABCIndexClass)):
                # given a string for a DF with Index
                return [index_label]
        return index_label

    def _get_index_label_from_obj(self) -> List[str]:
        if isinstance(self.obj.index, ABCMultiIndex):
            return self._get_index_label_multiindex()
        else:
            return self._get_index_label_flat()

    def _get_index_label_multiindex(self) -> List[str]:
        return [name or "" for name in self.obj.index.names]

    def _get_index_label_flat(self) -> List[str]:
        index_label = self.obj.index.name
        return [""] if index_label is None else [index_label]

    def _initialize_quotechar(self, quotechar: Optional[str]) -> Optional[str]:
        if self.quoting != csvlib.QUOTE_NONE:
            # prevents crash in _csv
            return quotechar

    @property
    def has_mi_columns(self) -> bool:
        return bool(isinstance(self.obj.columns, ABCMultiIndex))

    def _initialize_columns(self, cols: Optional[Sequence[Label]]) -> Sequence[Label]:
        # validate mi options
        if self.has_mi_columns:
            if cols is not None:
                msg = "cannot specify cols with a MultiIndex on the columns"
                raise TypeError(msg)

        if cols is not None:
            if isinstance(cols, ABCIndexClass):
                cols = cols._format_native_types(**self._number_format)
            else:
                cols = list(cols)
            self.obj = self.obj.loc[:, cols]

        # update columns to include possible multiplicity of dupes
        # and make sure sure cols is just a list of labels
        new_cols = self.obj.columns
        if isinstance(new_cols, ABCIndexClass):
            return new_cols._format_native_types(**self._number_format)
        else:
            assert isinstance(cols, Sequence)
            return list(new_cols)

    def _initialize_chunksize(self, chunksize: Optional[int]) -> int:
        if chunksize is None:
            return (100000 // (len(self.cols) or 1)) or 1
        return int(chunksize)

    @property
    def _number_format(self) -> Dict[str, Any]:
        """Dictionary used for storing number formatting settings."""
        return dict(
            na_rep=self.na_rep,
            float_format=self.float_format,
            date_format=self.date_format,
            quoting=self.quoting,
            decimal=self.decimal,
        )

    @property
    def data_index(self) -> Index:
        data_index = self.obj.index
        if (
            isinstance(data_index, (ABCDatetimeIndex, ABCPeriodIndex))
            and self.date_format is not None
        ):
            data_index = Index(
                [x.strftime(self.date_format) if notna(x) else "" for x in data_index]
            )
        return data_index

    @property
    def nlevels(self) -> int:
        if self.index:
            return getattr(self.data_index, "nlevels", 1)
        else:
            return 0

    @property
    def _has_aliases(self) -> bool:
        return isinstance(self.header, (tuple, list, np.ndarray, ABCIndexClass))

    @property
    def _need_to_save_header(self) -> bool:
        return bool(self._has_aliases or self.header)

    @property
    def write_cols(self) -> Sequence[Label]:
        if self._has_aliases:
            assert not isinstance(self.header, bool)
            if len(self.header) != len(self.cols):
                raise ValueError(
                    f"Writing {len(self.cols)} cols but got {len(self.header)} aliases"
                )
            else:
                return self.header
        else:
            return self.cols

    @property
    def encoded_labels(self) -> List[Label]:
        encoded_labels: List[Label] = []

        if self.index and self.index_label:
            assert isinstance(self.index_label, Sequence)
            encoded_labels = list(self.index_label)

        if not self.has_mi_columns or self._has_aliases:
            encoded_labels += list(self.write_cols)

        return encoded_labels

    def save(self) -> None:
        """
        Create the writer & save.
        """
        # get a handle or wrap an existing handle to take care of 1) compression and
        # 2) text -> byte conversion
        f, handles = get_handle(
            self.path_or_buf,
            self.mode,
            encoding=self.encoding,
            errors=self.errors,
            compression=dict(self.compression_args, method=self.compression),
        )

        try:
            # Note: self.encoding is irrelevant here
            self.writer = csvlib.writer(
                f,
                lineterminator=self.line_terminator,
                delimiter=self.sep,
                quoting=self.quoting,
                doublequote=self.doublequote,
                escapechar=self.escapechar,
                quotechar=self.quotechar,
            )

            self._save()

        finally:
            if self.should_close:
                f.close()
            elif (
                isinstance(f, TextIOWrapper)
                and not f.closed
                and f != self.path_or_buf
                and hasattr(self.path_or_buf, "write")
            ):
                # get_handle uses TextIOWrapper for non-binary handles. TextIOWrapper
                # closes the wrapped handle if it is not detached.
                f.flush()  # make sure everything is written
                f.detach()  # makes f unusable
                del f
            elif f != self.path_or_buf:
                f.close()
            for _fh in handles:
                _fh.close()

    def _save(self) -> None:
        if self._need_to_save_header:
            self._save_header()
        self._save_body()

    def _save_header(self) -> None:
        if not self.has_mi_columns or self._has_aliases:
            self.writer.writerow(self.encoded_labels)
        else:
            for row in self._generate_multiindex_header_rows():
                self.writer.writerow(row)

    def _generate_multiindex_header_rows(self) -> Iterator[List[Label]]:
        columns = self.obj.columns
        for i in range(columns.nlevels):
            # we need at least 1 index column to write our col names
            col_line = []
            if self.index:
                # name is the first column
                col_line.append(columns.names[i])

                if isinstance(self.index_label, list) and len(self.index_label) > 1:
                    col_line.extend([""] * (len(self.index_label) - 1))

            col_line.extend(columns._get_level_values(i))
            yield col_line

        # Write out the index line if it's not empty.
        # Otherwise, we will print out an extraneous
        # blank line between the mi and the data rows.
        if self.encoded_labels and set(self.encoded_labels) != {""}:
            yield self.encoded_labels + [""] * len(columns)

    def _save_body(self) -> None:
        nrows = len(self.data_index)
        chunks = int(nrows / self.chunksize) + 1
        for i in range(chunks):
            start_i = i * self.chunksize
            end_i = min(start_i + self.chunksize, nrows)
            if start_i >= end_i:
                break
            self._save_chunk(start_i, end_i)

    def _save_chunk(self, start_i: int, end_i: int) -> None:
        # create the data for a chunk
        slicer = slice(start_i, end_i)
        df = self.obj.iloc[slicer]

        res = df._mgr.to_native_types(**self._number_format)
        data = [res.iget_values(i) for i in range(len(res.items))]

        ix = self.data_index[slicer]._format_native_types(**self._number_format)
        libwriters.write_csv_rows(data, ix, self.nlevels, self.cols, self.writer)
