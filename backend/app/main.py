from __future__ import annotations
import uuid
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from .parser import parse_srd_url, parse_markdown, extract_metadata
from .scraper import scrape_service
from .comparator import compare_srd_with_form

app = FastAPI(title="SRD Compliance Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict = {}


async def _run_analysis(
    job_id: str,
    srd_url: Optional[str],
    srd_content: Optional[str],
    service_url: str,
) -> None:
    _jobs[job_id]["status"] = "running"
    try:
        if srd_url:
            srd_fields = await parse_srd_url(srd_url)
            srd_source = srd_url
        elif srd_content:
            srd_fields = await parse_markdown(srd_content)
            srd_source = "uploaded_file"
        else:
            raise ValueError("Provide srd_url or upload a markdown file")

        form_fields = await scrape_service(service_url)
        report = compare_srd_with_form(job_id, service_url, srd_source, srd_fields, form_fields)

        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["result"] = report.model_dump()
    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)


@app.post("/api/parse-srd")
async def parse_srd_endpoint(
    srd_url: Optional[str] = Form(None),
    srd_file: Optional[UploadFile] = File(None),
):
    """Parse an SRD document and return the extracted fields + metadata immediately (no scraping)."""
    if not srd_file and not srd_url:
        raise HTTPException(status_code=400, detail="Provide srd_file or srd_url")

    if srd_file:
        raw = await srd_file.read()
        content = raw.decode("utf-8", errors="replace")
        fields = await parse_markdown(content)
        metadata = extract_metadata(content)
        source = srd_file.filename or "uploaded_file"
    else:
        fields = await parse_srd_url(srd_url)
        metadata = {}
        source = srd_url

    return {
        "source": source,
        "field_count": len(fields),
        "fields": [f.model_dump() for f in fields],
        "metadata": metadata,
    }


@app.post("/api/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    service_url: str = Form(...),
    srd_url: Optional[str] = Form(None),
    srd_file: Optional[UploadFile] = File(None),
):
    """Start analysis. Accepts multipart/form-data with service_url + (srd_url or srd_file)."""
    if not srd_file and not srd_url:
        raise HTTPException(status_code=400, detail="Provide srd_file or srd_url")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "result": None, "error": None}

    srd_content: Optional[str] = None
    if srd_file:
        raw = await srd_file.read()
        srd_content = raw.decode("utf-8", errors="replace")

    background_tasks.add_task(_run_analysis, job_id, srd_url, srd_content, service_url)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}


@app.get("/api/report/{job_id}")
async def get_report(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    if job["status"] in ("pending", "running"):
        raise HTTPException(status_code=202, detail="Analysis still in progress")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job["error"])
    return job["result"]


@app.get("/")
async def root():
    return {"message": "SRD Compliance Bot API", "docs": "/docs"}
