"""FastAPI application for the inspectable Proofloom operator surface."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .service import ProofloomService


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=80)
    requested_amount_paise: int | None = Field(default=None, ge=0, le=10_000_000_000)


def create_app(service: ProofloomService | None = None) -> FastAPI:
    runtime = service or ProofloomService()
    app = FastAPI(
        title="Proofloom",
        version="1.0.0",
        description="Verification-first settlement close using synthetic evidence only.",
        docs_url="/api/docs",
        redoc_url=None,
    )
    web_root = Path(__file__).resolve().parent / "web"
    evaluation_path = Path(__file__).resolve().parents[2] / "evaluation" / "results.json"

    @app.get("/healthz")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "project": "Proofloom",
            "mode": "synthetic-local",
            "real_money_actions": False,
            "model_authority": "candidate ranking only",
        }

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        return runtime.overview()

    @app.post("/api/reset")
    def reset() -> dict[str, object]:
        return runtime.reset()

    @app.post("/api/run-close")
    def run_close() -> dict[str, object]:
        return runtime.run_close()

    @app.post("/api/review/{decision_id}")
    def review(decision_id: str, request: ReviewRequest) -> dict[str, object]:
        try:
            return runtime.review(
                decision_id,
                action=request.action,
                reviewer=request.reviewer,
                requested_amount_paise=request.requested_amount_paise,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown decision: {decision_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/failures/{scenario}")
    def failure(scenario: str) -> dict[str, object]:
        try:
            return runtime.failure(scenario)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/audit")
    def audit() -> dict[str, object]:
        return runtime.audit()

    @app.get("/api/evaluation")
    def evaluation() -> object:
        if not evaluation_path.is_file():
            raise HTTPException(status_code=503, detail="run `make evaluate` to generate the retained result")
        return json.loads(evaluation_path.read_text(encoding="utf-8"))

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    app.mount("/static", StaticFiles(directory=web_root), name="static")
    app.state.proofloom_service = runtime
    return app


app = create_app()
