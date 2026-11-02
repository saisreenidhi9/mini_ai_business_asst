"""
FastAPI application entry point.
Exposes RESTful endpoints for health checks, business metrics, metadata,
and natural language sales intelligence queries.
Serves frontend dashboard static assets.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.analytics import get_dataset_metadata
from app.config import settings
from app.data_loader import find_csv_file, import_csv_to_db
from app.database import connect_db, init_db
from app.schemas import (
    HealthResponse,
    MetadataResponse,
    QuestionRequest,
    QuestionResponse,
    SummaryResponse,
)
from app.services import get_application_summary, process_question

# Setup logging
logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bi_assistant")

FRONTEND_DIR = settings.BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: ensures database exists and loads CSV if needed.
    """
    logger.info("Initializing Mini AI Business Intelligence Assistant...")
    try:
        init_db()
        csv_file = find_csv_file()
        import_result = import_csv_to_db(csv_path=csv_file)
        logger.info(
            f"Data initialization completed: {import_result['status']} | "
            f"Total rows: {import_result['total_records']}, Valid: {import_result['valid_records']}, "
            f"Flagged: {import_result['flagged_records']}"
        )
    except Exception as e:
        logger.error(f"Error during startup data initialization: {e}")

    yield
    logger.info("Shutting down Mini AI Business Intelligence Assistant.")


app = FastAPI(
    title="Mini AI Business Intelligence Assistant",
    description="Natural-language business intelligence API querying sales transactions.",
    version=__version__,
    lifespan=lifespan,
)

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """
    Check application health and SQLite database connectivity.
    """
    db_connected = False
    total_records = 0
    valid_records = 0
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM sales_transactions;")
        total_records = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS valid FROM sales_transactions WHERE is_valid = 1;")
        valid_records = cursor.fetchone()["valid"]
        conn.close()
        db_connected = True
    except Exception as e:
        logger.error(f"Health check database failure: {e}")

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        database_connected=db_connected,
        total_records=total_records,
        valid_records=valid_records,
        version=__version__,
    )


@app.get("/api/summary", response_model=SummaryResponse, tags=["Analytics"])
def get_summary():
    """
    Return overall database-backed summary KPI metrics and data quality disclosures.
    """
    try:
        return get_application_summary()
    except Exception as e:
        logger.error(f"Summary computation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute business summary metrics.",
        )


@app.get("/api/metadata", response_model=MetadataResponse, tags=["Analytics"])
def get_metadata_endpoint():
    """
    Return dataset metadata: date ranges, distinct dimensions, categories, and audit flags.
    """
    try:
        conn = connect_db()
        try:
            metadata = get_dataset_metadata(conn)
            return MetadataResponse(**metadata)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Metadata retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dataset metadata.",
        )


@app.post("/api/ask", response_model=QuestionResponse, tags=["Analytics"])
def ask_question(request: QuestionRequest):
    """
    Interpret a natural-language business question and return a structured, verified analytical answer.
    """
    q = request.question.strip()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question string cannot be empty.",
        )

    try:
        return process_question(q)
    except Exception as e:
        logger.error(f"Error processing question '{q}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the question.",
        )


# Global Exception Handler to avoid exposing stack traces
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please verify your query or check server logs."},
    )


# Serve frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend index.html not found."},
        )
