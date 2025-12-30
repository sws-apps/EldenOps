"""Team goals and intents API."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from eldenops.api.deps import CurrentUser, get_db
from eldenops.db.models.tenant import Tenant

logger = structlog.get_logger()
router = APIRouter()


class TeamGoal(BaseModel):
    """A team goal/intent."""

    id: str
    name: str
    description: str
    priority: int = Field(ge=1, le=5, default=3)  # 1=highest, 5=lowest
    category: str  # 'delivery', 'productivity', 'quality', 'wellbeing', 'cost'
    target_metric: Optional[str] = None  # e.g., 'on_time_delivery_rate', 'average_work_hours'
    target_value: Optional[float] = None
    is_active: bool = True


class TeamGoalsConfig(BaseModel):
    """Team goals configuration."""

    goals: list[TeamGoal] = []
    primary_focus: Optional[str] = None  # The main goal category to focus on


class UpdateGoalsRequest(BaseModel):
    """Request to update team goals."""

    goals: list[TeamGoal]
    primary_focus: Optional[str] = None


# Predefined goal templates
GOAL_TEMPLATES = {
    "launch_on_time": TeamGoal(
        id="launch_on_time",
        name="Launch Projects On Time",
        description="Ensure all projects are delivered by their target dates",
        priority=1,
        category="delivery",
        target_metric="on_time_delivery_rate",
        target_value=95.0,
    ),
    "cost_efficiency": TeamGoal(
        id="cost_efficiency",
        name="Cost Efficiency",
        description="Optimize resource usage and reduce unnecessary costs",
        priority=2,
        category="cost",
        target_metric="budget_variance",
        target_value=10.0,
    ),
    "team_productivity": TeamGoal(
        id="team_productivity",
        name="Team Productivity",
        description="Maximize team output while maintaining quality",
        priority=2,
        category="productivity",
        target_metric="velocity_trend",
        target_value=0.0,  # positive means improving
    ),
    "work_life_balance": TeamGoal(
        id="work_life_balance",
        name="Work-Life Balance",
        description="Ensure team members maintain healthy work hours",
        priority=3,
        category="wellbeing",
        target_metric="overtime_hours",
        target_value=5.0,  # max 5 hours overtime per week
    ),
    "code_quality": TeamGoal(
        id="code_quality",
        name="Code Quality",
        description="Maintain high code quality standards",
        priority=2,
        category="quality",
        target_metric="pr_review_coverage",
        target_value=100.0,
    ),
}


@router.get("")
async def get_team_goals(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamGoalsConfig:
    """Get team goals configuration."""
    tenant_id = current_user.get("primary_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant selected",
        )
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Extract goals from settings
    settings = tenant.settings or {}
    goals_data = settings.get("goals", {})

    return TeamGoalsConfig(
        goals=[TeamGoal(**g) for g in goals_data.get("goals", [])],
        primary_focus=goals_data.get("primary_focus"),
    )


@router.put("")
async def update_team_goals(
    request: UpdateGoalsRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamGoalsConfig:
    """Update team goals configuration (admin/owner only)."""
    tenant_id = current_user.get("primary_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant selected",
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Update settings with new goals
    settings = tenant.settings or {}
    settings["goals"] = {
        "goals": [g.model_dump() for g in request.goals],
        "primary_focus": request.primary_focus,
    }
    tenant.settings = settings

    await db.commit()

    logger.info(
        "Team goals updated",
        tenant_id=tenant_id,
        goal_count=len(request.goals),
        primary_focus=request.primary_focus,
    )

    return TeamGoalsConfig(
        goals=request.goals,
        primary_focus=request.primary_focus,
    )


@router.get("/templates")
async def get_goal_templates() -> dict[str, TeamGoal]:
    """Get available goal templates."""
    return GOAL_TEMPLATES


@router.post("/apply-template/{template_id}")
async def apply_goal_template(
    template_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamGoalsConfig:
    """Apply a goal template to the team."""
    tenant_id = current_user.get("primary_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant selected",
        )

    if template_id not in GOAL_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found",
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Get current goals
    settings = tenant.settings or {}
    goals_data = settings.get("goals", {"goals": [], "primary_focus": None})
    current_goals = [TeamGoal(**g) for g in goals_data.get("goals", [])]

    # Add template if not already present
    template = GOAL_TEMPLATES[template_id]
    if not any(g.id == template_id for g in current_goals):
        current_goals.append(template)

    # Update settings
    settings["goals"] = {
        "goals": [g.model_dump() for g in current_goals],
        "primary_focus": goals_data.get("primary_focus") or template.category,
    }
    tenant.settings = settings

    await db.commit()

    logger.info(
        "Goal template applied",
        tenant_id=tenant_id,
        template_id=template_id,
    )

    return TeamGoalsConfig(
        goals=current_goals,
        primary_focus=settings["goals"]["primary_focus"],
    )
