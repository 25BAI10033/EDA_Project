"""EDA (Exploratory Data Analysis) Engine service.

Data profiling, statistical analysis, and dataset inspection routines.
Phase 2: In-memory dataset parsing, validation, and preview generation.
Phase 3: Automated Exploratory Data Analysis (EDA) engine.
"""

import io
import json
import logging
import math
import os
import warnings
import zipfile
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("eda_engine")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json", ".jsonl", ".ndjson"}


class DatasetValidationError(Exception):
    """Custom exception for expected dataset validation errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def clean_val(val: Any) -> Any:
    """Sanitize values for strict JSON serialization.

    Converts NaN, Infinity, and nulls to None, timestamps to ISO strings,
    and numpy scalars to Python native types.
    """
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(float(val), 4)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (pd.Timestamp, pd.Timedelta)):
        return str(val)
    return val


def format_memory_size(bytes_val: int) -> str:
    """Format memory usage in bytes into human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{round(bytes_val / 1024, 2)} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{round(bytes_val / (1024 * 1024), 2)} MB"
    return f"{round(bytes_val / (1024 * 1024 * 1024), 2)} GB"


class EDAEngine:
    """Core engine for exploratory data analysis and dataset inspection."""

    def __init__(self) -> None:
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return engine operational status."""
        return {"status": "initialized", "ready": True}

    def load_dataframe(self, filename: str, content: bytes) -> Tuple[pd.DataFrame, int, str]:
        """Validate uploaded file attributes and parse content into a Pandas DataFrame in-memory.

        Enforces extension validation, size limit, emptiness checks, and robust parsing.
        """
        if not filename or not filename.strip():
            raise DatasetValidationError("Invalid file name.", status_code=400)

        # 1. Validate file extension
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower not in ALLOWED_EXTENSIONS:
            raise DatasetValidationError(
                f"Unsupported file format '{ext}'. Only CSV (.csv), Excel (.xlsx), and JSON (.json, .jsonl, .ndjson) files are supported.",
                status_code=400,
            )

        # 2. Validate file size and content emptiness
        file_size = len(content)
        if file_size == 0:
            raise DatasetValidationError("The uploaded file is empty.", status_code=400)

        if file_size > MAX_FILE_SIZE:
            raise DatasetValidationError(
                "File exceeds maximum allowed size of 10 MB.",
                status_code=413,
            )

        # 3. Content-level validation & security checks
        if ext_lower == ".xlsx":
            # Verify OpenXML ZIP archive magic header
            if not content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
                raise DatasetValidationError(
                    "Invalid Excel file content. The file does not have a valid OpenXML (.xlsx) archive header.",
                    status_code=400,
                )
            # Inspect ZIP entries to prevent zip-bomb / resource exhaustion and verify OpenXML structure
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    corrupt_entry = zf.testzip()
                    if corrupt_entry is not None:
                        raise DatasetValidationError(
                            f"Corrupted Excel archive: entry '{corrupt_entry}' is damaged.",
                            status_code=400,
                        )
                    # Safe decompression limit: 60 MB uncompressed size
                    total_uncompressed = sum(info.file_size for info in zf.infolist())
                    if total_uncompressed > 60 * 1024 * 1024:
                        raise DatasetValidationError(
                            "Excel file exceeds safe decompression limits (possible decompression bomb).",
                            status_code=400,
                        )
                    namelist = zf.namelist()
                    if not any(name.startswith("xl/") or name == "[Content_Types].xml" for name in namelist):
                        raise DatasetValidationError(
                            "The uploaded file is a zip archive but does not contain valid Excel spreadsheet components.",
                            status_code=400,
                        )
            except zipfile.BadZipFile as bzf:
                raise DatasetValidationError(
                    "Invalid or corrupted Excel file (.xlsx).",
                    status_code=400,
                ) from bzf

        elif ext_lower == ".csv":
            # Inspect first 8 KB for binary null bytes to prevent uploading disguised binary/executable files
            sample_bytes = content[:8192]
            if b"\x00" in sample_bytes:
                raise DatasetValidationError(
                    "Invalid CSV file content. Binary or executable data detected.",
                    status_code=400,
                )

        elif ext_lower in (".json", ".jsonl", ".ndjson"):
            sample_bytes = content[:8192]
            if b"\x00" in sample_bytes:
                raise DatasetValidationError(
                    "Invalid JSON file content. Binary data detected.",
                    status_code=400,
                )

        # 4. Read dataset using Pandas (CSV / Excel / JSON)
        df: pd.DataFrame
        try:
            if ext_lower == ".csv":
                try:
                    df = pd.read_csv(io.BytesIO(content))
                except UnicodeDecodeError:
                    # Fallback to Latin-1 encoding for non-UTF-8 CSVs
                    df = pd.read_csv(io.BytesIO(content), encoding="latin-1")
            elif ext_lower == ".xlsx":
                df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
            elif ext_lower in (".json", ".jsonl", ".ndjson"):
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        text = content.decode("latin-1")
                    except Exception as enc_err:
                        raise DatasetValidationError(
                            "Invalid file encoding. Please upload a valid UTF-8 encoded JSON file.",
                            status_code=400,
                        ) from enc_err

                text_strip = text.strip()
                if not text_strip:
                    raise DatasetValidationError(
                        "The uploaded file is empty.",
                        status_code=400,
                    )

                data: Any = None
                # First attempt parsing standard JSON
                try:
                    data = json.loads(text_strip)
                except json.JSONDecodeError as json_err:
                    # Second attempt: Check if it is JSON Lines / NDJSON (one JSON object per line)
                    lines = [line.strip() for line in text_strip.splitlines() if line.strip()]
                    if len(lines) > 0:
                        records = []
                        try:
                            for line in lines:
                                records.append(json.loads(line))
                            data = records
                        except Exception:
                            raise DatasetValidationError(
                                f"Malformed JSON file: {json_err.msg} at line {json_err.lineno}, column {json_err.colno}.",
                                status_code=400,
                            ) from json_err
                    else:
                        raise DatasetValidationError(
                            f"Malformed JSON file: {json_err.msg} at line {json_err.lineno}, column {json_err.colno}.",
                            status_code=400,
                        ) from json_err

                # Convert parsed JSON structure into tabular records
                records_to_normalize: List[Dict[str, Any]] = []

                if isinstance(data, list):
                    if len(data) == 0:
                        raise DatasetValidationError(
                            "The JSON array is empty and contains no data records.",
                            status_code=400,
                        )
                    # Reject multi-dimensional arrays (list of lists)
                    if any(isinstance(item, list) for item in data):
                        raise DatasetValidationError(
                            "Unsupported JSON structure: Nested multi-dimensional arrays cannot be represented as a single table. Please upload an array of record objects.",
                            status_code=400,
                        )
                    # Reject arrays of scalar primitives
                    if not all(isinstance(item, dict) for item in data):
                        raise DatasetValidationError(
                            "Unsupported JSON structure: JSON array must contain record objects (e.g. [{\"col1\": val1, ...}]), not primitive values.",
                            status_code=400,
                        )
                    records_to_normalize = data

                elif isinstance(data, dict):
                    table_keys = [
                        k for k, v in data.items()
                        if isinstance(v, list) and len(v) > 0 and all(isinstance(item, dict) for item in v)
                    ]
                    # Check for multiple separate tables in one file
                    if len(table_keys) > 1:
                        key_names = ", ".join(repr(k) for k in table_keys)
                        raise DatasetValidationError(
                            f"Unsupported JSON structure: The JSON file contains multiple separate tables ({key_names}) and cannot be represented as a single table without data loss. Please upload each table as a separate dataset.",
                            status_code=400,
                        )
                    elif len(table_keys) == 1:
                        records_to_normalize = data[table_keys[0]]
                    else:
                        # Check if dict values contain multi-dimensional arrays
                        if any(isinstance(v, list) and any(isinstance(elem, list) for elem in v) for v in data.values()):
                            raise DatasetValidationError(
                                "Unsupported JSON structure: The JSON object contains nested multi-dimensional arrays that cannot be represented as a single table.",
                                status_code=400,
                            )
                        # Single dictionary record (flat or nested)
                        records_to_normalize = [data]
                else:
                    raise DatasetValidationError(
                        "Unsupported JSON structure: Root JSON element must be an array of records or a dictionary containing records.",
                        status_code=400,
                    )

                # Requirement 3: Handle nested arrays carefully.
                # Never silently discard data; show a clear error when a structure cannot be represented as one table.
                def inspect_for_unrepresentable_nested_arrays(obj: Any, prefix: str = "") -> None:
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            field_name = f"{prefix}.{k}" if prefix else k
                            if isinstance(v, list):
                                if any(isinstance(elem, (dict, list)) for elem in v):
                                    raise DatasetValidationError(
                                        f"Unsupported JSON structure: Field '{field_name}' contains a nested array of objects/records that cannot be represented as a single table without data loss. Please normalize or flatten nested arrays before uploading.",
                                        status_code=400,
                                    )
                            elif isinstance(v, dict):
                                inspect_for_unrepresentable_nested_arrays(v, field_name)

                for rec in records_to_normalize:
                    inspect_for_unrepresentable_nested_arrays(rec)

                # Safe flattening: flatten nested objects (e.g. user.address.city)
                df = pd.json_normalize(records_to_normalize, max_level=10)

                # Ensure all nested lists or dicts in cells are serialized to JSON strings
                # so hash-dependent Pandas functions (duplicated, unique, describe) never raise TypeError.
                for col in df.columns:
                    df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)

        except (pd.errors.EmptyDataError, DatasetValidationError) as e:
            if isinstance(e, DatasetValidationError):
                raise
            raise DatasetValidationError(
                "The uploaded file is empty or contains no parseable data.",
                status_code=400,
            ) from e
        except pd.errors.ParserError as e:
            raise DatasetValidationError(
                "Failed to parse CSV file. Please ensure the file has a consistent delimiter and format.",
                status_code=400,
            ) from e
        except (zipfile.BadZipFile, ValueError, KeyError) as e:
            if isinstance(e, DatasetValidationError):
                raise
            raise DatasetValidationError(
                "Invalid or corrupted Excel or JSON file. Please ensure the file is properly formatted.",
                status_code=400,
            ) from e
        except Exception as e:
            if isinstance(e, DatasetValidationError):
                raise
            logger.exception("Unexpected error while parsing dataset '%s'", filename)
            raise DatasetValidationError(
                "Could not parse the dataset. Please ensure the file is not corrupted and is formatted properly.",
                status_code=400,
            ) from e

        # 4. Check for missing columns or rows
        if len(df.columns) == 0:
            raise DatasetValidationError(
                "The dataset contains no valid data columns.",
                status_code=400,
            )

        if len(df) == 0:
            raise DatasetValidationError(
                "The dataset contains column headers but no data rows.",
                status_code=400,
            )

        return df, file_size, filename

    @staticmethod
    def detect_file_format(filename: str) -> str:
        """Identify user-facing format label from filename extension."""
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower == ".csv":
            return "CSV"
        elif ext_lower == ".xlsx":
            return "Excel (.xlsx)"
        elif ext_lower in (".jsonl", ".ndjson"):
            return "JSON Lines"
        elif ext_lower == ".json":
            return "JSON"
        return ext_lower.upper().replace(".", "")

    def parse_dataset(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Phase 2: Validate, parse, and extract metadata and 5-row preview.

        Processed purely in-memory with zero disk persistence.
        """
        df, file_size, filename = self.load_dataframe(filename, content)

        row_count = int(len(df))
        column_count = int(len(df.columns))
        columns = [str(c) for c in df.columns]
        data_types = {str(col): str(dtype) for col, dtype in df.dtypes.items()}

        # Extract first 5 rows preview and sanitize for strict JSON compatibility
        preview_df = df.head(5)
        preview_records: List[Dict[str, Any]] = []

        for row in preview_df.to_dict(orient="records"):
            clean_row = {str(col): clean_val(row.get(col)) for col in df.columns}
            preview_records.append(clean_row)

        return {
            "filename": filename,
            "file_format": self.detect_file_format(filename),
            "file_size": file_size,
            "row_count": row_count,
            "column_count": column_count,
            "columns": columns,
            "data_types": data_types,
            "preview": preview_records,
        }

    def analyze_dataset(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Phase 3: Automated Exploratory Data Analysis (EDA).

        Calculates dataset overview, statistical summary, missing values, duplicates,
        column profiles, IQR outliers, correlations, and distribution histograms.
        Processed purely in-memory with zero disk persistence.
        """
        df, file_size, filename = self.load_dataframe(filename, content)

        total_rows = int(len(df))
        total_columns = int(len(df.columns))

        # Detect numerical and categorical column subsets
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = [c for c in df.columns if c not in num_cols]

        memory_bytes = int(df.memory_usage(deep=True).sum())
        memory_formatted = format_memory_size(memory_bytes)

        # -------------------------------------------------------------
        # 1. Dataset Overview
        # -------------------------------------------------------------
        overview = {
            "filename": filename,
            "file_format": self.detect_file_format(filename),
            "file_size": file_size,
            "total_rows": total_rows,
            "total_columns": total_columns,
            "numerical_columns_count": len(num_cols),
            "categorical_columns_count": len(cat_cols),
            "numerical_columns": [str(c) for c in num_cols],
            "categorical_columns": [str(c) for c in cat_cols],
            "memory_usage_bytes": memory_bytes,
            "memory_usage_formatted": memory_formatted,
        }

        # -------------------------------------------------------------
        # 2. Statistical Summary (describe for numerical & categorical)
        # -------------------------------------------------------------
        stats_summary: Dict[str, Any] = {"numerical": {}, "categorical": {}}

        if num_cols:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                desc_num = df[num_cols].describe().to_dict()
            for col, stats in desc_num.items():
                stats_summary["numerical"][str(col)] = {
                    str(k): clean_val(v) for k, v in stats.items()
                }

        if cat_cols:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                desc_cat = df[cat_cols].astype(object).describe().to_dict()
            for col, stats in desc_cat.items():
                stats_summary["categorical"][str(col)] = {
                    str(k): clean_val(v) for k, v in stats.items()
                }

        # -------------------------------------------------------------
        # 3. Missing Values Analysis
        # -------------------------------------------------------------
        missing_cols: List[Dict[str, Any]] = []
        total_missing_cells = 0
        total_cells = total_rows * total_columns

        for col in df.columns:
            m_count = int(df[col].isna().sum())
            total_missing_cells += m_count
            m_pct = round(float((m_count / total_rows) * 100), 2) if total_rows > 0 else 0.0
            missing_cols.append({
                "column": str(col),
                "missing_count": m_count,
                "missing_percentage": m_pct,
                "has_missing": m_count > 0,
                "data_type": str(df[col].dtype),
            })

        missing_cols.sort(key=lambda x: x["missing_count"], reverse=True)

        missing_values = {
            "overall": {
                "total_cells": total_cells,
                "total_missing_cells": total_missing_cells,
                "overall_missing_percentage": (
                    round(float((total_missing_cells / total_cells) * 100), 2)
                    if total_cells > 0
                    else 0.0
                ),
            },
            "columns": missing_cols,
        }

        # -------------------------------------------------------------
        # 4. Duplicate Detection (Do not remove)
        # -------------------------------------------------------------
        dup_count = int(df.duplicated().sum())
        dup_pct = round(float((dup_count / total_rows) * 100), 2) if total_rows > 0 else 0.0
        duplicates = {
            "duplicate_count": dup_count,
            "duplicate_percentage": dup_pct,
            "has_duplicates": dup_count > 0,
            "unique_rows_count": total_rows - dup_count,
        }

        # -------------------------------------------------------------
        # 5. Column Analysis (Types, unique counts, sample unique values)
        # -------------------------------------------------------------
        column_analysis: List[Dict[str, Any]] = []
        for col in df.columns:
            series = df[col]
            u_count = int(series.nunique(dropna=True))
            u_pct = round(float((u_count / total_rows) * 100), 2) if total_rows > 0 else 0.0

            # Collect up to 15 unique sample values
            unique_samples = [clean_val(x) for x in series.dropna().unique()[:15]]

            column_analysis.append({
                "column": str(col),
                "data_type": str(series.dtype),
                "is_numerical": col in num_cols,
                "is_categorical": col in cat_cols,
                "unique_count": u_count,
                "unique_percentage": u_pct,
                "sample_unique_values": unique_samples,
            })

        # -------------------------------------------------------------
        # 6. Outlier Detection (IQR method on numerical columns)
        # -------------------------------------------------------------
        outliers_data: List[Dict[str, Any]] = []
        total_outliers = 0

        for col in num_cols:
            col_series = df[col].dropna()
            # Filter finite numbers to prevent inf issues
            col_finite = col_series[np.isfinite(col_series)]

            if len(col_finite) >= 4:
                q1 = float(col_finite.quantile(0.25))
                q3 = float(col_finite.quantile(0.75))
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outlier_series = col_finite[(col_finite < lower_bound) | (col_finite > upper_bound)]
                o_count = int(len(outlier_series))
                o_pct = round(float((o_count / len(col_finite)) * 100), 2) if len(col_finite) > 0 else 0.0
                total_outliers += o_count

                outliers_data.append({
                    "column": str(col),
                    "q1": clean_val(q1),
                    "q3": clean_val(q3),
                    "iqr": clean_val(iqr),
                    "lower_bound": clean_val(lower_bound),
                    "upper_bound": clean_val(upper_bound),
                    "outlier_count": o_count,
                    "outlier_percentage": o_pct,
                    "sample_outliers": [clean_val(x) for x in outlier_series.head(10).tolist()],
                })
            else:
                outliers_data.append({
                    "column": str(col),
                    "q1": None,
                    "q3": None,
                    "iqr": None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "outlier_count": 0,
                    "outlier_percentage": 0.0,
                    "sample_outliers": [],
                })

        outliers_summary = {
            "total_outliers_detected": total_outliers,
            "columns": outliers_data,
        }

        # -------------------------------------------------------------
        # 7. Correlation Analysis (between numerical columns)
        # -------------------------------------------------------------
        correlation: Dict[str, Any] = {
            "numerical_columns": [str(c) for c in num_cols],
            "matrix": {},
            "top_correlations": [],
            "message": None,
        }

        if len(num_cols) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                corr_df = df[num_cols].corr(method="pearson")
            matrix_dict: Dict[str, Dict[str, Any]] = {}
            pairs: List[Dict[str, Any]] = []

            for i, c1 in enumerate(num_cols):
                matrix_dict[str(c1)] = {}
                for j, c2 in enumerate(num_cols):
                    val = corr_df.loc[c1, c2]
                    cleaned_r = clean_val(val)
                    matrix_dict[str(c1)][str(c2)] = cleaned_r

                    if i < j and cleaned_r is not None:
                        pairs.append({
                            "col1": str(c1),
                            "col2": str(c2),
                            "correlation": cleaned_r,
                            "abs_correlation": round(abs(cleaned_r), 4),
                        })

            pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
            correlation["matrix"] = matrix_dict
            correlation["top_correlations"] = pairs
        else:
            correlation["message"] = "At least 2 numerical columns are required for correlation analysis."

        # -------------------------------------------------------------
        # 8. Distribution Analysis (Numerical & Categorical)
        # -------------------------------------------------------------
        distributions: Dict[str, Any] = {"numerical": {}, "categorical": {}}

        # Numerical distributions (histogram-ready bins)
        for col in num_cols:
            col_series = df[col].dropna()
            col_finite = col_series[np.isfinite(col_series)]

            if len(col_finite) > 0:
                num_unique = len(col_finite.unique())
                num_bins = min(10, max(2, num_unique)) if num_unique > 1 else 1
                counts, bin_edges = np.histogram(col_finite, bins=num_bins)

                bins_list = []
                for i in range(len(counts)):
                    b_start = round(float(bin_edges[i]), 2)
                    b_end = round(float(bin_edges[i + 1]), 2)
                    bins_list.append({
                        "bin_start": b_start,
                        "bin_end": b_end,
                        "label": f"{b_start} - {b_end}",
                        "count": int(counts[i]),
                    })

                distributions["numerical"][str(col)] = {
                    "min": clean_val(col_finite.min()),
                    "max": clean_val(col_finite.max()),
                    "mean": clean_val(col_finite.mean()),
                    "median": clean_val(col_finite.median()),
                    "std": clean_val(col_finite.std()),
                    "bins": bins_list,
                }

        # Categorical distributions (frequencies)
        for col in cat_cols:
            val_counts = df[col].value_counts(dropna=False)
            categories_list: List[Dict[str, Any]] = []
            top_n = val_counts.head(10)
            remaining_count = int(val_counts.iloc[10:].sum()) if len(val_counts) > 10 else 0

            for cat, cnt in top_n.items():
                cat_name = "(Missing)" if pd.isna(cat) else str(cat)
                pct = round(float((cnt / total_rows) * 100), 2) if total_rows > 0 else 0.0
                categories_list.append({
                    "category": cat_name,
                    "count": int(cnt),
                    "percentage": pct,
                })

            if remaining_count > 0:
                pct = round(float((remaining_count / total_rows) * 100), 2) if total_rows > 0 else 0.0
                categories_list.append({
                    "category": f"Other ({len(val_counts) - 10} values)",
                    "count": remaining_count,
                    "percentage": pct,
                })

            distributions["categorical"][str(col)] = categories_list

        return {
            "overview": overview,
            "statistical_summary": stats_summary,
            "missing_values": missing_values,
            "duplicates": duplicates,
            "column_analysis": column_analysis,
            "outliers": outliers_summary,
            "correlation": correlation,
            "distributions": distributions,
        }
