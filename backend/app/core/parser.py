from __future__ import annotations

from dataclasses import dataclass
import io
import re
from pathlib import Path
import numpy as np
import pandas as pd

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class ParsedTable:
    filename: str
    columns: list[str]
    data: np.ndarray
    preview_rows: list[list[float | str]]
    skip_rows_used: int
    delimiter_used: str


def is_image_file(filename: str, content: bytes | None = None) -> bool:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return True
    if content:
        if content.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"BM", b"II*\x00", b"MM\x00*")):
            return True
    return False


def _decode_bytes(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _split_line(line: str, delimiter: str) -> list[str]:
    if delimiter == "whitespace":
        return re.split(r"\s+", line.strip())
    return [cell.strip() for cell in line.split(delimiter)]


def _is_numeric_row(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    valid = 0
    for t in tokens:
        if t == "":
            continue
        try:
            val = float(t)
            if np.isfinite(val):
                valid += 1
        except ValueError:
            return False
    return valid >= 2


def _detect_delimiter(lines: list[str]) -> str:
    sample = "\n".join(lines[:12])
    for delim in (",", "\t", ";"):
        counts = [len(ln.split(delim)) for ln in lines[:8] if ln.strip()]
        if counts and min(counts) >= 2:
            return delim
    if "," in sample:
        return ","
    if "\t" in sample:
        return "\t"
    if ";" in sample:
        return ";"
    return "whitespace"


def parse_tabular_bytes(
    filename: str,
    content: bytes,
    skip_rows: int | None = None,
    delimiter: str | None = None,
) -> ParsedTable:
    """Parse CSV, TSV, TXT, DAT, XY, ASC, or XLSX experimental files into numeric arrays."""
    ext = Path(filename).suffix.lower()
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(io.BytesIO(content), skiprows=skip_rows or 0)
        # Drop completely empty rows/cols and coerce numeric
        df = df.dropna(how="all").dropna(axis=1, how="all")
        num_df = df.apply(pd.to_numeric, errors="coerce").dropna(how="any")
        if num_df.empty:
            # Maybe metadata rows existed before header; scan rows
            raw_df = pd.read_excel(io.BytesIO(content), header=None)
            header_idx = 0
            for idx, row in raw_df.iterrows():
                vals = [str(v) for v in row.tolist() if pd.notna(v)]
                if len(vals) >= 2 and not _is_numeric_row(vals):
                    header_idx = int(idx)
                elif _is_numeric_row(vals):
                    break
            df = pd.read_excel(io.BytesIO(content), skiprows=header_idx)
            df = df.dropna(how="all").dropna(axis=1, how="all")
            num_df = df.apply(pd.to_numeric, errors="coerce").dropna(how="any")
        columns = [str(c) for c in num_df.columns]
        arr = num_df.to_numpy(dtype=float)
        preview = arr[:6].round(6).tolist()
        return ParsedTable(
            filename=filename,
            columns=columns,
            data=arr,
            preview_rows=preview,
            skip_rows_used=skip_rows or 0,
            delimiter_used="excel",
        )

    text = _decode_bytes(content)
    raw_lines = [ln.strip() for ln in text.splitlines()]
    non_empty = [ln for ln in raw_lines if ln]
    if skip_rows is not None and skip_rows > 0:
        non_empty = non_empty[skip_rows:]

    # Strip leading comment lines unless manual skip_rows was explicitly given to keep them
    comment_skipped = 0
    cleaned_lines: list[str] = []
    started = False
    for ln in non_empty:
        if not started and (ln.startswith("#") or ln.startswith("//") or ln.startswith("%")):
            comment_skipped += 1
            continue
        if ln.startswith("#") or ln.startswith("//"):
            continue
        started = True
        cleaned_lines.append(ln)

    if not cleaned_lines:
        raise ValueError(f"File '{filename}' contains no tabular rows.")

    delim = delimiter or _detect_delimiter(cleaned_lines)

    # Locate first numeric row; anything right above it with matching width is the header
    numeric_start = None
    for idx, ln in enumerate(cleaned_lines):
        toks = _split_line(ln, delim)
        if _is_numeric_row(toks):
            numeric_start = idx
            break

    if numeric_start is None:
        raise ValueError(f"Could not find numeric data rows in '{filename}'.")

    first_toks = _split_line(cleaned_lines[numeric_start], delim)
    n_cols = len(first_toks)
    if numeric_start > 0:
        cand_header = _split_line(cleaned_lines[numeric_start - 1], delim)
        if len(cand_header) == n_cols:
            columns = cand_header
        elif len(cand_header) > 0:
            columns = [cand_header[i] if i < len(cand_header) else f"Col {i + 1}" for i in range(n_cols)]
        else:
            columns = [f"Col {i + 1}" for i in range(n_cols)]
    else:
        columns = [f"Col {i + 1}" for i in range(n_cols)]

    rows: list[list[float]] = []
    for ln in cleaned_lines[numeric_start:]:
        toks = _split_line(ln, delim)
        if len(toks) < n_cols:
            continue
        vals: list[float] = []
        ok = True
        for t in toks[:n_cols]:
            try:
                v = float(t)
                if not np.isfinite(v):
                    ok = False
                    break
                vals.append(v)
            except ValueError:
                ok = False
                break
        if ok:
            rows.append(vals)

    if not rows:
        raise ValueError(f"No valid numeric rows extracted from '{filename}'.")

    arr = np.asarray(rows, dtype=float)
    return ParsedTable(
        filename=filename,
        columns=columns,
        data=arr,
        preview_rows=arr[:6].round(6).tolist(),
        skip_rows_used=(skip_rows or 0) + comment_skipped + numeric_start,
        delimiter_used=delim,
    )
