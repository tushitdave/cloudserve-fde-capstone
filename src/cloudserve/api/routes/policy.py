"""Read-only active policy and the operator kill switch (operator role required to change it)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cloudserve.domain.policies import policy
from cloudserve.api.security import Principal, require

router = APIRouter(prefix="/v1/policy", tags=["policy"])


class KillSwitchIn(BaseModel):
    active: bool
    operator: str
    reason: str


@router.get("/active")
def active_policy(_principal=Depends(require("support_agent", "operator", "knowledge_owner"))):
    rules = [{k: rule[k] for k in ("rule_id", "priority", "name", "kind", "action", "reason", "evidence", "requirement_ids")}
             for rule in policy.POLICY["rules"]]
    return {"policy_version": policy.POLICY_VERSION, "effective_from": policy.POLICY["effective_from"],
            "owner": policy.POLICY["owner"], "thresholds": policy.THRESHOLDS, "rules": rules,
            "kill_switch": policy.kill_switch_state()}


@router.get("/kill-switch")
def kill_switch(_principal=Depends(require("support_agent", "operator", "knowledge_owner"))):
    return policy.kill_switch_state()


@router.post("/kill-switch")
def set_kill_switch(payload: KillSwitchIn, principal: Principal = Depends(require("operator"))):
    if not payload.operator.strip() or len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="Operator name and a reason of at least 5 characters are required")
    return policy.set_kill_switch(payload.active, f"{payload.operator.strip()} ({principal.key_id})", payload.reason.strip())
