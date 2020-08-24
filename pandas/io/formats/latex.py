"""
Module for formatting output data in Latex.
"""
from abc import ABC, abstractmethod
from typing import IO, List, Optional

import numpy as np

from pandas.core.dtypes.generic import ABCMultiIndex

from pandas.io.formats.format import DataFrameFormatter, TableFormatter


class RowCreator:
    def __init__(self, *, fmt, multicolumn, multicolumn_format, multirow):
        self.fmt = fmt
        self.frame = self.fmt.frame
        self.multicolumn = multicolumn
        self.multicolumn_format = multicolumn_format
        self.multirow = multirow
        self.clinebuf: List[List[int]] = []
        self.strcols = self._get_strcols()
        self.strrows = list(zip(*self.strcols))

    def get_strrow(self, row_num, row):
        """Get string representation of the row."""
        is_multicol = row_num < self._clevels and self.fmt.header and self.multicolumn

        is_multirow = (
            row_num >= self._nlevels
            and self.fmt.index
            and self.multirow
            and self._ilevels > 1
        )

        is_cline_maybe_required = is_multirow and row_num < len(self.strrows) - 1

        crow = self._preprocess_row(row)

        if is_multicol:
            crow = self._format_multicolumn(crow)
        if is_multirow:
            crow = self._format_multirow(crow, row_num)

        lst = []
        lst.append(" & ".join(crow))
        lst.append(" \\\\")
        if is_cline_maybe_required:
            cline = self._compose_cline(row_num, len(self.strcols))
            lst.append(cline)
        return "".join(lst)

    @property
    def _header_row_num(self):
        return self._nlevels if self.fmt.header else 0

    @property
    def _ilevels(self):
        return self.frame.index.nlevels

    @property
    def _clevels(self):
        return self.frame.columns.nlevels

    @property
    def _nlevels(self):
        nlevels = self._clevels
        if self.fmt.has_index_names and self.fmt.show_index_names:
            nlevels += 1
        return nlevels

    def _get_strcols(self):
        """String representation of the columns."""
        if len(self.frame.columns) == 0 or len(self.frame.index) == 0:
            info_line = (
                f"Empty {type(self.frame).__name__}\n"
                f"Columns: {self.frame.columns}\n"
                f"Index: {self.frame.index}"
            )
            strcols = [[info_line]]
        else:
            strcols = self.fmt._to_str_columns()

        # reestablish the MultiIndex that has been joined by _to_str_column
        if self.fmt.index and isinstance(self.frame.index, ABCMultiIndex):
            out = self.frame.index.format(
                adjoin=False,
                sparsify=self.fmt.sparsify,
                names=self.fmt.has_index_names,
                na_rep=self.fmt.na_rep,
            )

            # index.format will sparsify repeated entries with empty strings
            # so pad these with some empty space
            def pad_empties(x):
                for pad in reversed(x):
                    if pad:
                        break
                return [x[0]] + [i if i else " " * len(pad) for i in x[1:]]

            out = (pad_empties(i) for i in out)

            # Add empty spaces for each column level
            clevels = self.frame.columns.nlevels
            out = [[" " * len(i[-1])] * clevels + i for i in out]

            # Add the column names to the last index column
            cnames = self.frame.columns.names
            if any(cnames):
                new_names = [i if i else "{}" for i in cnames]
                out[self.frame.index.nlevels - 1][:clevels] = new_names

            # Get rid of old multiindex column and add new ones
            strcols = out + strcols[1:]
        return strcols

    def _preprocess_row(self, row):
        if self.fmt.escape:
            crow = self._escape_backslashes(row)
        else:
            crow = [x if x else "{}" for x in row]
        if self.fmt.bold_rows and self.fmt.index:
            crow = self._convert_to_bold(crow, self._ilevels)
        return crow

    @staticmethod
    def _escape_backslashes(row):
        return [
            (
                x.replace("\\", "\\textbackslash ")
                .replace("_", "\\_")
                .replace("%", "\\%")
                .replace("$", "\\$")
                .replace("#", "\\#")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace("~", "\\textasciitilde ")
                .replace("^", "\\textasciicircum ")
                .replace("&", "\\&")
                if (x and x != "{}")
                else "{}"
            )
            for x in row
        ]

    @staticmethod
    def _convert_to_bold(crow, ilevels):
        return [
            f"\\textbf{{{x}}}" if j < ilevels and x.strip() not in ["", "{}"] else x
            for j, x in enumerate(crow)
        ]

    def _format_multicolumn(self, row: List[str]) -> List[str]:
        r"""
        Combine columns belonging to a group to a single multicolumn entry
        according to self.multicolumn_format

        e.g.:
        a &  &  & b & c &
        will become
        \multicolumn{3}{l}{a} & b & \multicolumn{2}{l}{c}
        """
        row2 = list(row[: self._ilevels])
        ncol = 1
        coltext = ""

        def append_col():
            # write multicolumn if needed
            if ncol > 1:
                row2.append(
                    f"\\multicolumn{{{ncol:d}}}{{{self.multicolumn_format}}}"
                    f"{{{coltext.strip()}}}"
                )
            # don't modify where not needed
            else:
                row2.append(coltext)

        for c in row[self._ilevels :]:
            # if next col has text, write the previous
            if c.strip():
                if coltext:
                    append_col()
                coltext = c
                ncol = 1
            # if not, add it to the previous multicolumn
            else:
                ncol += 1
        # write last column name
        if coltext:
            append_col()
        return row2

    def _format_multirow(self, row: List[str], i: int) -> List[str]:
        r"""
        Check following rows, whether row should be a multirow

        e.g.:     becomes:
        a & 0 &   \multirow{2}{*}{a} & 0 &
          & 1 &     & 1 &
        b & 0 &   \cline{1-2}
                  b & 0 &
        """
        for j in range(self._ilevels):
            if row[j].strip():
                nrow = 1
                for r in self.strrows[i + 1 :]:
                    if not r[j].strip():
                        nrow += 1
                    else:
                        break
                if nrow > 1:
                    # overwrite non-multirow entry
                    row[j] = f"\\multirow{{{nrow:d}}}{{*}}{{{row[j].strip()}}}"
                    # save when to end the current block with \cline
                    self.clinebuf.append([i + nrow - 1, j + 1])
        return row

    def _compose_cline(self, i: int, icol: int) -> str:
        """
        Print clines after multirow-blocks are finished.
        """
        lst = []
        for cl in self.clinebuf:
            if cl[0] == i:
                lst.append(f"\n\\cline{{{cl[1]:d}-{icol:d}}}")
                # remove entries that have been written to buffer
                self.clinebuf = [x for x in self.clinebuf if x[0] != i]
        return "".join(lst)


class RowHeaderIterator(RowCreator):
    def __iter__(self):
        for row_num, row in enumerate(self.strrows):
            if row_num < self._header_row_num:
                yield self.get_strrow(row_num, row)


class RowBodyIterator(RowCreator):
    def __iter__(self):
        for row_num, row in enumerate(self.strrows):
            if row_num >= self._header_row_num:
                yield self.get_strrow(row_num, row)


class LatexFormatterAbstract(ABC):
    def _compose_string(self) -> str:
        elements = [
            self._compose_env_begin(),
            self._compose_top_separator(),
            self._compose_header(),
            self._compose_middle_separator(),
            self._compose_env_body(),
            self._compose_bottom_separator(),
            self._compose_env_end(),
        ]
        result = "\n".join([item for item in elements if item])
        trailing_newline = "\n"
        return result + trailing_newline

    @abstractmethod
    def _compose_env_begin(self):
        pass

    @abstractmethod
    def _compose_top_separator(self):
        pass

    @abstractmethod
    def _compose_header(self):
        pass

    @abstractmethod
    def _compose_middle_separator(self):
        pass

    @abstractmethod
    def _compose_env_body(self):
        pass

    @abstractmethod
    def _compose_bottom_separator(self):
        pass

    @abstractmethod
    def _compose_env_end(self):
        pass


class LatexFormatter(TableFormatter, LatexFormatterAbstract):
    """
    Used to render a DataFrame to a LaTeX tabular/longtable environment output.

    Parameters
    ----------
    formatter : `DataFrameFormatter`
    column_format : str, default None
        The columns format as specified in `LaTeX table format
        <https://en.wikibooks.org/wiki/LaTeX/Tables>`__ e.g 'rcl' for 3 columns

    See Also
    --------
    HTMLFormatter
    """

    def __init__(
        self,
        formatter: DataFrameFormatter,
        column_format: Optional[str] = None,
        multicolumn: bool = False,
        multicolumn_format: Optional[str] = None,
        multirow: bool = False,
        caption: Optional[str] = None,
        label: Optional[str] = None,
        position: Optional[str] = None,
    ):
        self.fmt = formatter
        self.frame = self.fmt.frame
        self.column_format = column_format
        self.multicolumn = multicolumn
        self.multicolumn_format = multicolumn_format
        self.multirow = multirow
        self.caption = caption
        self.label = label
        self.position = position

    def write_result(self, buf: IO[str]) -> None:
        """
        Render a DataFrame to a LaTeX tabular, longtable, or table/tabular
        environment output.
        """
        buf.write(self._compose_string())

    @property
    def column_format(self):
        return self._column_format

    @column_format.setter
    def column_format(self, input_column_format):
        if input_column_format is None:
            self._column_format = (
                self._get_index_format() + self._get_column_format_based_on_dtypes()
            )
        elif not isinstance(input_column_format, str):  # pragma: no cover
            raise AssertionError(
                f"column_format must be str or unicode, "
                f"not {type(input_column_format)}"
            )
        else:
            self._column_format = input_column_format

    def _get_column_format_based_on_dtypes(self):
        def get_col_type(dtype):
            if issubclass(dtype.type, np.number):
                return "r"
            return "l"

        dtypes = self.frame.dtypes._values
        return "".join(map(get_col_type, dtypes))

    def _get_index_format(self):
        if self.fmt.index:
            return "l" * self.frame.index.nlevels
        return ""

    @property
    def position_macro(self):
        return f"[{self.position}]" if self.position else ""

    @property
    def caption_macro(self):
        return f"\\caption{{{self.caption}}}" if self.caption else ""

    @property
    def label_macro(self):
        return f"\\label{{{self.label}}}" if self.label else ""

    def _create_row_iterator(self, over):
        kwargs = dict(
            fmt=self.fmt,
            multicolumn=self.multicolumn,
            multicolumn_format=self.multicolumn_format,
            multirow=self.multirow,
        )
        if over == "header":
            return RowHeaderIterator(**kwargs)
        elif over == "body":
            return RowBodyIterator(**kwargs)

    def _compose_header(self):
        iterator = self._create_row_iterator(over="header")
        return "\n".join(list(iterator))

    def _compose_top_separator(self):
        return "\\toprule"

    def _compose_middle_separator(self):
        return "\\midrule" if self._is_separator_required() else ""

    def _compose_env_body(self):
        iterator = self._create_row_iterator(over="body")
        return "\n".join(list(iterator))

    def _is_separator_required(self):
        return self._compose_header() and self._compose_env_body()


class LatexTableFormatter(LatexFormatter):
    def _compose_env_begin(self):
        elements = [
            f"\\begin{{table}}{self.position_macro}",
            f"\\centering",
            f"{self.caption_macro}",
            f"{self.label_macro}",
            f"\\begin{{tabular}}{{{self.column_format}}}",
        ]
        return "\n".join([item for item in elements if item])

    def _compose_bottom_separator(self):
        return "\\bottomrule"

    def _compose_env_end(self):
        return "\n".join(["\\end{tabular}", "\\end{table}"])


class LatexTabularFormatter(LatexFormatter):
    def _compose_env_begin(self):
        return f"\\begin{{tabular}}{{{self.column_format}}}"

    def _compose_bottom_separator(self):
        return "\\bottomrule"

    def _compose_env_end(self):
        return "\\end{tabular}"


class LatexLongTableFormatter(LatexFormatter):
    def _compose_env_begin(self):
        first_row = (
            f"\\begin{{longtable}}{self.position_macro}" f"{{{self.column_format}}}"
        )
        elements = [first_row, f"{self._caption_and_label()}"]
        return "\n".join([item for item in elements if item])

    def _caption_and_label(self):
        if not self.caption and not self.label:
            return ""
        elif self.caption or self.label:
            double_backslash = "\\\\"
            elements = [f"{self.caption_macro}", f"{self.label_macro}"]
            caption_and_label = "\n".join([item for item in elements if item])
            caption_and_label += double_backslash
            return caption_and_label

    def _compose_middle_separator(self):
        iterator = self._create_row_iterator(over="header")
        elements = [
            "\\midrule",
            "\\endhead",
            "\\midrule",
            f"\\multicolumn{{{len(iterator.strcols)}}}{{r}}"
            "{{Continued on next page}} \\\\",
            "\\midrule",
            "\\endfoot\n",
            "\\bottomrule",
            "\\endlastfoot",
        ]
        if self._is_separator_required():
            return "\n".join(elements)
        return ""

    def _compose_bottom_separator(self):
        return ""

    def _compose_env_end(self):
        return "\\end{longtable}"
