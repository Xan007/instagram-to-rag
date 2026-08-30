"""InstaRAG HTTP API (FastAPI).

Run locally with:  uv run api.py
Interactive docs:  http://localhost:8000/docs
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import saved as saved_config
from config.profiles import (
    ProfileConfig,
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)
from config.settings import VALID_ANALYSIS_MODES, VALID_EMBED_PROVIDERS, VALID_ENGINES, AppSettings, load_settings, save_settings
from src.api.jobs import manager

app = FastAPI(
    title="InstaRAG API",
    description="Extract knowledge from Instagram profiles and saved posts into a vector database for RAG.",
    version="0.2.0",
)

_cors_origins = [o.strip() for o in os.getenv("INSTARAG_CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    expected = os.getenv("INSTARAG_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")


class ProfileIn(BaseModel):
    username: str
    interests: str = ""
    max_posts: int = 50
    analysis_mode: str = "gemini"
    audio_only: bool = False


class ProfilePatch(BaseModel):
    interests: Optional[str] = None
    max_posts: Optional[int] = None
    analysis_mode: Optional[str] = None
    audio_only: Optional[bool] = None


class RunIn(BaseModel):
    username: str
    newer_than: Optional[str] = None
    keep_media: bool = False


class AddReelIn(BaseModel):
    url: Optional[str] = None
    urls: Optional[List[str]] = None
    creator: Optional[str] = None
    caption_only: bool = False
    keep_media: bool = False

    def resolved_urls(self) -> List[str]:
        items = list(self.urls or [])
        if self.url:
            items.append(self.url)
        return [u.strip() for u in items if u and u.strip()]


class SavedProcessIn(BaseModel):
    limit: Optional[int] = None
    caption_only: bool = False
    workers: int = 4


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class QueryIn(BaseModel):
    question: str
    creator: Optional[str] = None
    mode: str = "grounded_plus"
    top_k: int = 6
    min_score: float = 0.35
    history: Optional[List[ChatTurn]] = None



@app.get("/health", tags=["meta"])
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/config", tags=["config"])
def get_config(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    return vars(load_settings())


@app.patch("/config", tags=["config"])
def patch_config(patch: Dict[str, Any], _: None = Depends(require_api_key)) -> Dict[str, Any]:
    settings = load_settings()
    allowed = {"audio_only", "engine", "embed_provider"}
    for key, value in patch.items():
        if key not in allowed:
            raise HTTPException(status_code=422, detail=f"Unknown setting '{key}'.")
        if key == "engine" and value not in VALID_ENGINES:
            raise HTTPException(status_code=422, detail=f"engine must be one of {sorted(VALID_ENGINES)}.")
        if key == "embed_provider" and value not in VALID_EMBED_PROVIDERS:
            raise HTTPException(status_code=422, detail=f"embed_provider must be one of {sorted(VALID_EMBED_PROVIDERS)}.")
        setattr(settings, key, value)
    save_settings(settings)
    return vars(load_settings())


def _profile_to_dict(p: ProfileConfig) -> Dict[str, Any]:
    return {
        "username": p.username,
        "interests": p.interests,
        "max_posts": p.max_posts,
        "analysis_mode": p.analysis_mode,
        "audio_only": p.audio_only,
        "processed_count": len(p.processed_ids),
        "failed_ids": p.failed_ids,
    }


@app.get("/profiles", tags=["profiles"])
def get_profiles(_: None = Depends(require_api_key)) -> List[Dict[str, Any]]:
    result = []
    for username in list_profiles():
        p = load_profile(username)
        if p:
            result.append(_profile_to_dict(p))
    return result


@app.post("/profiles", status_code=201, tags=["profiles"])
def create_or_update_profile(body: ProfileIn, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    if body.analysis_mode not in VALID_ANALYSIS_MODES:
        raise HTTPException(status_code=422, detail=f"analysis_mode must be one of {sorted(VALID_ANALYSIS_MODES)}.")
    profile = load_profile(body.username)
    existed = profile is not None
    if profile is None:
        profile = ProfileConfig(username=body.username)
    profile.interests = body.interests
    profile.max_posts = body.max_posts
    profile.analysis_mode = body.analysis_mode
    profile.audio_only = body.audio_only
    save_profile(profile)
    data = _profile_to_dict(profile)
    data["updated_existing"] = existed
    return data


@app.get("/profiles/{username}", tags=["profiles"])
def get_profile(username: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    profile = load_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile @{username} not found.")
    return _profile_to_dict(profile)


@app.patch("/profiles/{username}", tags=["profiles"])
def patch_profile(username: str, body: ProfilePatch, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    profile = load_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile @{username} not found.")
    if body.analysis_mode is not None:
        if body.analysis_mode not in VALID_ANALYSIS_MODES:
            raise HTTPException(status_code=422, detail=f"analysis_mode must be one of {sorted(VALID_ANALYSIS_MODES)}.")
        profile.analysis_mode = body.analysis_mode
    if body.interests is not None:
        profile.interests = body.interests
    if body.max_posts is not None:
        profile.max_posts = body.max_posts
    if body.audio_only is not None:
        profile.audio_only = body.audio_only
    save_profile(profile)
    return _profile_to_dict(profile)


@app.delete("/profiles/{username}", tags=["profiles"])
def remove_profile(username: str, _: None = Depends(require_api_key)) -> Dict[str, str]:
    if not delete_profile(username):
        raise HTTPException(status_code=404, detail=f"Profile @{username} not found.")
    return {"deleted": username}


@app.post("/profiles/{username}/reset", tags=["profiles"])
def reset_profile(username: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    profile = load_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile @{username} not found.")
    cleared = len(profile.processed_ids) + len(profile.failed_ids)
    profile.processed_ids = []
    profile.failed_ids = []
    save_profile(profile)
    return {"reset": username, "cleared": cleared}


def _submit(kind: str, fn, **fn_kwargs) -> JSONResponse:
    job = manager.submit(kind, fn, **fn_kwargs)
    return JSONResponse(status_code=202, content={"job_id": job.id, "status_url": f"/jobs/{job.id}"})


@app.post("/jobs/run", status_code=202, tags=["jobs"])
def job_run(body: RunIn, _: None = Depends(require_api_key)) -> JSONResponse:
    from src.pipeline import run_profile

    if not load_profile(body.username):
        raise HTTPException(status_code=404, detail=f"Profile @{body.username} not found. Create it via POST /profiles.")
    return _submit(
        "run",
        run_profile,
        username=body.username,
        newer_than=body.newer_than,
        keep_media=body.keep_media,
    )


@app.post("/jobs/add-reel", status_code=202, tags=["jobs"])
def job_add_reel(body: AddReelIn, _: None = Depends(require_api_key)) -> JSONResponse:
    from src.pipeline import add_reel

    urls = body.resolved_urls()
    if not urls:
        raise HTTPException(status_code=422, detail="Provide 'url' (string) or 'urls' (list of strings).")
    return _submit(
        "add-reel",
        add_reel,
        urls=urls,
        creator=body.creator,
        caption_only=body.caption_only,
        keep_media=body.keep_media,
    )


@app.post("/jobs/saved-process", status_code=202, tags=["jobs"])
def job_saved_process(body: SavedProcessIn, _: None = Depends(require_api_key)) -> JSONResponse:
    from src.pipeline import process_saved

    return _submit(
        "saved-process",
        process_saved,
        limit=body.limit,
        caption_only=body.caption_only,
        workers=body.workers,
    )


@app.get("/jobs", tags=["jobs"])
def list_jobs(
    include_log: bool = False,
    log_limit: int = 20,
    _: None = Depends(require_api_key),
) -> Dict[str, Any]:
    current = manager.current()
    jobs = []
    for j in manager.all_jobs():
        data = j.to_dict(include_log=include_log, log_limit=log_limit)
        if j.status == "queued" and current is not None:
            data["queued_behind"] = current.id
            data["note"] = f"Serialized worker busy with job {current.id} ({current.kind}); this job starts when it finishes."
        jobs.append(data)
    return {
        "worker": {"current_job": current.id, "kind": current.kind} if current else {"current_job": None, "idle": True},
        "jobs": jobs,
    }


@app.get("/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: str, log_limit: int = 200, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict(log_limit=log_limit)


@app.post("/saved/import", tags=["saved"])
async def saved_import(file: UploadFile = File(...), _: None = Depends(require_api_key)) -> Dict[str, Any]:
    suffix = Path(file.filename or "export.zip").suffix.lower()
    if suffix not in (".zip", ".json"):
        raise HTTPException(status_code=422, detail="Upload a .zip export or a saved_posts.json file.")

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            shutil.copyfileobj(file.file, tmp)
        state = saved_config.import_saved_posts(Path(tmp_path))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(tmp_path)

    return {
        "total": state.total,
        "imported_at": state.imported_at,
        "source": state.source,
        "processed": len(state.processed_ids),
        "failed": len(state.failed_ids),
    }


@app.get("/saved/status", tags=["saved"])
def saved_status(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    state = saved_config.load_state()
    if state.total == 0:
        return {"imported": False}
    return {
        "imported": True,
        "total": state.total,
        "imported_at": state.imported_at,
        "source": state.source,
        "processed": len(state.processed_ids),
        "failed": len(state.failed_ids),
        "pending": max(state.total - len(state.processed_ids), 0),
        "failed_ids": state.failed_ids,
    }


@app.post("/saved/reset", tags=["saved"])
def saved_reset(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    state = saved_config.load_state()
    cleared = len(state.processed_ids) + len(state.failed_ids)
    state.processed_ids = []
    state.failed_ids = []
    saved_config.save_state(state)
    return {"cleared": cleared}


@app.post("/query", tags=["rag"])
def query(body: QueryIn, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Grounded RAG query.

    mode='grounded_plus' (default) answers from creator content and may append
    a clearly labeled general-knowledge block. mode='strict' never leaves the
    creators' content.
    """
    if body.mode not in ("strict", "grounded_plus"):
        raise HTTPException(status_code=422, detail="mode must be 'strict' or 'grounded_plus'.")
    if not 1 <= body.top_k <= 20:
        raise HTTPException(status_code=422, detail="top_k must be between 1 and 20.")
    if not 0 <= body.min_score <= 1:
        raise HTTPException(status_code=422, detail="min_score must be between 0 and 1.")

    history_dicts = None
    if body.history is not None:
        if len(body.history) > 12:
            raise HTTPException(status_code=422, detail="history supports at most 12 messages.")
        history_dicts = [{"role": t.role, "content": t.content} for t in body.history]

    from src.pipeline import query_knowledge

    try:
        return query_knowledge(
            body.question,
            body.creator,
            top_k=body.top_k,
            min_score=body.min_score,
            mode=body.mode,
            history=history_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Query failed: {e}")
