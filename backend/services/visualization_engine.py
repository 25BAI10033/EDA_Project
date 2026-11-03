"""Data Visualization Engine.

Phase 5: Generates structured, statistical chart payloads for interactive
frontend visualization (Bar, Line, Pie/Donut, Histogram, Scatter, Box Plot, Heatmap).
All processing is purely in-memory and never mutates original datasets.
"""

import json
import logging
import math
import warnings
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from backend.services.eda_engine import (
    EDAEngine,
    clean_val,
    DatasetValidationError,
)

logger = logging.getLogger("visualization_engine")

SUPPORTED_CHART_TYPES = {
    "bar",
    "line",
    "pie",
    "donut",
    "histogram",
    "scatter",
    "box",
    "heatmap",
}

# Distinct, professional color palette with primary blue accents
CHART_PALETTE = [
    "#2563eb",  # Accent Blue
    "#0ea5e9",  # Sky
    "#6366f1",  # Indigo
    "#8b5cf6",  # Purple
    "#06b6d4",  # Cyan
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#ef4444",  # Red
    "#ec4899",  # Pink
    "#64748b",  # Slate
]


class VisualizationEngine:
    """Core engine for transforming tabular datasets into visualization payloads."""

    def __init__(self, eda_engine: Optional[EDAEngine] = None) -> None:
        self.eda_engine = eda_engine or EDAEngine()

    def visualize(
        self,
        filename: str,
        content: bytes,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        aggregation: Optional[str] = None,
        title: Optional[str] = None,
        config: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Load dataset from file content and generate visualization payload."""
        df, _, _ = self.eda_engine.load_dataframe(filename, content)

        parsed_config: Dict[str, Any] = {}
        if isinstance(config, str) and config.strip():
            try:
                parsed_config = json.loads(config)
            except Exception:
                parsed_config = {}
        elif isinstance(config, dict):
            parsed_config = config

        return self.generate_chart(
            df_source=df,
            chart_type=chart_type,
            x_column=x_column,
            y_column=y_column,
            aggregation=aggregation,
            title=title,
            config=parsed_config,
        )

    def generate_chart(
        self,
        df_source: pd.DataFrame,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        aggregation: Optional[str] = None,
        title: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate inputs and generate a comprehensive chart payload."""
        if df_source.empty:
            raise DatasetValidationError("Cannot visualize an empty dataset.")

        ctype = chart_type.lower().strip()
        if ctype not in SUPPORTED_CHART_TYPES:
            raise DatasetValidationError(
                f"Unsupported chart type '{chart_type}'. Choose from: {', '.join(sorted(SUPPORTED_CHART_TYPES))}."
            )

        config = config or {}

        # Route to chart generators
        if ctype == "bar":
            return self._build_bar_chart(df_source, x_column, y_column, aggregation, title, config)
        elif ctype == "line":
            return self._build_line_chart(df_source, x_column, y_column, aggregation, title, config)
        elif ctype in ("pie", "donut"):
            return self._build_pie_chart(df_source, x_column, y_column, aggregation, title, config, is_donut=(ctype == "donut"))
        elif ctype == "histogram":
            return self._build_histogram(df_source, x_column, title, config)
        elif ctype == "scatter":
            return self._build_scatter_plot(df_source, x_column, y_column, title, config)
        elif ctype == "box":
            return self._build_box_plot(df_source, x_column, y_column, title, config)
        elif ctype == "heatmap":
            return self._build_correlation_heatmap(df_source, title, config)
        else:
            raise DatasetValidationError(f"Handler for '{ctype}' not implemented.")

    # -------------------------------------------------------------------------
    # 1. Bar Chart
    # -------------------------------------------------------------------------
    def _build_bar_chart(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        y_col: Optional[str],
        agg: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not x_col or x_col not in df.columns:
            raise DatasetValidationError("Bar chart requires a valid X-axis (category) column.")

        agg_method = (agg or "count").lower().strip()
        if y_col and y_col not in df.columns:
            raise DatasetValidationError(f"Y-axis column '{y_col}' does not exist.")

        if not y_col and agg_method in ("mean", "sum", "median"):
            raise DatasetValidationError(f"Aggregation '{agg_method}' requires a numerical Y-axis column.")

        if y_col and agg_method != "count":
            if not pd.api.types.is_numeric_dtype(df[y_col]):
                raise DatasetValidationError(
                    f"Y-axis column '{y_col}' must be numerical for aggregation '{agg_method}'. Use 'count' for categorical data."
                )

        # Sub-dataframe cleaning
        temp_df = df[[x_col] + ([y_col] if y_col else [])].copy()
        temp_df[x_col] = temp_df[x_col].fillna("(Missing)").astype(str)

        if not y_col:
            val_counts = temp_df[x_col].value_counts()
            top_cats = val_counts.head(14)
            labels = top_cats.index.tolist()
            data_values = [clean_val(v) for v in top_cats.values]

            if len(val_counts) > 14:
                other_sum = int(val_counts.iloc[14:].sum())
                labels.append(f"Other ({len(val_counts) - 14} items)")
                data_values.append(other_sum)

            y_label = "Count / Frequency"
        elif agg_method == "count":
            # Both X and Y provided with count aggregation (e.g. categorical X + categorical Y)
            temp_df = temp_df.dropna(subset=[y_col])
            grouped = temp_df.groupby(x_col)[y_col].count()
            grouped = grouped.sort_values(ascending=False)
            top_cats = grouped.head(14)
            labels = [str(x) for x in top_cats.index.tolist()]
            data_values = [clean_val(v) for v in top_cats.values]

            if len(grouped) > 14:
                other_sum = int(grouped.iloc[14:].sum())
                labels.append(f"Other ({len(grouped) - 14} items)")
                data_values.append(other_sum)

            y_label = f"Count of {y_col}"
        else:
            # Group by X and aggregate numerical Y
            temp_df = temp_df.dropna(subset=[y_col])
            if agg_method == "sum":
                grouped = temp_df.groupby(x_col)[y_col].sum()
            elif agg_method == "median":
                grouped = temp_df.groupby(x_col)[y_col].median()
            else:  # default mean
                grouped = temp_df.groupby(x_col)[y_col].mean()

            grouped = grouped.sort_values(ascending=False)
            top_cats = grouped.head(14)
            labels = top_cats.index.tolist()
            data_values = [clean_val(v) for v in top_cats.values]

            if len(grouped) > 14:
                rem = grouped.iloc[14:]
                other_val = float(rem.sum() if agg_method == "sum" else rem.mean())
                labels.append(f"Other ({len(grouped) - 14} items)")
                data_values.append(clean_val(other_val))

            y_label = f"{agg_method.title()} of {y_col}"

        chart_title = title or f"{y_label} by {x_col}"

        return {
            "chart_type": "bar",
            "title": chart_title,
            "labels": labels,
            "datasets": [
                {
                    "label": y_label,
                    "data": data_values,
                    "backgroundColor": "#2563eb",
                    "borderColor": "#1d4ed8",
                    "borderWidth": 1,
                }
            ],
            "axis_info": {
                "x_label": x_col,
                "y_label": y_label,
            },
            "statistics": {
                "category_count": len(labels),
                "total_observations": int(len(df)),
            },
            "metadata": {
                "x_column": x_col,
                "y_column": y_col,
                "aggregation": agg_method,
            },
        }

    # -------------------------------------------------------------------------
    # 2. Line Chart
    # -------------------------------------------------------------------------
    def _build_line_chart(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        y_col: Optional[str],
        agg: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not x_col or x_col not in df.columns:
            raise DatasetValidationError("Line chart requires a valid X-axis column.")
        if not y_col or y_col not in df.columns:
            raise DatasetValidationError("Line chart requires a valid Y-axis (numerical) column.")
        if not pd.api.types.is_numeric_dtype(df[y_col]):
            raise DatasetValidationError(f"Line chart Y-axis column '{y_col}' must be numerical.")

        temp_df = df[[x_col, y_col]].dropna().copy()
        if temp_df.empty:
            raise DatasetValidationError("No valid non-null records available for line chart.")

        # Try chronological sort if datetime or convert
        try:
            temp_df["_sort_key"] = pd.to_datetime(temp_df[x_col], errors="ignore")
            temp_df = temp_df.sort_values(by="_sort_key")
        except Exception:
            temp_df = temp_df.sort_values(by=x_col)

        # Aggregate duplicates along X if specified or duplicate X values exist
        agg_method = (agg or "mean").lower().strip()
        if temp_df[x_col].duplicated().any():
            if agg_method == "sum":
                grouped = temp_df.groupby(x_col, sort=False)[y_col].sum()
            elif agg_method == "median":
                grouped = temp_df.groupby(x_col, sort=False)[y_col].median()
            else:
                grouped = temp_df.groupby(x_col, sort=False)[y_col].mean()

            labels = [str(x) for x in grouped.index.tolist()]
            values = [clean_val(v) for v in grouped.values]
        else:
            labels = [str(x) for x in temp_df[x_col].tolist()]
            values = [clean_val(v) for v in temp_df[y_col].tolist()]

        # Downsample if point count > 500 for responsive rendering
        if len(labels) > 500:
            step = math.ceil(len(labels) / 500)
            labels = labels[::step]
            values = values[::step]

        chart_title = title or f"{y_col} Trend across {x_col}"
        y_label = f"{agg_method.title() if agg else ''} {y_col}".strip()

        return {
            "chart_type": "line",
            "title": chart_title,
            "labels": labels,
            "datasets": [
                {
                    "label": y_label,
                    "data": values,
                    "borderColor": "#2563eb",
                    "backgroundColor": "rgba(37, 99, 235, 0.08)",
                    "borderWidth": 2,
                    "fill": True,
                    "tension": 0.25,
                    "pointRadius": 3 if len(labels) <= 50 else 0,
                }
            ],
            "axis_info": {
                "x_label": x_col,
                "y_label": y_label,
            },
            "statistics": {
                "points_rendered": len(labels),
            },
            "metadata": {
                "x_column": x_col,
                "y_column": y_col,
                "aggregation": agg_method,
            },
        }

    # -------------------------------------------------------------------------
    # 3. Pie / Donut Chart
    # -------------------------------------------------------------------------
    def _build_pie_chart(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        y_col: Optional[str],
        agg: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
        is_donut: bool = False,
    ) -> Dict[str, Any]:
        if not x_col or x_col not in df.columns:
            raise DatasetValidationError("Pie / Donut chart requires a valid categorical column.")

        agg_method = (agg or "count").lower().strip()
        if y_col and y_col not in df.columns:
            raise DatasetValidationError(f"Y-axis column '{y_col}' does not exist.")

        if not y_col and agg_method in ("mean", "sum", "median"):
            raise DatasetValidationError(f"Aggregation '{agg_method}' requires a numerical value column.")

        if y_col and agg_method != "count":
            if not pd.api.types.is_numeric_dtype(df[y_col]):
                raise DatasetValidationError(
                    f"Y-axis column '{y_col}' must be numerical for aggregation '{agg_method}'. Use 'count' for categorical data."
                )

        temp_df = df[[x_col] + ([y_col] if y_col else [])].copy()
        temp_df[x_col] = temp_df[x_col].fillna("(Missing)").astype(str)

        if not y_col:
            val_counts = temp_df[x_col].value_counts()
            top_cats = val_counts.head(9)
            labels = top_cats.index.tolist()
            data_values = [clean_val(v) for v in top_cats.values]

            if len(val_counts) > 9:
                labels.append(f"Other ({len(val_counts) - 9} items)")
                data_values.append(int(val_counts.iloc[9:].sum()))
            slice_title = f"{'Donut' if is_donut else 'Pie'} Distribution of {x_col}"
        elif agg_method == "count":
            temp_df = temp_df.dropna(subset=[y_col])
            grouped = temp_df.groupby(x_col)[y_col].count().sort_values(ascending=False)
            top_cats = grouped.head(9)
            labels = [str(x) for x in top_cats.index.tolist()]
            data_values = [clean_val(v) for v in top_cats.values]

            if len(grouped) > 9:
                labels.append(f"Other ({len(grouped) - 9} items)")
                data_values.append(int(grouped.iloc[9:].sum()))
            slice_title = f"{'Donut' if is_donut else 'Pie'} Distribution: Count of {y_col} by {x_col}"
        else:
            temp_df = temp_df.dropna(subset=[y_col])
            grouped = temp_df.groupby(x_col)[y_col].sum() if agg_method == "sum" else temp_df.groupby(x_col)[y_col].mean()
            grouped = grouped.sort_values(ascending=False)
            top_cats = grouped.head(9)
            labels = [str(x) for x in top_cats.index.tolist()]
            data_values = [clean_val(v) for v in top_cats.values]

            if len(grouped) > 9:
                labels.append(f"Other ({len(grouped) - 9} items)")
                data_values.append(clean_val(float(grouped.iloc[9:].sum())))
            slice_title = f"{'Donut' if is_donut else 'Pie'} Distribution: {agg_method.title()} of {y_col} by {x_col}"

        # Cycle colors
        bg_colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(labels))]
        chart_title = title or slice_title

        return {
            "chart_type": "donut" if is_donut else "pie",
            "title": chart_title,
            "labels": labels,
            "datasets": [
                {
                    "data": data_values,
                    "backgroundColor": bg_colors,
                    "borderWidth": 1.5,
                    "borderColor": "#ffffff",
                }
            ],
            "metadata": {
                "is_donut": is_donut,
                "x_column": x_col,
                "y_column": y_col,
                "aggregation": agg_method,
            },
        }

    # -------------------------------------------------------------------------
    # 4. Histogram
    # -------------------------------------------------------------------------
    def _build_histogram(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not x_col or x_col not in df.columns:
            raise DatasetValidationError("Histogram requires a valid numerical column.")
        if not pd.api.types.is_numeric_dtype(df[x_col]):
            raise DatasetValidationError(f"Column '{x_col}' must be numerical to compute a histogram.")

        series = df[x_col].dropna()
        finite_series = series[np.isfinite(series)]

        if len(finite_series) == 0:
            raise DatasetValidationError(f"Column '{x_col}' has no finite numerical values.")

        num_unique = len(finite_series.unique())
        bin_count = config.get("bins") or min(15, max(3, num_unique))
        bin_count = max(2, min(50, int(bin_count))) if num_unique > 1 else 1

        counts, bin_edges = np.histogram(finite_series, bins=bin_count)
        labels = []
        for i in range(len(counts)):
            b_start = round(float(bin_edges[i]), 2)
            b_end = round(float(bin_edges[i + 1]), 2)
            labels.append(f"{b_start} - {b_end}")

        chart_title = title or f"Frequency Distribution of {x_col}"

        return {
            "chart_type": "histogram",
            "title": chart_title,
            "labels": labels,
            "datasets": [
                {
                    "label": f"Frequency ({x_col})",
                    "data": [int(c) for c in counts],
                    "backgroundColor": "rgba(37, 99, 235, 0.75)",
                    "borderColor": "#2563eb",
                    "borderWidth": 1,
                }
            ],
            "axis_info": {
                "x_label": f"{x_col} Bins",
                "y_label": "Frequency Count",
            },
            "statistics": {
                "min": clean_val(finite_series.min()),
                "max": clean_val(finite_series.max()),
                "mean": clean_val(finite_series.mean()),
                "median": clean_val(finite_series.median()),
                "std": clean_val(finite_series.std()),
                "total_finite_points": len(finite_series),
            },
            "metadata": {
                "x_column": x_col,
                "bin_count": bin_count,
            },
        }

    # -------------------------------------------------------------------------
    # 5. Scatter Plot
    # -------------------------------------------------------------------------
    def _build_scatter_plot(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        y_col: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not x_col or x_col not in df.columns:
            raise DatasetValidationError("Scatter plot requires a valid X-axis column.")
        if not y_col or y_col not in df.columns:
            raise DatasetValidationError("Scatter plot requires a valid Y-axis column.")
        if x_col == y_col:
            raise DatasetValidationError("Scatter plot requires two distinct numerical columns.")
        if not pd.api.types.is_numeric_dtype(df[x_col]) or not pd.api.types.is_numeric_dtype(df[y_col]):
            raise DatasetValidationError(f"Both '{x_col}' and '{y_col}' must be numerical for a scatter plot.")

        temp_df = df[[x_col, y_col]].dropna()
        # Filter finite values
        temp_df = temp_df[np.isfinite(temp_df[x_col]) & np.isfinite(temp_df[y_col])]

        if temp_df.empty:
            raise DatasetValidationError("No finite paired data points available for scatter plot.")

        # Limit to 1000 points for smooth canvas rendering
        sample_ratio = 1.0
        if len(temp_df) > 1000:
            sample_ratio = round(1000 / len(temp_df), 3)
            temp_df = temp_df.sample(n=1000, random_state=42)

        scatter_points = [
            {"x": clean_val(r[x_col]), "y": clean_val(r[y_col])}
            for _, r in temp_df.iterrows()
        ]

        # Calculate Pearson correlation
        corr_val = None
        if len(temp_df) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                corr_matrix = temp_df.corr(method="pearson")
                if x_col in corr_matrix.columns and y_col in corr_matrix.index:
                    corr_val = clean_val(corr_matrix.loc[y_col, x_col])

        chart_title = title or f"{x_col} vs {y_col} Relationship"

        return {
            "chart_type": "scatter",
            "title": chart_title,
            "datasets": [
                {
                    "label": f"{x_col} vs {y_col}",
                    "data": scatter_points,
                    "backgroundColor": "rgba(37, 99, 235, 0.65)",
                    "borderColor": "#1d4ed8",
                    "borderWidth": 1,
                    "pointRadius": 4,
                }
            ],
            "axis_info": {
                "x_label": x_col,
                "y_label": y_col,
            },
            "statistics": {
                "points_rendered": len(scatter_points),
                "pearson_correlation": corr_val,
                "sample_ratio": sample_ratio,
            },
            "metadata": {
                "x_column": x_col,
                "y_column": y_col,
            },
        }

    # -------------------------------------------------------------------------
    # 6. Box Plot
    # -------------------------------------------------------------------------
    def _build_box_plot(
        self,
        df: pd.DataFrame,
        x_col: Optional[str],
        y_col: Optional[str],
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If only one column given, it's the target numeric
        target_num_col = y_col or x_col
        group_col = x_col if (x_col and y_col and x_col != y_col) else None

        if not target_num_col or target_num_col not in df.columns:
            raise DatasetValidationError("Box plot requires a valid numerical feature.")
        if not pd.api.types.is_numeric_dtype(df[target_num_col]):
            raise DatasetValidationError(f"Target column '{target_num_col}' must be numerical for a box plot.")

        def compute_group_box(s: pd.Series, group_name: str) -> Dict[str, Any]:
            finite_s = s.dropna()
            finite_s = finite_s[np.isfinite(finite_s)]
            if len(finite_s) < 4:
                return {
                    "group": group_name,
                    "min": clean_val(finite_s.min()) if len(finite_s) > 0 else None,
                    "q1": None,
                    "median": clean_val(finite_s.median()) if len(finite_s) > 0 else None,
                    "q3": None,
                    "max": clean_val(finite_s.max()) if len(finite_s) > 0 else None,
                    "lower_whisker": clean_val(finite_s.min()) if len(finite_s) > 0 else None,
                    "upper_whisker": clean_val(finite_s.max()) if len(finite_s) > 0 else None,
                    "mean": clean_val(finite_s.mean()) if len(finite_s) > 0 else None,
                    "outliers": [],
                    "count": len(finite_s),
                }

            q1 = float(finite_s.quantile(0.25))
            q3 = float(finite_s.quantile(0.75))
            iqr = q3 - q1
            median = float(finite_s.median())
            mean = float(finite_s.mean())
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            in_whiskers = finite_s[(finite_s >= lower_bound) & (finite_s <= upper_bound)]
            lower_whisker = float(in_whiskers.min()) if len(in_whiskers) > 0 else q1
            upper_whisker = float(in_whiskers.max()) if len(in_whiskers) > 0 else q3
            outlier_series = finite_s[(finite_s < lower_bound) | (finite_s > upper_bound)]

            return {
                "group": group_name,
                "min": clean_val(finite_s.min()),
                "q1": clean_val(q1),
                "median": clean_val(median),
                "q3": clean_val(q3),
                "max": clean_val(finite_s.max()),
                "lower_whisker": clean_val(lower_whisker),
                "upper_whisker": clean_val(upper_whisker),
                "mean": clean_val(mean),
                "outliers": [clean_val(v) for v in outlier_series.head(15).tolist()],
                "count": len(finite_s),
            }

        box_groups: List[Dict[str, Any]] = []

        if group_col and group_col in df.columns:
            # Group by category, limit to top 8 groups
            top_groups = df[group_col].value_counts().head(8).index.tolist()
            for grp in top_groups:
                subset = df[df[group_col] == grp][target_num_col]
                box_groups.append(compute_group_box(subset, str(grp)))
            chart_title = title or f"Box Plot of {target_num_col} by {group_col}"
        else:
            box_groups.append(compute_group_box(df[target_num_col], target_num_col))
            chart_title = title or f"Box Plot Quartile Distribution of {target_num_col}"

        labels = [bg["group"] for bg in box_groups]

        return {
            "chart_type": "box",
            "title": chart_title,
            "labels": labels,
            "box_data": box_groups,
            "axis_info": {
                "x_label": group_col or "Feature",
                "y_label": target_num_col,
            },
            "statistics": {
                "groups_evaluated": len(box_groups),
            },
            "metadata": {
                "target_column": target_num_col,
                "group_column": group_col,
            },
        }

    # -------------------------------------------------------------------------
    # 7. Correlation Heatmap
    # -------------------------------------------------------------------------
    def _build_correlation_heatmap(
        self,
        df: pd.DataFrame,
        title: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(num_cols) < 2:
            raise DatasetValidationError("Correlation heatmap requires at least 2 numerical features.")

        # Limit to top 10 numerical features if too many to keep visual legible
        if len(num_cols) > 10:
            num_cols = num_cols[:10]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            corr_df = df[num_cols].corr(method="pearson")

        matrix_rows: List[List[Optional[float]]] = []
        top_pairs: List[Dict[str, Any]] = []

        for i, c1 in enumerate(num_cols):
            row_vals: List[Optional[float]] = []
            for j, c2 in enumerate(num_cols):
                r = clean_val(corr_df.loc[c1, c2])
                row_vals.append(r)
                if i < j and r is not None:
                    top_pairs.append({
                        "col1": str(c1),
                        "col2": str(c2),
                        "correlation": r,
                        "abs_correlation": round(abs(r), 4),
                    })
            matrix_rows.append(row_vals)

        top_pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
        chart_title = title or "Pairwise Correlation Heatmap Matrix"

        return {
            "chart_type": "heatmap",
            "title": chart_title,
            "columns": [str(c) for c in num_cols],
            "matrix": matrix_rows,
            "top_correlations": top_pairs[:6],
            "statistics": {
                "numerical_features_count": len(num_cols),
            },
            "metadata": {
                "columns": [str(c) for c in num_cols],
            },
        }
