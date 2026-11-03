"""Automated EDA Report Generation Engine.

Phase 6: Professional, publication-ready PDF report generation using ReportLab and Matplotlib.
Integrates Exploratory Data Analysis (EDA), cleaning history, outlier audits,
cross-feature correlation matrices, embedded visualizations, and automated data-driven insights.
All PDF generation is performed purely in-memory with zero permanent disk storage.
"""

import html
import io
import math
import os
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.services.eda_engine import (
    EDAEngine,
    DatasetValidationError,
    clean_val,
    format_memory_size,
    MAX_FILE_SIZE,
)
from backend.services.cleaning_engine import CleaningEngine


class NumberedCanvas(canvas.Canvas):
    """Two-pass ReportLab Canvas that dynamically computes running page count

    and renders standard headers and footers with 'Page X of Y' on all running pages.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        page_w, page_h = letter

        # Suppress running header and footer on the Cover Page (Page 1)
        if self._pageNumber > 1:
            # Running Header
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#0284c7"))
            self.drawString(36, page_h - 26, "DATA DETECTIVE")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawRightString(page_w - 36, page_h - 26, "AUTOMATED EXPLORATORY DATA ANALYSIS REPORT")

            # Header rule
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.75)
            self.line(36, page_h - 30, page_w - 36, page_h - 30)

            # Footer rule
            self.line(36, 32, page_w - 36, 32)

            # Running Footer
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(36, 20, "Confidential • In-Memory Analysis • Data Detective Engine v0.6.0")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(page_w - 36, 20, page_text)

        self.restoreState()


class ReportEngine:
    """Core engine for automated PDF report generation."""

    def __init__(
        self,
        eda_engine: Optional[EDAEngine] = None,
        cleaning_engine: Optional[CleaningEngine] = None,
    ) -> None:
        self.eda_engine = eda_engine or EDAEngine()
        self.cleaning_engine = cleaning_engine or CleaningEngine(eda_engine=self.eda_engine)
        self._setup_styles()

    def _setup_styles(self) -> None:
        """Initialize custom ReportLab typography styles."""
        self.styles = getSampleStyleSheet()

        # Cover Page styles
        self.styles.add(ParagraphStyle(
            "CoverBadge",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0284c7"),
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            "CoverTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            "CoverSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#475569"),
            spaceAfter=20,
        ))

        # Section Heading styles
        self.styles.add(ParagraphStyle(
            "SectionHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        ))
        self.styles.add(ParagraphStyle(
            "SubSectionHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0284c7"),
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        ))
        self.styles.add(ParagraphStyle(
            "BodyDesc",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12.5,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            "KeyFindingBullet",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#0f172a"),
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=5,
        ))

        # Table cell styles
        self.styles.add(ParagraphStyle(
            "TH",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=0,
        ))
        self.styles.add(ParagraphStyle(
            "TH_Right",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=2,
        ))
        self.styles.add(ParagraphStyle(
            "TD",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0f172a"),
            alignment=0,
        ))
        self.styles.add(ParagraphStyle(
            "TD_Bold",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0f172a"),
            alignment=0,
        ))
        self.styles.add(ParagraphStyle(
            "TD_Right",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0f172a"),
            alignment=2,
        ))
        self.styles.add(ParagraphStyle(
            "TD_Accent",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0284c7"),
            alignment=0,
        ))
        self.styles.add(ParagraphStyle(
            "ChartCaption",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            alignment=1,
            spaceBefore=3,
            spaceAfter=8,
        ))

    # =========================================================================
    # Matplotlib In-Memory Chart Generators
    # =========================================================================
    def _plot_correlation_heatmap(self, df: pd.DataFrame, num_cols: List[str]) -> Optional[io.BytesIO]:
        """Generate high-resolution correlation heatmap matrix as PNG bytes."""
        if len(num_cols) < 2:
            return None

        cols = num_cols[:9]  # Limit to 9 for legible layout
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            corr = df[cols].corr(method="pearson").fillna(0)

        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=180)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        cax = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        cbar = fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=7.5)

        short_labels = [c if len(c) <= 12 else c[:10] + ".." for c in cols]
        ax.set_xticks(range(len(cols)))
        ax.set_yticks(range(len(cols)))
        ax.set_xticklabels(short_labels, rotation=35, ha="right", fontsize=7.5)
        ax.set_yticklabels(short_labels, fontsize=7.5)

        for i in range(len(cols)):
            for j in range(len(cols)):
                val = corr.iloc[i, j]
                text_col = "#ffffff" if abs(val) > 0.55 else "#0f172a"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=text_col, fontsize=7, weight="bold")

        ax.set_title("Pearson Pairwise Feature Correlation Heatmap", fontsize=9.5, weight="bold", color="#0f172a", pad=8)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=180)
        plt.close(fig)
        buf.seek(0)
        return buf

    def _plot_histogram(self, df: pd.DataFrame, col: str) -> Optional[io.BytesIO]:
        """Generate numerical feature distribution histogram as PNG bytes."""
        s = df[col].dropna()
        s = s[np.isfinite(s)]
        if len(s) == 0:
            return None

        fig, ax = plt.subplots(figsize=(5.8, 2.5), dpi=180)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        n_bins = min(14, max(4, len(s.unique()))) if len(s.unique()) > 1 else 1
        ax.hist(s, bins=n_bins, color="#0284c7", edgecolor="#0369a1", alpha=0.88, rwidth=0.92)

        mean_val = float(s.mean())
        median_val = float(s.median())
        ax.axvline(mean_val, color="#dc2626", linestyle="--", linewidth=1.2, label=f"Mean: {mean_val:.2f}")
        ax.axvline(median_val, color="#16a34a", linestyle=":", linewidth=1.5, label=f"Median: {median_val:.2f}")

        ax.set_title(f"Numerical Distribution: {col}", fontsize=9, weight="bold", color="#0f172a")
        ax.set_xlabel(col, fontsize=7.5, color="#334155")
        ax.set_ylabel("Frequency Count", fontsize=7.5, color="#334155")
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.5, color="#cbd5e1")
        ax.legend(fontsize=7, loc="upper right", framealpha=0.9)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=180)
        plt.close(fig)
        buf.seek(0)
        return buf

    def _plot_categorical_bar(self, df: pd.DataFrame, col: str) -> Optional[io.BytesIO]:
        """Generate categorical feature frequency bar chart as PNG bytes."""
        vc = df[col].fillna("(Missing)").value_counts()
        if len(vc) == 0:
            return None

        top_cats = vc.head(7)
        if len(vc) > 7:
            other_sum = int(vc.iloc[7:].sum())
            top_cats = pd.concat([top_cats, pd.Series({"Other": other_sum})])

        fig, ax = plt.subplots(figsize=(5.8, 2.5), dpi=180)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        labels = [str(x) if len(str(x)) <= 13 else str(x)[:11] + ".." for x in top_cats.index]
        colors_list = ["#0284c7" if l != "Other" else "#94a3b8" for l in labels]

        bars = ax.bar(labels, top_cats.values, color=colors_list, edgecolor="#0369a1", alpha=0.9, width=0.62)
        for bar in bars:
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                yval + max(0.5, yval * 0.02),
                f"{int(yval)}",
                ha="center",
                va="bottom",
                fontsize=6.5,
                color="#334155",
            )

        ax.set_title(f"Categorical Frequency: {col}", fontsize=9, weight="bold", color="#0f172a")
        ax.set_ylabel("Observation Count", fontsize=7.5, color="#334155")
        ax.tick_params(labelsize=7)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.5, color="#cbd5e1")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=180)
        plt.close(fig)
        buf.seek(0)
        return buf

    def _plot_box_plots(self, df: pd.DataFrame, num_cols: List[str]) -> Optional[io.BytesIO]:
        """Generate box-and-whisker plot for numerical features as PNG bytes."""
        valid_cols = [c for c in num_cols if len(df[c].dropna()) > 0][:5]
        if not valid_cols:
            return None

        fig, ax = plt.subplots(figsize=(5.8, 2.5), dpi=180)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        data = [df[c].dropna().values for c in valid_cols]
        short_labels = [c if len(c) <= 12 else c[:10] + ".." for c in valid_cols]
        bp = ax.boxplot(data, patch_artist=True, tick_labels=short_labels)

        for box in bp["boxes"]:
            box.set(facecolor="#e0f2fe", edgecolor="#0284c7", linewidth=1.2)
        for whisker in bp["whiskers"]:
            whisker.set(color="#0284c7", linewidth=1)
        for cap in bp["caps"]:
            cap.set(color="#0284c7", linewidth=1)
        for median in bp["medians"]:
            median.set(color="#dc2626", linewidth=1.5)
        for flier in bp["fliers"]:
            flier.set(marker="o", color="#ea580c", alpha=0.55, markersize=3.5)

        ax.set_title("Quartile & Outlier Distribution (Box Plots)", fontsize=9, weight="bold", color="#0f172a")
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.5, color="#cbd5e1")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=180)
        plt.close(fig)
        buf.seek(0)
        return buf

    # =========================================================================
    # Automated Factual Key Findings
    # =========================================================================
    def _generate_key_findings(
        self,
        eda_res: Dict[str, Any],
        is_cleaned: bool,
        operations: List[Dict[str, Any]],
        orig_eda: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Compute factual, data-driven observations strictly derived from dataset statistics."""
        findings: List[str] = []
        ov = eda_res.get("overview", {})
        total_rows = ov.get("total_rows", 0)
        total_cols = ov.get("total_columns", 0)
        num_cols = ov.get("numerical_columns", [])
        cat_cols = ov.get("categorical_columns", [])

        # 1. Scale & Dimensions
        mem_str = ov.get("memory_usage_formatted") or ov.get("memory_usage", "N/A")
        findings.append(
            f"<b>Dataset Composition:</b> Analyzed <b>{total_rows:,}</b> rows across <b>{total_cols}</b> features "
            f"({len(num_cols)} numerical, {len(cat_cols)} categorical), occupying {mem_str} in-memory."
        )

        # 2. Completeness & Missing Values
        mv = eda_res.get("missing_values", {})
        overall_mv = mv.get("overall", {})
        tot_missing = overall_mv.get("total_missing_cells", 0)
        pct_missing = overall_mv.get("overall_missing_percentage", 0.0)
        cols_missing = [c for c in mv.get("columns", []) if c.get("missing_count", 0) > 0]

        if tot_missing == 0:
            findings.append("<b>Data Completeness:</b> <b>100.0% Complete</b>. Zero missing values were identified across all features.")
        else:
            highest_col = cols_missing[0] if cols_missing else {}
            findings.append(
                f"<b>Missingness Audit:</b> Identified <b>{tot_missing:,}</b> missing cells ({pct_missing:.2f}% overall missingness) "
                f"across {len(cols_missing)} feature(s). Column <i>'{highest_col.get('column')}'</i> had the highest missing rate "
                f"at {highest_col.get('missing_percentage', 0.0):.2f}% ({highest_col.get('missing_count', 0):,} records)."
            )

        # 3. Duplicate Records
        dups = eda_res.get("duplicates", {})
        dup_count = dups.get("duplicate_count", 0)
        dup_pct = dups.get("duplicate_percentage", 0.0)
        if dup_count == 0:
            findings.append("<b>Record Uniqueness:</b> <b>100.0% Unique</b>. No duplicate rows were detected in the dataset.")
        else:
            findings.append(
                f"<b>Duplicate Detection:</b> Identified <b>{dup_count:,}</b> duplicate records ({dup_pct:.2f}% of dataset). "
                f"A deduplication pass may be beneficial for data integrity."
            )

        # 4. Outliers
        outliers = eda_res.get("outliers", {})
        tot_outliers = outliers.get("total_outliers_detected", 0)
        outlier_cols = [c for c in outliers.get("columns", []) if c.get("outlier_count", 0) > 0]
        if tot_outliers == 0:
            findings.append("<b>Outlier Analysis:</b> No statistical outliers were detected under the 1.5×IQR boundary rule across numerical features.")
        else:
            top_outlier = outlier_cols[0] if outlier_cols else {}
            findings.append(
                f"<b>Outlier Prevalence:</b> Identified <b>{tot_outliers:,}</b> statistical outlier observations using the IQR method. "
                f"Feature <i>'{top_outlier.get('column')}'</i> exhibited the highest concentration with {top_outlier.get('outlier_count', 0):,} outliers "
                f"({top_outlier.get('outlier_percentage', 0.0):.2f}%)."
            )

        # 5. Correlations
        corr_data = eda_res.get("correlation", {})
        top_pairs = corr_data.get("top_correlations", [])
        if top_pairs:
            best_pair = top_pairs[0]
            findings.append(
                f"<b>Linear Feature Dependency:</b> Strongest pairwise correlation exists between <b>'{best_pair.get('col1')}'</b> "
                f"and <b>'{best_pair.get('col2')}'</b> (Pearson <i>r</i> = <b>{best_pair.get('correlation', 0.0):+.3f}</b>)."
            )
        elif len(num_cols) < 2:
            findings.append("<b>Correlation Analysis:</b> Dataset contains fewer than two numerical features; pairwise correlation matrix is not applicable.")

        # 6. Cleaning Impact
        if is_cleaned:
            ops_count = len(operations)
            if orig_eda:
                orig_rows = orig_eda.get("overview", {}).get("total_rows", total_rows)
                orig_mv = orig_eda.get("missing_values", {}).get("overall", {}).get("total_missing_cells", 0)
                findings.append(
                    f"<b>Cleaning Studio Pipeline Impact:</b> Executed <b>{ops_count}</b> preprocessing operation(s). "
                    f"Row count moved from {orig_rows:,} to {total_rows:,} (Δ = {total_rows - orig_rows:+d}), "
                    f"and missing cells changed from {orig_mv:,} to {tot_missing:,}."
                )
            else:
                findings.append(
                    f"<b>Cleaned Dataset Status:</b> Generated from a preprocessed pipeline of <b>{ops_count}</b> operation(s). "
                    f"All metrics reflect the verified cleaned working state."
                )

        return findings

    # =========================================================================
    # Main Report Generator
    # =========================================================================
    def generate_report_pdf(
        self,
        filename: str,
        content: bytes,
        dataset_type: str = "original",
        operations_input: Optional[Any] = None,
        original_content: Optional[bytes] = None,
        original_filename: Optional[str] = None,
    ) -> io.BytesIO:
        """Generate a complete publication-quality PDF report in-memory.

        Returns an in-memory io.BytesIO buffer containing the PDF bytes.
        """
        # 1. Load active dataset
        df, file_size, clean_filename = self.eda_engine.load_dataframe(filename, content)
        is_cleaned = dataset_type.lower().strip() == "cleaned"

        # 2. Execute full automated EDA analysis
        eda_res = self.eda_engine.analyze_dataset(clean_filename, content)

        # 3. If cleaned and original file provided, run EDA on original dataset for before/after comparison
        orig_eda: Optional[Dict[str, Any]] = None
        if is_cleaned and original_content and len(original_content) > 0:
            try:
                _, orig_ext = os.path.splitext(filename)
                fallback_orig_name = f"original{orig_ext if orig_ext else '.csv'}"
                orig_eda = self.eda_engine.analyze_dataset(original_filename or fallback_orig_name, original_content)
            except Exception:
                orig_eda = None

        # 4. Normalize operations log
        operations: List[Dict[str, Any]] = []
        if operations_input:
            try:
                operations = self.cleaning_engine.normalize_operations(operations_input)
            except Exception:
                operations = []

        # 5. Build Document Story
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        story: List[Any] = []
        printable_w = doc.width  # 540 pt on standard Letter with 36 pt margins

        # -------------------------------------------------------------
        # SECTION 1: Cover Page
        # -------------------------------------------------------------
        story.append(Spacer(1, 40))
        story.append(Paragraph("DATA DETECTIVE • AUTOMATED AUDIT PLATFORM", self.styles["CoverBadge"]))
        story.append(Paragraph("Exploratory Data Analysis &amp; Quality Audit Report", self.styles["CoverTitle"]))
        story.append(HRFlowable(width="100%", thickness=3.5, color=colors.HexColor("#0284c7"), spaceAfter=18))

        scope_label = "Cleaned Dataset (Post-Preprocessing)" if is_cleaned else "Original Dataset (Raw Baseline)"
        scope_color = "#16a34a" if is_cleaned else "#0284c7"
        report_timestamp = datetime.now(timezone.utc).strftime("%B %d, %Y • %H:%M:%S UTC")

        story.append(Paragraph(
            "An automated end-to-end audit analyzing statistical distributions, schema definitions, "
            "missing values, record uniqueness, IQR outlier thresholds, and cross-feature linear correlations. "
            "All metrics are generated purely in-memory with zero permanent disk persistence.",
            self.styles["CoverSubtitle"],
        ))

        story.append(Spacer(1, 15))

        # Metadata Summary Card Table
        meta_table_data = [
            [
                Paragraph("<b>Dataset Filename:</b>", self.styles["TD_Bold"]),
                Paragraph(f"<code>{clean_filename}</code>", self.styles["TD_Accent"]),
                Paragraph("<b>Audit Scope:</b>", self.styles["TD_Bold"]),
                Paragraph(f"<font color='{scope_color}'><b>{scope_label}</b></font>", self.styles["TD_Bold"]),
            ],
            [
                Paragraph("<b>Total Rows:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{eda_res['overview']['total_rows']:,}", self.styles["TD"]),
                Paragraph("<b>Total Features:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{eda_res['overview']['total_columns']:,}", self.styles["TD"]),
            ],
            [
                Paragraph("<b>Numerical Features:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{len(eda_res['overview']['numerical_columns'])}", self.styles["TD"]),
                Paragraph("<b>Categorical Features:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{len(eda_res['overview']['categorical_columns'])}", self.styles["TD"]),
            ],
            [
                Paragraph("<b>Memory Footprint:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{eda_res['overview'].get('memory_usage_formatted', eda_res['overview'].get('memory_usage', 'N/A'))}", self.styles["TD"]),
                Paragraph("<b>Generated Timestamp:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{report_timestamp}", self.styles["TD"]),
            ],
            [
                Paragraph("<b>Platform Engine:</b>", self.styles["TD_Bold"]),
                Paragraph("Data Detective Engine v0.6.0", self.styles["TD"]),
                Paragraph("<b>Storage Policy:</b>", self.styles["TD_Bold"]),
                Paragraph("Ephemeral Memory Only", self.styles["TD"]),
            ],
        ]

        col_w = printable_w / 4
        t_meta = Table(meta_table_data, colWidths=[col_w * 0.9, col_w * 1.1, col_w * 0.9, col_w * 1.1])
        t_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t_meta)

        story.append(Spacer(1, 40))

        # Executive Notice Box
        notice_data = [[
            Paragraph(
                "<b>Notice of Automated Generation:</b> This technical document was produced automatically by the Data Detective "
                "Automated EDA Engine. Statistical profiling, outlier identification, and correlation coefficients reflect the mathematically "
                "computed properties of the analyzed dataset without manual bias or synthetic data fabrication.",
                self.styles["BodyDesc"],
            )
        ]]
        t_notice = Table(notice_data, colWidths=[printable_w])
        t_notice.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t_notice)

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 2: Executive Summary & Key Findings
        # -------------------------------------------------------------
        story.append(Paragraph("1. Executive Summary &amp; Key Findings", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))
        story.append(Paragraph(
            "Key factual findings derived strictly from programmatic analysis of the uploaded dataset. "
            "All findings are empirically grounded in the underlying distributions and quality checks.",
            self.styles["BodyDesc"],
        ))

        findings = self._generate_key_findings(eda_res, is_cleaned, operations, orig_eda)
        for f in findings:
            story.append(Paragraph(f"• {f}", self.styles["KeyFindingBullet"]))

        story.append(Spacer(1, 14))

        # -------------------------------------------------------------
        # SECTION 3: Dataset Overview & Schema Profiling
        # -------------------------------------------------------------
        story.append(Paragraph("2. Dataset Overview &amp; Column Classification", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        col_analysis = eda_res.get("column_analysis", [])
        total_rows = eda_res["overview"]["total_rows"]

        schema_headers = [
            Paragraph("Column Name", self.styles["TH"]),
            Paragraph("Data Type", self.styles["TH"]),
            Paragraph("Classification", self.styles["TH"]),
            Paragraph("Unique Count", self.styles["TH_Right"]),
            Paragraph("Unique %", self.styles["TH_Right"]),
        ]
        schema_rows = [schema_headers]

        for ca in col_analysis:
            c_type = "Numerical" if ca.get("is_numerical") else "Categorical"
            type_color = "#0284c7" if ca.get("is_numerical") else "#16a34a"
            schema_rows.append([
                Paragraph(f"<b>{ca.get('column')}</b>", self.styles["TD_Bold"]),
                Paragraph(f"<code>{ca.get('data_type')}</code>", self.styles["TD"]),
                Paragraph(f"<font color='{type_color}'>{c_type}</font>", self.styles["TD"]),
                Paragraph(f"{ca.get('unique_count'):,}", self.styles["TD_Right"]),
                Paragraph(f"{ca.get('unique_percentage', 0.0):.1f}%", self.styles["TD_Right"]),
            ])

        t_schema = Table(
            schema_rows,
            colWidths=[printable_w * 0.32, printable_w * 0.20, printable_w * 0.20, printable_w * 0.14, printable_w * 0.14],
        )
        t_schema.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_schema)

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 4: Statistical Profiling
        # -------------------------------------------------------------
        story.append(Paragraph("3. Statistical Profiling &amp; Distribution Summaries", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        num_stats = eda_res.get("statistical_summary", {}).get("numerical", {})
        if num_stats:
            story.append(Paragraph("Numerical Features Summary (Descriptive Statistics)", self.styles["SubSectionHeader"]))
            num_stat_headers = [
                Paragraph("Feature", self.styles["TH"]),
                Paragraph("Count", self.styles["TH_Right"]),
                Paragraph("Mean", self.styles["TH_Right"]),
                Paragraph("Std Dev", self.styles["TH_Right"]),
                Paragraph("Min", self.styles["TH_Right"]),
                Paragraph("Q1 (25%)", self.styles["TH_Right"]),
                Paragraph("Median", self.styles["TH_Right"]),
                Paragraph("Q3 (75%)", self.styles["TH_Right"]),
                Paragraph("Max", self.styles["TH_Right"]),
            ]
            num_stat_rows = [num_stat_headers]

            w_feature = printable_w * 0.20
            w_stat = (printable_w - w_feature) / 8

            for col_name, st in num_stats.items():
                def f_val(val: Any) -> str:
                    if val is None or math.isnan(val) if isinstance(val, float) else False:
                        return "—"
                    return f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)

                num_stat_rows.append([
                    Paragraph(f"<b>{col_name}</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{int(st.get('count', 0)):,}", self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("mean")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("std")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("min")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("25%")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("50%")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("75%")), self.styles["TD_Right"]),
                    Paragraph(f_val(st.get("max")), self.styles["TD_Right"]),
                ])

            t_num = Table(num_stat_rows, colWidths=[w_feature] + [w_stat] * 8)
            t_num.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_num)
            story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("<i>No numerical columns identified for descriptive statistics.</i>", self.styles["BodyDesc"]))

        cat_stats = eda_res.get("statistical_summary", {}).get("categorical", {})
        if cat_stats:
            story.append(Paragraph("Categorical Features Summary (Frequencies &amp; Modes)", self.styles["SubSectionHeader"]))
            cat_stat_headers = [
                Paragraph("Feature", self.styles["TH"]),
                Paragraph("Count", self.styles["TH_Right"]),
                Paragraph("Unique", self.styles["TH_Right"]),
                Paragraph("Top Category (Mode)", self.styles["TH"]),
                Paragraph("Top Frequency", self.styles["TH_Right"]),
                Paragraph("Dominance %", self.styles["TH_Right"]),
            ]
            cat_stat_rows = [cat_stat_headers]

            for col_name, st in cat_stats.items():
                c_cnt = int(st.get("count", 0))
                c_top_freq = int(st.get("freq", 0))
                c_pct = (c_top_freq / c_cnt * 100) if c_cnt > 0 else 0.0
                cat_stat_rows.append([
                    Paragraph(f"<b>{col_name}</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{c_cnt:,}", self.styles["TD_Right"]),
                    Paragraph(f"{int(st.get('unique', 0)):,}", self.styles["TD_Right"]),
                    Paragraph(str(st.get("top", "—")), self.styles["TD"]),
                    Paragraph(f"{c_top_freq:,}", self.styles["TD_Right"]),
                    Paragraph(f"{c_pct:.1f}%", self.styles["TD_Right"]),
                ])

            w_cat_f = printable_w * 0.25
            w_cat_other = (printable_w - w_cat_f) / 5
            t_cat = Table(cat_stat_rows, colWidths=[w_cat_f, w_cat_other, w_cat_other, w_cat_other * 1.5, w_cat_other * 0.8, w_cat_other * 0.7])
            t_cat.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_cat)

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 5: Data Quality Analysis (Missing & Duplicates)
        # -------------------------------------------------------------
        story.append(Paragraph("4. Data Quality &amp; Cleanliness Audit", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        story.append(Paragraph("Missing Values Breakdown by Column", self.styles["SubSectionHeader"]))
        mv_cols = eda_res.get("missing_values", {}).get("columns", [])

        mv_headers = [
            Paragraph("Column Name", self.styles["TH"]),
            Paragraph("Data Type", self.styles["TH"]),
            Paragraph("Missing Count", self.styles["TH_Right"]),
            Paragraph("Missing %", self.styles["TH_Right"]),
            Paragraph("Completeness Status", self.styles["TH"]),
        ]
        mv_rows = [mv_headers]

        for m in mv_cols:
            m_cnt = m.get("missing_count", 0)
            m_pct = m.get("missing_percentage", 0.0)
            if m_cnt == 0:
                status_text = "<font color='#16a34a'><b>100% Complete</b></font>"
            elif m_pct < 10.0:
                status_text = f"<font color='#0284c7'>Low Missing ({m_pct:.1f}%)</font>"
            elif m_pct < 30.0:
                status_text = f"<font color='#ea580c'>Moderate Missing ({m_pct:.1f}%)</font>"
            else:
                status_text = f"<font color='#dc2626'><b>High Missing ({m_pct:.1f}%)</b></font>"

            mv_rows.append([
                Paragraph(f"<b>{m.get('column')}</b>", self.styles["TD_Bold"]),
                Paragraph(f"<code>{m.get('data_type')}</code>", self.styles["TD"]),
                Paragraph(f"{m_cnt:,}", self.styles["TD_Right"]),
                Paragraph(f"{m_pct:.2f}%", self.styles["TD_Right"]),
                Paragraph(status_text, self.styles["TD"]),
            ])

        t_mv = Table(
            mv_rows,
            colWidths=[printable_w * 0.32, printable_w * 0.20, printable_w * 0.16, printable_w * 0.14, printable_w * 0.18],
        )
        t_mv.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_mv)

        story.append(Spacer(1, 12))

        # Duplicate Rows Block
        story.append(Paragraph("Duplicate Rows Assessment", self.styles["SubSectionHeader"]))
        dups = eda_res.get("duplicates", {})
        dup_data = [
            [
                Paragraph("<b>Duplicate Rows:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{dups.get('duplicate_count', 0):,} rows", self.styles["TD"]),
                Paragraph("<b>Duplicate Percentage:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{dups.get('duplicate_percentage', 0.0):.2f}%", self.styles["TD"]),
            ],
            [
                Paragraph("<b>Unique Rows:</b>", self.styles["TD_Bold"]),
                Paragraph(f"{dups.get('unique_rows_count', total_rows):,} rows", self.styles["TD"]),
                Paragraph("<b>Uniqueness Health:</b>", self.styles["TD_Bold"]),
                Paragraph(
                    "<font color='#16a34a'><b>Optimal (Zero Duplicates)</b></font>"
                    if dups.get("duplicate_count", 0) == 0
                    else "<font color='#ea580c'>Duplicates Detected</font>",
                    self.styles["TD"],
                ),
            ],
        ]
        t_dup = Table(dup_data, colWidths=[printable_w * 0.25, printable_w * 0.25, printable_w * 0.25, printable_w * 0.25])
        t_dup.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t_dup)

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 6: Outlier Analysis (IQR Method)
        # -------------------------------------------------------------
        story.append(Paragraph("5. Outlier Detection &amp; Analysis (IQR Method)", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        story.append(Paragraph(
            "Outliers are evaluated using the standard Tukey Interquartile Range (IQR) rule: "
            "<b>IQR = Third Quartile (75%) − First Quartile (25%)</b>. "
            "Observations falling below <b>Q1 − 1.5×IQR</b> or above <b>Q3 + 1.5×IQR</b> are flagged as potential anomalies.",
            self.styles["BodyDesc"],
        ))

        outliers_cols = eda_res.get("outliers", {}).get("columns", [])
        if outliers_cols:
            outlier_headers = [
                Paragraph("Feature", self.styles["TH"]),
                Paragraph("First Q (25%)", self.styles["TH_Right"]),
                Paragraph("Third Q (75%)", self.styles["TH_Right"]),
                Paragraph("IQR", self.styles["TH_Right"]),
                Paragraph("Lower Bound", self.styles["TH_Right"]),
                Paragraph("Upper Bound", self.styles["TH_Right"]),
                Paragraph("Outliers", self.styles["TH_Right"]),
                Paragraph("Outlier %", self.styles["TH_Right"]),
            ]
            outlier_rows = [outlier_headers]

            w_out_col = printable_w * 0.22
            w_out_stat = (printable_w - w_out_col) / 7

            for o in outliers_cols:
                def f_num(val: Any) -> str:
                    if val is None:
                        return "—"
                    return f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)

                o_cnt = o.get("outlier_count", 0)
                o_pct = o.get("outlier_percentage", 0.0)
                outlier_rows.append([
                    Paragraph(f"<b>{o.get('column')}</b>", self.styles["TD_Bold"]),
                    Paragraph(f_num(o.get("q1")), self.styles["TD_Right"]),
                    Paragraph(f_num(o.get("q3")), self.styles["TD_Right"]),
                    Paragraph(f_num(o.get("iqr")), self.styles["TD_Right"]),
                    Paragraph(f_num(o.get("lower_bound")), self.styles["TD_Right"]),
                    Paragraph(f_num(o.get("upper_bound")), self.styles["TD_Right"]),
                    Paragraph(
                        f"<font color='{'#dc2626' if o_cnt > 0 else '#16a34a'}'><b>{o_cnt:,}</b></font>",
                        self.styles["TD_Right"],
                    ),
                    Paragraph(f"{o_pct:.1f}%", self.styles["TD_Right"]),
                ])

            t_outliers = Table(outlier_rows, colWidths=[w_out_col] + [w_out_stat] * 7)
            t_outliers.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_outliers)
        else:
            story.append(Paragraph("<i>No numerical columns available for IQR outlier detection.</i>", self.styles["BodyDesc"]))

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 7: Correlation Analysis & Heatmap
        # -------------------------------------------------------------
        story.append(Paragraph("6. Correlation Analysis &amp; Feature Heatmap", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        num_cols = eda_res.get("overview", {}).get("numerical_columns", [])
        if len(num_cols) >= 2:
            story.append(Paragraph(
                "Pearson product-moment correlation coefficients measuring linear dependencies between numerical features. "
                "Values range from -1.0 (perfect inverse relationship) to +1.0 (perfect positive linear association).",
                self.styles["BodyDesc"],
            ))

            # Render Correlation Heatmap Image
            heatmap_buf = self._plot_correlation_heatmap(df, num_cols)
            if heatmap_buf:
                story.append(KeepTogether([
                    Image(heatmap_buf, width=440, height=275),
                    Paragraph("Figure 1: Pairwise Pearson Correlation Matrix Heatmap.", self.styles["ChartCaption"]),
                ]))
                story.append(Spacer(1, 10))

            # Top Correlation Pairs Table
            top_pairs = eda_res.get("correlation", {}).get("top_correlations", [])
            if top_pairs:
                story.append(Paragraph("Top Correlated Feature Pairs", self.styles["SubSectionHeader"]))
                pair_headers = [
                    Paragraph("Feature 1", self.styles["TH"]),
                    Paragraph("Feature 2", self.styles["TH"]),
                    Paragraph("Pearson r", self.styles["TH_Right"]),
                    Paragraph("Relationship Direction &amp; Strength", self.styles["TH"]),
                ]
                pair_rows = [pair_headers]

                for p in top_pairs[:6]:
                    r_val = float(p.get("correlation", 0.0))
                    strength = "Strong" if abs(r_val) >= 0.7 else "Moderate" if abs(r_val) >= 0.4 else "Weak"
                    direction = "Positive" if r_val >= 0 else "Negative"
                    r_color = "#0284c7" if r_val >= 0 else "#dc2626"
                    pair_rows.append([
                        Paragraph(f"<b>{p.get('col1')}</b>", self.styles["TD_Bold"]),
                        Paragraph(f"<b>{p.get('col2')}</b>", self.styles["TD_Bold"]),
                        Paragraph(f"<font color='{r_color}'><b>{r_val:+.3f}</b></font>", self.styles["TD_Right"]),
                        Paragraph(f"{strength} {direction} Association", self.styles["TD"]),
                    ])

                t_pairs = Table(pair_rows, colWidths=[printable_w * 0.28, printable_w * 0.28, printable_w * 0.16, printable_w * 0.28])
                t_pairs.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(t_pairs)
        else:
            story.append(Paragraph(
                "<i>At least 2 numerical features are required to compute Pearson correlation coefficients. "
                "Only one or zero numerical columns are present in the dataset.</i>",
                self.styles["BodyDesc"],
            ))

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 8: Data Visualizations (Embedded Actual Charts)
        # -------------------------------------------------------------
        story.append(Paragraph("7. Data Distribution Visualizations", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))
        story.append(Paragraph(
            "Empirical visualizations generated directly from dataset records, including numerical distribution histograms, "
            "categorical observation frequencies, and quartile box plots.",
            self.styles["BodyDesc"],
        ))

        fig_index = 2

        # 1. Box plots of numerical columns
        if len(num_cols) >= 1:
            box_buf = self._plot_box_plots(df, num_cols)
            if box_buf:
                story.append(KeepTogether([
                    Image(box_buf, width=450, height=195),
                    Paragraph(f"Figure {fig_index}: Quartile & Outlier Box-and-Whisker Plots.", self.styles["ChartCaption"]),
                ]))
                fig_index += 1
                story.append(Spacer(1, 8))

        # 2. Histogram of top numerical column
        if len(num_cols) >= 1:
            hist_col = num_cols[0]
            hist_buf = self._plot_histogram(df, hist_col)
            if hist_buf:
                story.append(KeepTogether([
                    Image(hist_buf, width=450, height=195),
                    Paragraph(f"Figure {fig_index}: Numerical Distribution Histogram for '{hist_col}'.", self.styles["ChartCaption"]),
                ]))
                fig_index += 1
                story.append(Spacer(1, 8))

        # 3. Bar chart of top categorical column
        cat_cols = eda_res.get("overview", {}).get("categorical_columns", [])
        if len(cat_cols) >= 1:
            cat_col = cat_cols[0]
            bar_buf = self._plot_categorical_bar(df, cat_col)
            if bar_buf:
                story.append(KeepTogether([
                    Image(bar_buf, width=450, height=195),
                    Paragraph(f"Figure {fig_index}: Observation Frequency Bar Chart for '{cat_col}'.", self.styles["ChartCaption"]),
                ]))
                fig_index += 1
                story.append(Spacer(1, 8))

        story.append(PageBreak())

        # -------------------------------------------------------------
        # SECTION 9: Data Cleaning Summary & Before-vs-After Comparison
        # -------------------------------------------------------------
        story.append(Paragraph("8. Data Cleaning History &amp; Preprocessing Audit", self.styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

        if is_cleaned:
            story.append(Paragraph(
                "This report reflects a <b>Cleaned Dataset</b> processed through the Data Detective Preprocessing Studio. "
                "Below is the sequential log of transformations applied to the original dataset.",
                self.styles["BodyDesc"],
            ))

            if operations:
                story.append(Paragraph("Applied Cleaning Pipeline Operations", self.styles["SubSectionHeader"]))
                for idx, op in enumerate(operations, 1):
                    op_type = op.get("type", "unknown").replace("_", " ").title()
                    details = ", ".join(f"<b>{k}</b>: {v}" for k, v in op.items() if k != "type")
                    story.append(Paragraph(f"<b>Step {idx} [{op_type}]:</b> {details}", self.styles["KeyFindingBullet"]))
                story.append(Spacer(1, 10))
            else:
                story.append(Paragraph("<i>No specific operation parameter log was provided with this cleaned export.</i>", self.styles["BodyDesc"]))

            # Comparative Before vs After Table
            story.append(Paragraph("Before vs. After Comparative Analysis", self.styles["SubSectionHeader"]))

            orig_rows_val = orig_eda.get("overview", {}).get("total_rows", "—") if orig_eda else "Baseline"
            orig_cols_val = orig_eda.get("overview", {}).get("total_columns", "—") if orig_eda else "Baseline"
            orig_mv_val = (
                f"{orig_eda.get('missing_values', {}).get('overall', {}).get('total_missing_cells', 0):,}"
                if orig_eda
                else "—"
            )
            orig_dup_val = (
                f"{orig_eda.get('duplicates', {}).get('duplicate_count', 0):,}"
                if orig_eda
                else "—"
            )
            orig_mem_val = orig_eda.get("overview", {}).get("memory_usage_formatted", "—") if orig_eda else "—"

            comp_headers = [
                Paragraph("Metric", self.styles["TH"]),
                Paragraph("Original Dataset", self.styles["TH_Right"]),
                Paragraph("Cleaned Dataset", self.styles["TH_Right"]),
                Paragraph("Net Change (Δ)", self.styles["TH_Right"]),
            ]

            def fmt_delta(curr: int, orig: Any) -> str:
                if isinstance(orig, int):
                    diff = curr - orig
                    color = "#16a34a" if diff <= 0 else "#dc2626"
                    return f"<font color='{color}'><b>{diff:+d}</b></font>"
                return "—"

            clean_rows = eda_res["overview"]["total_rows"]
            clean_cols = eda_res["overview"]["total_columns"]
            clean_mv = eda_res.get("missing_values", {}).get("overall", {}).get("total_missing_cells", 0)
            clean_dup = eda_res.get("duplicates", {}).get("duplicate_count", 0)

            comp_rows = [
                comp_headers,
                [
                    Paragraph("<b>Total Row Count</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{orig_rows_val}", self.styles["TD_Right"]),
                    Paragraph(f"<b>{clean_rows:,}</b>", self.styles["TD_Right"]),
                    Paragraph(
                        fmt_delta(clean_rows, orig_eda.get("overview", {}).get("total_rows") if orig_eda else None),
                        self.styles["TD_Right"],
                    ),
                ],
                [
                    Paragraph("<b>Total Column Count</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{orig_cols_val}", self.styles["TD_Right"]),
                    Paragraph(f"<b>{clean_cols:,}</b>", self.styles["TD_Right"]),
                    Paragraph(
                        fmt_delta(clean_cols, orig_eda.get("overview", {}).get("total_columns") if orig_eda else None),
                        self.styles["TD_Right"],
                    ),
                ],
                [
                    Paragraph("<b>Total Missing Cells</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{orig_mv_val}", self.styles["TD_Right"]),
                    Paragraph(f"<b>{clean_mv:,}</b>", self.styles["TD_Right"]),
                    Paragraph(
                        fmt_delta(
                            clean_mv,
                            orig_eda.get("missing_values", {}).get("overall", {}).get("total_missing_cells") if orig_eda else None,
                        ),
                        self.styles["TD_Right"],
                    ),
                ],
                [
                    Paragraph("<b>Duplicate Rows</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{orig_dup_val}", self.styles["TD_Right"]),
                    Paragraph(f"<b>{clean_dup:,}</b>", self.styles["TD_Right"]),
                    Paragraph(
                        fmt_delta(clean_dup, orig_eda.get("duplicates", {}).get("duplicate_count") if orig_eda else None),
                        self.styles["TD_Right"],
                    ),
                ],
                [
                    Paragraph("<b>Memory Footprint</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{orig_mem_val}", self.styles["TD_Right"]),
                    Paragraph(f"<b>{eda_res['overview'].get('memory_usage_formatted', 'N/A')}</b>", self.styles["TD_Right"]),
                    Paragraph("Optimized", self.styles["TD_Right"]),
                ],
            ]

            t_comp = Table(comp_rows, colWidths=[printable_w * 0.35, printable_w * 0.22, printable_w * 0.22, printable_w * 0.21])
            t_comp.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(t_comp)

        else:
            story.append(Paragraph(
                "This report reflects the <b>Original Dataset</b> evaluated in its raw, unmodified state. "
                "No data cleaning, missing value imputation, outlier capping, or feature transformations have been applied.",
                self.styles["BodyDesc"],
            ))
            story.append(Spacer(1, 10))

            baseline_data = [
                [
                    Paragraph("<b>Baseline Dimensions:</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{eda_res['overview']['total_rows']:,} rows × {eda_res['overview']['total_columns']} features", self.styles["TD"]),
                ],
                [
                    Paragraph("<b>Baseline Missingness:</b>", self.styles["TD_Bold"]),
                    Paragraph(
                        f"{eda_res.get('missing_values', {}).get('overall', {}).get('total_missing_cells', 0):,} cells "
                        f"({eda_res.get('missing_values', {}).get('overall', {}).get('overall_missing_percentage', 0.0):.2f}%)",
                        self.styles["TD"],
                    ),
                ],
                [
                    Paragraph("<b>Baseline Duplication:</b>", self.styles["TD_Bold"]),
                    Paragraph(
                        f"{eda_res.get('duplicates', {}).get('duplicate_count', 0):,} duplicate records "
                        f"({eda_res.get('duplicates', {}).get('duplicate_percentage', 0.0):.2f}%)",
                        self.styles["TD"],
                    ),
                ],
                [
                    Paragraph("<b>Baseline Outliers:</b>", self.styles["TD_Bold"]),
                    Paragraph(f"{eda_res.get('outliers', {}).get('total_outliers_detected', 0):,} records flagged via IQR", self.styles["TD"]),
                ],
            ]
            t_base = Table(baseline_data, colWidths=[printable_w * 0.35, printable_w * 0.65])
            t_base.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(t_base)
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                "<i>To generate a Before vs. After comparison report, apply transformations in the Data Detective "
                "Cleaning Studio and download a Cleaned Dataset report.</i>",
                self.styles["BodyDesc"],
            ))

        # 6. Build Document with NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_buffer.seek(0)
        return pdf_buffer
