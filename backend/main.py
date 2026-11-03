"""Data Detective Backend API.

FastAPI application providing health checks, dataset upload, preview,
automated exploratory data analysis (EDA), data cleaning & preprocessing studio,
and interactive data visualization studio services.
"""

import logging
import os
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.services.eda_engine import (
    EDAEngine,
    DatasetValidationError,
    MAX_FILE_SIZE,
)
from backend.services.cleaning_engine import CleaningEngine
from backend.services.visualization_engine import VisualizationEngine
from backend.services.report_engine import ReportEngine

logger = logging.getLogger("data_detective_api")

app = FastAPI(
    title="Data Detective API",
    description="Backend API for exploratory data analysis, dataset profiling, interactive cleaning studio, visualization studio, automated report generation, and multi-format dataset conversion (CSV, Excel, JSON).",
    version="0.7.0",
)

# Production-ready CORS configuration supporting environment overrides
raw_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
allowed_origins = [orig.strip() for orig in raw_origins if orig.strip()]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject standard security headers into all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(DatasetValidationError)
async def dataset_validation_exception_handler(request: Request, exc: DatasetValidationError):
    """Normalize domain validation exceptions into structured HTTP JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Intercept unhandled exceptions to prevent stack trace leakage to clients."""
    logger.exception("Unhandled server exception processing request to %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred. Please verify dataset integrity and try again."},
    )


eda_engine = EDAEngine()
cleaning_engine = CleaningEngine(eda_engine=eda_engine)
visualization_engine = VisualizationEngine(eda_engine=eda_engine)
report_engine = ReportEngine(eda_engine=eda_engine, cleaning_engine=cleaning_engine)


@app.get("/")
@app.get("/api")
@app.get("/api/")
def read_root():
    """Root endpoint welcoming clients and confirming API availability."""
    return {
        "message": "Welcome to Data Detective API",
        "status": "online",
        "version": "0.7.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "docs_url": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check endpoint to verify system status."""
    return {
        "status": "healthy"
    }


@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and preview a CSV or Excel (.xlsx) dataset.

    Validates file extension, size limit (10 MB), parses with Pandas,
    and returns dataset dimensions, column data types, and first 5 rows preview.
    Datasets are processed in-memory and are not permanently saved to disk.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        result = eda_engine.parse_dataset(filename=file.filename, content=content)
        return result

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error processing file '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the dataset. Please verify the file and try again.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/analyze")
@app.post("/api/eda", include_in_schema=False)
async def analyze_dataset(file: UploadFile = File(...)):
    """Phase 3: Perform automated Exploratory Data Analysis (EDA) on an uploaded CSV/XLSX dataset.

    Reuses in-memory parsing, returns dataset overview, statistical summary (describe),
    missing values analysis, duplicate detection, column unique analysis, IQR outlier detection,
    correlation matrix, and distribution histograms.
    Datasets are processed in-memory and are not permanently saved to disk.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in analyze request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        result = eda_engine.analyze_dataset(filename=file.filename, content=content)
        return result

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error analyzing file '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while analyzing the dataset. Please verify the file and try again.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/clean/preview")
async def preview_clean_dataset(
    file: UploadFile = File(...),
    operations: str = Form("[]"),
):
    """Phase 4: Preview data cleaning & preprocessing transformations.

    Validates operations, executes cleaning pipeline on an in-memory copy,
    and returns Before vs After summary metrics, 5-row preview, diff stats,
    and operations execution log without modifying original files.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in cleaning preview request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        preview_result = cleaning_engine.preview_clean(
            filename=file.filename,
            content=content,
            operations_input=operations,
        )
        return preview_result

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in cleaning preview for '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while previewing cleaning operations. Please check your operations and try again.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/clean/download")
async def download_cleaned_dataset(
    file: UploadFile = File(...),
    operations: str = Form("[]"),
    format: str = Form("csv"),
):
    """Phase 4: Apply cleaning operations and export downloadable cleaned dataset file (CSV, XLSX, or JSON).

    Never overwrites original uploaded files; generates export bytes purely in-memory.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in download request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        file_bytes, mime_type, export_filename = cleaning_engine.export_cleaned_dataset(
            filename=file.filename,
            content=content,
            operations_input=operations,
            output_format=format,
        )

        return Response(
            content=file_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error exporting cleaned file for '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the cleaned dataset file.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/export/original")
async def export_original_dataset(
    file: UploadFile = File(...),
    format: str = Form("csv"),
):
    """Multi-Format Export: Export uploaded dataset in CSV, Excel (.xlsx), or JSON (.json) format.

    Enables seamless format conversion purely in-memory with zero disk persistence.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in export request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        file_bytes, mime_type, export_filename = cleaning_engine.export_original_dataset(
            filename=file.filename,
            content=content,
            output_format=format,
        )

        return Response(
            content=file_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error exporting original file for '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while exporting the dataset file.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/visualize")
async def generate_visualization(
    file: UploadFile = File(...),
    chart_type: str = Form(...),
    x_column: Optional[str] = Form(None),
    y_column: Optional[str] = Form(None),
    aggregation: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    config: Optional[str] = Form(None),
):
    """Phase 5: Generate chart visualization payload from CSV/XLSX dataset.

    Supports Bar, Line, Pie/Donut, Histogram, Scatter, Box Plot, and Correlation Heatmap.
    Accepts chart type, dynamic X/Y columns, optional aggregation, title, and config.
    Validates column data types and parameters server-side.
    Datasets are processed in-memory and are not permanently saved to disk.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in visualization request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        clean_x = x_column.strip() if x_column and x_column.strip() else None
        clean_y = y_column.strip() if y_column and y_column.strip() else None
        clean_agg = aggregation.strip() if aggregation and aggregation.strip() else None
        clean_title = title.strip() if title and title.strip() else None
        clean_config = config.strip() if config and config.strip() else None

        result = visualization_engine.visualize(
            filename=file.filename,
            content=content,
            chart_type=chart_type,
            x_column=clean_x,
            y_column=clean_y,
            aggregation=clean_agg,
            title=clean_title,
            config=clean_config,
        )
        return result

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error generating visualization for '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the visualization. Please check your selections and try again.",
        ) from exc
    finally:
        await file.close()


@app.post("/api/report/generate")
async def generate_eda_report(
    file: UploadFile = File(...),
    dataset_type: str = Form("original"),
    operations: Optional[str] = Form(None),
    original_file: Optional[UploadFile] = File(None),
):
    """Phase 6: Generate an in-memory, publication-ready PDF exploratory data analysis report.

    Integrates full EDA statistical profiling, data quality analysis, outlier audits,
    correlation matrices, embedded Matplotlib visualizations, and cleaning history with
    Before vs. After comparative metrics.
    All PDF documents are streamed directly to the client without permanent disk persistence.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in report generation request.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum allowed size of 10 MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        original_content: Optional[bytes] = None
        original_filename: Optional[str] = None

        if original_file and original_file.filename:
            original_content = await original_file.read(MAX_FILE_SIZE + 1)
            if len(original_content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Original comparison file exceeds maximum allowed size of 10 MB.",
                )
            original_filename = original_file.filename

        pdf_buffer = report_engine.generate_report_pdf(
            filename=file.filename,
            content=content,
            dataset_type=dataset_type,
            operations_input=operations,
            original_content=original_content,
            original_filename=original_filename,
        )

        base_name = os.path.splitext(file.filename)[0]
        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base_name)
        out_filename = f"data_detective_eda_report_{safe_title}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{out_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error generating report for '%s'", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the PDF report. Please verify dataset integrity and try again.",
        ) from exc
    finally:
        await file.close()
        if original_file:
            await original_file.close()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")

    # Support running either from root or from backend folder
    app_import = "backend.main:app" if os.path.exists("backend") else "main:app"
    uvicorn.run(app_import, host=host, port=port, reload=reload)
