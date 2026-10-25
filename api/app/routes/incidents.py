from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request
from temporalio.client import WorkflowQueryFailedError

from app.models import DecisionRequest, DecisionResponse, IncidentDetail, IncidentList
from app.temporal import TemporalDep

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# Must match worker/app/contracts.py. Plain strings so the api doesn't import worker code.
WORKFLOW_TYPE = "InvestigateIncident"
PROGRESS_QUERY = "get_progress"
DECISION_SIGNAL = "submit_decision"

WorkflowId = Annotated[str, Path(pattern=r"^incident-[A-Z]{2,10}$")]


def _rpc_timeout(request: Request) -> timedelta:
    return timedelta(seconds=request.app.state.settings.temporal_rpc_timeout_s)


@router.get("", response_model=IncidentList)
async def list_incidents(
    request: Request,
    client: TemporalDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> IncidentList:
    """Newest first. Each run of incident-<BANK> is one incident."""
    runs = [
        run
        async for run in client.list_workflows(
            f"WorkflowType = '{WORKFLOW_TYPE}'", limit=limit, rpc_timeout=_rpc_timeout(request)
        )
    ]
    runs.sort(key=lambda run: run.start_time, reverse=True)
    return IncidentList.model_validate(
        {
            "incidents": [
                {
                    "workflow_id": run.id,
                    "run_id": run.run_id,
                    "bank": run.id.removeprefix("incident-"),
                    "temporal_status": run.status.name if run.status else "UNKNOWN",
                    "started_at": run.start_time,
                    "closed_at": run.close_time,
                }
                for run in runs
            ]
        }
    )


@router.get("/{workflow_id}", response_model=IncidentDetail)
async def get_incident(
    workflow_id: WorkflowId,
    request: Request,
    client: TemporalDep,
    run_id: Annotated[str | None, Query(max_length=100)] = None,
) -> IncidentDetail:
    handle = client.get_workflow_handle(workflow_id, run_id=run_id)
    timeout = _rpc_timeout(request)
    description = await handle.describe(rpc_timeout=timeout)
    try:
        # Works on closed runs too: Temporal replays the history to answer.
        progress = await handle.query(PROGRESS_QUERY, rpc_timeout=timeout)
    except WorkflowQueryFailedError as exc:
        raise HTTPException(status_code=503, detail=f"Progress unavailable: {exc}") from exc
    return IncidentDetail(
        workflow_id=workflow_id,
        run_id=description.run_id,
        temporal_status=description.status.name if description.status else "UNKNOWN",
        progress=progress,
    )


@router.post("/{workflow_id}/decision", response_model=DecisionResponse)
async def decide(
    workflow_id: WorkflowId,
    body: DecisionRequest,
    request: Request,
    client: TemporalDep,
) -> DecisionResponse:
    """Approve or reject the proposed fix. Sends the Temporal signal the workflow waits on.

    Safe to repeat: the workflow keeps the first decision. A closed incident answers 404.
    """
    handle = client.get_workflow_handle(workflow_id, run_id=body.run_id)
    await handle.signal(
        DECISION_SIGNAL,
        {"approved": body.approved, "by": body.by, "note": body.note},
        rpc_timeout=_rpc_timeout(request),
    )
    return DecisionResponse(workflow_id=workflow_id)
