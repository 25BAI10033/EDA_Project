"""Data Cleaning and Preprocessing Engine.

Phase 4: Missing value imputation/removal, duplicate detection/removal,
type casting, IQR outlier capping/removal, categorical encoding (Label & One-Hot),
numerical scaling (Min-Max & Z-Score), and column management (Rename & Drop).
All processing is purely in-memory and never mutates original dataset sources.
"""

import io
import json
import logging
import os
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from backend.services.eda_engine import (
    EDAEngine,
    clean_val,
    DatasetValidationError,
)

logger = logging.getLogger("cleaning_engine")


class CleaningEngine:
    """Core engine for data preprocessing, cleaning transformations, and export generation."""

    def __init__(self, eda_engine: EDAEngine = None) -> None:
        self.eda_engine = eda_engine or EDAEngine()

    @staticmethod
    def normalize_operations(operations_input: Any) -> List[Dict[str, Any]]:
        """Normalize operations input from JSON string, dictionary, or list into an ordered sequence."""
        if isinstance(operations_input, str):
            try:
                operations_input = json.loads(operations_input)
            except Exception as exc:
                raise DatasetValidationError(f"Invalid JSON in operations: {str(exc)}") from exc

        if isinstance(operations_input, list):
            return operations_input

        if isinstance(operations_input, dict):
            # Convert structured categorized dictionary into an ordered pipeline
            normalized_list: List[Dict[str, Any]] = []

            # 1. Column renames first
            if "rename_columns" in operations_input:
                for old_n, new_n in operations_input["rename_columns"].items():
                    normalized_list.append({"type": "rename_column", "old_name": old_n, "new_name": new_n})

            # 2. Column drops
            if "drop_columns" in operations_input and operations_input["drop_columns"]:
                normalized_list.append({"type": "drop_columns", "columns": operations_input["drop_columns"]})

            # 3. Duplicate handling
            if operations_input.get("drop_duplicates"):
                dup_cfg = operations_input["drop_duplicates"]
                if isinstance(dup_cfg, dict):
                    normalized_list.append({
                        "type": "drop_duplicates",
                        "subset": dup_cfg.get("subset"),
                        "keep": dup_cfg.get("keep", "first"),
                    })
                else:
                    normalized_list.append({"type": "drop_duplicates", "keep": "first"})

            # 4. Type conversions
            if "type_conversions" in operations_input:
                for conv in operations_input["type_conversions"]:
                    normalized_list.append({"type": "convert_type", **conv})

            # 5. Missing values
            if "missing_values" in operations_input:
                for mv in operations_input["missing_values"]:
                    normalized_list.append({"type": "fill_missing", **mv})

            # 6. Outliers
            if "outliers" in operations_input:
                for out in operations_input["outliers"]:
                    normalized_list.append({"type": "handle_outliers", **out})

            # 7. Encoding
            if "encodings" in operations_input:
                for enc in operations_input["encodings"]:
                    normalized_list.append({"type": "encode_column", **enc})

            # 8. Scaling
            if "scaling" in operations_input:
                for sc in operations_input["scaling"]:
                    normalized_list.append({"type": "scale_column", **sc})

            return normalized_list

        raise DatasetValidationError("Operations must be a list of step objects or a structured configuration map.")

    def apply_operations(self, df_original: pd.DataFrame, operations: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """Sequentially execute clean operations on a deep copy of df_original.

        Never alters the original DataFrame instance.
        Returns: (df_cleaned, operations_log, warnings)
        """
        df = df_original.copy(deep=True)
        log: List[str] = []
        warnings: List[str] = []

        for idx, op in enumerate(operations):
            if not isinstance(op, dict):
                raise DatasetValidationError(f"Operation #{idx + 1} must be an object.")

            op_type = op.get("type", "").lower().strip()
            if not op_type:
                raise DatasetValidationError(f"Operation #{idx + 1} is missing the required 'type' field.")

            # -------------------------------------------------------------
            # 1. Missing Values
            # -------------------------------------------------------------
            if op_type in ("fill_missing", "drop_missing", "missing_values"):
                strategy = op.get("strategy", "").lower().strip()
                col = op.get("column")

                if strategy == "drop_rows":
                    before = len(df)
                    if col and col != "all":
                        if col not in df.columns:
                            raise DatasetValidationError(f"Column '{col}' does not exist for dropping missing values.")
                        df = df.dropna(subset=[col])
                        dropped = before - len(df)
                        log.append(f"Dropped {dropped} row(s) containing missing values in '{col}'.")
                    else:
                        df = df.dropna()
                        dropped = before - len(df)
                        log.append(f"Dropped {dropped} row(s) containing any missing values across all columns.")

                elif strategy in ("mean", "median"):
                    if not col or col not in df.columns:
                        raise DatasetValidationError(f"Valid column required for {strategy} imputation.")
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        raise DatasetValidationError(f"Column '{col}' must be numerical for {strategy} imputation.")

                    missing_count = int(df[col].isna().sum())
                    if missing_count > 0:
                        calc_val = float(df[col].mean()) if strategy == "mean" else float(df[col].median())
                        if np.isnan(calc_val):
                            warnings.append(f"Column '{col}' has no non-null values; skipped {strategy} fill.")
                        else:
                            df[col] = df[col].fillna(round(calc_val, 4))
                            log.append(f"Filled {missing_count} missing value(s) in '{col}' with {strategy} ({round(calc_val, 4)}).")
                    else:
                        log.append(f"No missing values in '{col}' to fill with {strategy}.")

                elif strategy == "mode":
                    if not col or col not in df.columns:
                        raise DatasetValidationError("Valid column required for mode imputation.")
                    missing_count = int(df[col].isna().sum())
                    if missing_count > 0:
                        modes = df[col].mode(dropna=True)
                        if len(modes) > 0:
                            mode_val = modes.iloc[0]
                            df[col] = df[col].fillna(mode_val)
                            log.append(f"Filled {missing_count} missing value(s) in '{col}' with mode ('{mode_val}').")
                        else:
                            warnings.append(f"Column '{col}' has no non-null mode; skipped mode fill.")
                    else:
                        log.append(f"No missing values in '{col}' to fill with mode.")

                elif strategy == "custom":
                    if not col or col not in df.columns:
                        raise DatasetValidationError("Valid column required for custom value imputation.")
                    if "fill_value" not in op:
                        raise DatasetValidationError(f"Missing 'fill_value' parameter for custom imputation on '{col}'.")
                    fill_val = op.get("fill_value")
                    missing_count = int(df[col].isna().sum())
                    if missing_count > 0:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            try:
                                fill_val = float(fill_val) if "." in str(fill_val) else int(fill_val)
                            except (ValueError, TypeError):
                                pass
                        df[col] = df[col].fillna(fill_val)
                        log.append(f"Filled {missing_count} missing value(s) in '{col}' with custom value ({fill_val}).")
                    else:
                        log.append(f"No missing values in '{col}' to fill with custom value.")
                else:
                    raise DatasetValidationError(f"Unsupported missing value strategy '{strategy}'. Use 'drop_rows', 'mean', 'median', 'mode', or 'custom'.")

            # -------------------------------------------------------------
            # 2. Duplicate Handling
            # -------------------------------------------------------------
            elif op_type in ("drop_duplicates", "duplicates"):
                before = len(df)
                subset = op.get("subset")
                if subset:
                    if not isinstance(subset, list) or not all(c in df.columns for c in subset):
                        raise DatasetValidationError("Subset columns for duplicate removal do not exist.")
                else:
                    subset = None

                keep = op.get("keep", "first")
                if keep not in ("first", "last", False):
                    keep = "first"

                df = df.drop_duplicates(subset=subset, keep=keep)
                dropped = before - len(df)
                log.append(f"Removed {dropped} duplicate row(s) (preserved {keep} occurrence).")

            # -------------------------------------------------------------
            # 3. Data Type Conversion
            # -------------------------------------------------------------
            elif op_type in ("convert_type", "type_conversion"):
                col = op.get("column")
                target = op.get("target_type", "").lower().strip()
                if not col or col not in df.columns:
                    raise DatasetValidationError(f"Column '{col}' does not exist for type conversion.")

                if target in ("int", "integer"):
                    df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")
                    log.append(f"Converted column '{col}' to integer.")
                elif target in ("float", "numeric", "number"):
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
                    log.append(f"Converted column '{col}' to float.")
                elif target in ("str", "string", "text"):
                    df[col] = df[col].astype(str).replace({"nan": None, "<NA>": None})
                    log.append(f"Converted column '{col}' to string.")
                elif target in ("datetime", "date"):
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    log.append(f"Converted column '{col}' to datetime.")
                else:
                    raise DatasetValidationError(f"Unsupported target type '{target}'. Choose integer, float, string, or datetime.")

            # -------------------------------------------------------------
            # 4. Outlier Handling (IQR Method)
            # -------------------------------------------------------------
            elif op_type in ("handle_outliers", "outliers"):
                col = op.get("column")
                action = op.get("action", op.get("method", "")).lower().strip()
                if not col or col not in df.columns:
                    raise DatasetValidationError(f"Column '{col}' does not exist for outlier treatment.")
                if not pd.api.types.is_numeric_dtype(df[col]):
                    raise DatasetValidationError(f"Column '{col}' must be numerical for outlier treatment.")

                finite_series = df[col].dropna()
                finite_series = finite_series[np.isfinite(finite_series)]
                if len(finite_series) < 4:
                    warnings.append(f"Column '{col}' has insufficient finite observations for IQR calculation.")
                    continue

                q1 = float(finite_series.quantile(0.25))
                q3 = float(finite_series.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr

                if action == "remove":
                    before = len(df)
                    mask = (df[col].isna()) | ((df[col] >= lower) & (df[col] <= upper))
                    df = df[mask]
                    removed = before - len(df)
                    log.append(f"Removed {removed} outlier row(s) from '{col}' (outside [{round(lower, 2)}, {round(upper, 2)}]).")
                elif action == "cap":
                    outlier_count = int(((df[col] < lower) | (df[col] > upper)).sum())
                    df[col] = df[col].clip(lower=lower, upper=upper)
                    log.append(f"Capped {outlier_count} outlier value(s) in '{col}' to [{round(lower, 2)}, {round(upper, 2)}].")
                else:
                    raise DatasetValidationError(f"Unsupported outlier action '{action}'. Choose 'remove' or 'cap'.")

            # -------------------------------------------------------------
            # 5. Categorical Encoding (Label & One-Hot)
            # -------------------------------------------------------------
            elif op_type in ("encode_column", "encoding"):
                col = op.get("column")
                method = op.get("method", "").lower().strip()
                if not col or col not in df.columns:
                    raise DatasetValidationError(f"Column '{col}' does not exist for categorical encoding.")

                if method in ("label", "label_encode"):
                    unique_cats = df[col].dropna().unique().tolist()
                    mapping = {cat: idx for idx, cat in enumerate(unique_cats)}
                    df[col] = df[col].map(mapping).astype("Int64")
                    log.append(f"Applied Label Encoding on '{col}' ({len(unique_cats)} classes mapped to 0..{len(unique_cats)-1}).")
                elif method in ("one_hot", "onehot", "one_hot_encode"):
                    before_cols = len(df.columns)
                    df = pd.get_dummies(df, columns=[col], prefix=col, dtype=int)
                    added_cols = len(df.columns) - (before_cols - 1)
                    log.append(f"Applied One-Hot Encoding on '{col}' (generated {added_cols} indicator columns).")
                else:
                    raise DatasetValidationError(f"Unsupported encoding method '{method}'. Choose 'label' or 'one_hot'.")

            # -------------------------------------------------------------
            # 6. Numerical Scaling (Min-Max & Standardization)
            # -------------------------------------------------------------
            elif op_type in ("scale_column", "scaling"):
                col = op.get("column")
                method = op.get("method", "").lower().strip()
                if not col or col not in df.columns:
                    raise DatasetValidationError(f"Column '{col}' does not exist for scaling.")
                if not pd.api.types.is_numeric_dtype(df[col]):
                    raise DatasetValidationError(f"Column '{col}' must be numerical for scaling.")

                if method in ("min_max", "minmax", "normalize"):
                    min_val = float(df[col].min())
                    max_val = float(df[col].max())
                    if max_val == min_val:
                        warnings.append(f"Column '{col}' has identical min and max ({min_val}); scaled to 0.0.")
                        df[col] = df[col] * 0.0
                    else:
                        df[col] = (df[col] - min_val) / (max_val - min_val)
                    log.append(f"Applied Min-Max Normalization on '{col}' (scaled to [0, 1]).")
                elif method in ("z_score", "standardize", "zscore", "standard"):
                    mean_val = float(df[col].mean())
                    std_val = float(df[col].std())
                    if std_val == 0 or np.isnan(std_val):
                        warnings.append(f"Column '{col}' has zero standard deviation; scaled to 0.0.")
                        df[col] = df[col] * 0.0
                    else:
                        df[col] = (df[col] - mean_val) / std_val
                    log.append(f"Applied Standardization (Z-score) on '{col}' (mean=0, std=1).")
                else:
                    raise DatasetValidationError(f"Unsupported scaling method '{method}'. Choose 'min_max' or 'standardize'.")

            # -------------------------------------------------------------
            # 7. Column Management (Rename & Remove)
            # -------------------------------------------------------------
            elif op_type in ("rename_column", "rename"):
                old_name = op.get("old_name", op.get("column"))
                new_name = op.get("new_name")
                if not old_name or old_name not in df.columns:
                    raise DatasetValidationError(f"Column '{old_name}' does not exist to rename.")
                if not new_name or not str(new_name).strip():
                    raise DatasetValidationError("New column name cannot be empty.")
                new_name = str(new_name).strip()
                if new_name in df.columns and new_name != old_name:
                    raise DatasetValidationError(f"A column named '{new_name}' already exists in the dataset.")
                df = df.rename(columns={old_name: new_name})
                log.append(f"Renamed column '{old_name}' to '{new_name}'.")

            elif op_type in ("drop_column", "remove_column", "drop_columns"):
                target_cols = op.get("columns", [op.get("column")])
                if isinstance(target_cols, str):
                    target_cols = [target_cols]
                target_cols = [c for c in target_cols if c]
                for tc in target_cols:
                    if tc not in df.columns:
                        raise DatasetValidationError(f"Column '{tc}' does not exist to remove.")
                if len(df.columns) <= len(target_cols):
                    raise DatasetValidationError("Cannot remove all columns. At least 1 column must remain in dataset.")
                df = df.drop(columns=target_cols)
                log.append(f"Removed column(s): {', '.join(target_cols)}.")

            else:
                raise DatasetValidationError(f"Unknown operation type '{op_type}'.")

        if len(df) == 0:
            raise DatasetValidationError("Cleaning operations resulted in an empty dataset (0 rows remain).")
        if len(df.columns) == 0:
            raise DatasetValidationError("Cleaning operations resulted in 0 columns.")

        return df, log, warnings

    def preview_clean(self, filename: str, content: bytes, operations_input: Any) -> Dict[str, Any]:
        """Compute before vs after summary and 5-row preview without persisting changes."""
        df_original, _, filename = self.eda_engine.load_dataframe(filename, content)
        operations = self.normalize_operations(operations_input)

        # Apply operations on deep copy
        df_cleaned, log, warnings = self.apply_operations(df_original, operations)

        # Helper to extract sanitized 5-row preview
        def extract_summary(d: pd.DataFrame) -> Dict[str, Any]:
            cols = [str(c) for c in d.columns]
            dtypes = {str(c): str(d[c].dtype) for c in d.columns}
            preview_rows: List[Dict[str, Any]] = []
            for r in d.head(5).to_dict(orient="records"):
                preview_rows.append({str(c): clean_val(r.get(c)) for c in d.columns})
            return {
                "row_count": int(len(d)),
                "column_count": int(len(d.columns)),
                "columns": cols,
                "data_types": dtypes,
                "preview": preview_rows,
            }

        original_summary = extract_summary(df_original)
        cleaned_summary = extract_summary(df_cleaned)

        diff_summary = {
            "rows_delta": cleaned_summary["row_count"] - original_summary["row_count"],
            "columns_delta": cleaned_summary["column_count"] - original_summary["column_count"],
            "columns_added": [c for c in cleaned_summary["columns"] if c not in original_summary["columns"]],
            "columns_removed": [c for c in original_summary["columns"] if c not in cleaned_summary["columns"]],
        }

        return {
            "filename": filename,
            "original_summary": original_summary,
            "cleaned_summary": cleaned_summary,
            "diff_summary": diff_summary,
            "operations_applied": log,
            "warnings": warnings,
        }

    def _serialize_dataframe(
        self,
        df: pd.DataFrame,
        base_name: str,
        prefix: str,
        output_format: str = "csv",
    ) -> Tuple[bytes, str, str]:
        """Convert a DataFrame into downloadable file bytes (CSV, XLSX, or JSON)."""
        clean_format = output_format.lower().strip().replace(".", "")

        if clean_format in ("xlsx", "excel"):
            bio = io.BytesIO()
            df.to_excel(bio, index=False, engine="openpyxl")
            export_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            export_filename = f"{prefix}{base_name}.xlsx"
        elif clean_format in ("json", "ndjson", "jsonl"):
            # Format as standard JSON records
            records = json.loads(df.to_json(orient="records", date_format="iso"))
            # Unescape any stringified JSON arrays/objects if they represent structured JSON
            for row in records:
                for k, v in row.items():
                    if isinstance(v, str) and ((v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}"))):
                        try:
                            row[k] = json.loads(v)
                        except Exception:
                            pass
            if clean_format in ("jsonl", "ndjson"):
                lines = [json.dumps(r, ensure_ascii=False) for r in records]
                json_str = "\n".join(lines) + "\n"
                mime_type = "application/x-ndjson; charset=utf-8"
                export_filename = f"{prefix}{base_name}.jsonl"
            else:
                json_str = json.dumps(records, indent=2, ensure_ascii=False)
                mime_type = "application/json; charset=utf-8"
                export_filename = f"{prefix}{base_name}.json"
            export_bytes = json_str.encode("utf-8")
        else:
            # Default to CSV
            csv_str = df.to_csv(index=False)
            export_bytes = csv_str.encode("utf-8")
            mime_type = "text/csv; charset=utf-8"
            export_filename = f"{prefix}{base_name}.csv"

        return export_bytes, mime_type, export_filename

    def export_cleaned_dataset(
        self,
        filename: str,
        content: bytes,
        operations_input: Any,
        output_format: str = "csv",
    ) -> Tuple[bytes, str, str]:
        """Execute cleaning pipeline and render downloadable file bytes in-memory.

        Returns: (file_bytes, mime_type, export_filename)
        """
        df_original, _, filename = self.eda_engine.load_dataframe(filename, content)
        operations = self.normalize_operations(operations_input)
        df_cleaned, _, _ = self.apply_operations(df_original, operations)

        base_name, _ = os.path.splitext(filename)
        return self._serialize_dataframe(
            df_cleaned,
            base_name=base_name,
            prefix="cleaned_",
            output_format=output_format,
        )

    def export_original_dataset(
        self,
        filename: str,
        content: bytes,
        output_format: str = "csv",
    ) -> Tuple[bytes, str, str]:
        """Export original uploaded dataset converted into CSV, XLSX, or JSON in-memory.

        Returns: (file_bytes, mime_type, export_filename)
        """
        df_original, _, filename = self.eda_engine.load_dataframe(filename, content)
        base_name, _ = os.path.splitext(filename)
        return self._serialize_dataframe(
            df_original,
            base_name=base_name,
            prefix="original_",
            output_format=output_format,
        )

