"""Project and team management endpoints."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional, List

import discord
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from eldenops.api.deps import CurrentUser, DBSession, TenantID, TenantMembership
from eldenops.db.models.project import (
    GitHubIdentity,
    Project,
    ProjectGitHubLink,
    ProjectMember,
    TenantProjectConfig,
)
from eldenops.db.models.github import GitHubConnection
from eldenops.db.models.user import User
from eldenops.db.models.tenant import Tenant

logger = structlog.get_logger()
router = APIRouter()


# ============ Response Schemas ============

class GitHubIdentityResponse(BaseModel):
    id: str
    user_id: str
    committer_email: str
    committer_name: Optional[str]
    is_verified: bool


class ProjectMemberResponse(BaseModel):
    id: str
    user_id: str
    discord_username: Optional[str]
    github_username: Optional[str]
    role: str
    responsibilities: dict[str, Any]
    assigned_at: str
    is_active: bool


class ProjectGitHubLinkResponse(BaseModel):
    id: str
    github_connection_id: str
    repo_full_name: str
    branch_filter: Optional[str]
    is_primary: bool


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    discord_thread_id: Optional[int]
    discord_thread_name: Optional[str]
    start_date: Optional[str]
    target_launch_date: Optional[str]
    objectives: dict[str, Any]
    kpi_config: dict[str, Any]
    launch_checklist: dict[str, Any]
    members: List[ProjectMemberResponse]
    github_links: List[ProjectGitHubLinkResponse]
    created_at: str
    updated_at: str


class ProjectConfigResponse(BaseModel):
    id: str
    task_channel_id: Optional[int]
    task_channel_name: Optional[str]
    thread_name_pattern: str
    auto_create_projects: bool
    report_config: dict[str, Any]
    default_kpis: dict[str, Any]
    ai_config: dict[str, Any]


class TeamMemberResponse(BaseModel):
    id: str
    discord_id: int
    discord_username: Optional[str]
    github_username: Optional[str]
    email: Optional[str]
    github_identities: List[GitHubIdentityResponse]
    project_count: int
    is_active: bool


# ============ Request Schemas ============

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    discord_thread_id: Optional[int] = None
    discord_thread_name: Optional[str] = None
    start_date: Optional[str] = None
    target_launch_date: Optional[str] = None
    objectives: dict[str, Any] = {}


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    discord_thread_id: Optional[int] = None
    discord_thread_name: Optional[str] = None
    start_date: Optional[str] = None
    target_launch_date: Optional[str] = None
    objectives: Optional[dict[str, Any]] = None
    kpi_config: Optional[dict[str, Any]] = None
    launch_checklist: Optional[dict[str, Any]] = None


class AddProjectMemberRequest(BaseModel):
    user_id: str
    role: str = "developer"
    responsibilities: dict[str, Any] = {}


class UpdateProjectMemberRequest(BaseModel):
    role: Optional[str] = None
    responsibilities: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class LinkGitHubRepoRequest(BaseModel):
    github_connection_id: str
    branch_filter: Optional[str] = None
    is_primary: bool = False


class AddGitHubIdentityRequest(BaseModel):
    user_id: str
    committer_email: str
    committer_name: Optional[str] = None


class UpdateProjectConfigRequest(BaseModel):
    task_channel_id: Optional[int] = None
    task_channel_name: Optional[str] = None
    thread_name_pattern: Optional[str] = None
    auto_create_projects: Optional[bool] = None
    report_config: Optional[dict[str, Any]] = None
    default_kpis: Optional[dict[str, Any]] = None
    ai_config: Optional[dict[str, Any]] = None


class ChannelWithThreads(BaseModel):
    channel_id: int
    channel_name: str
    thread_count: int
    sample_threads: List[str]


class DetectedRole(BaseModel):
    role_id: int
    role_name: str
    role_type: str  # "stakeholder" or "team"


class AnalysisResult(BaseModel):
    success: bool
    channels_with_threads: List[ChannelWithThreads]
    recommended_channel: Optional[ChannelWithThreads]
    detected_pattern: Optional[str]
    detected_roles: List[DetectedRole]
    config_applied: bool
    message: str


# Thread naming pattern detection
THREAD_PATTERNS = [
    (r"^(.+?)\s*\((.+?)\)$", "{member} ({project})"),
    (r"^(.+?)\s*-\s*(.+?)$", "{project} - {member}"),
    (r"^(.+?)$", "{project}"),
]

# Role detection keywords
STAKEHOLDER_KEYWORDS = [
    "stakeholder", "client", "owner", "manager", "lead", "director",
    "exec", "ceo", "cto", "cfo", "coo", "founder", "co-founder", "cofounder",
    "president", "vp", "vice president", "head", "chief", "principal",
    "investor", "board", "advisor", "supervisor", "boss", "admin", "administrator",
    "moderator", "mod", "staff", "management", "leadership", "senior"
]

TEAM_KEYWORDS = [
    "dev", "devs", "developer", "engineer", "engineering", "programmer", "coder",
    "frontend", "backend", "fullstack", "full-stack", "software", "swe",
    "designer", "ui", "ux", "graphic", "creative",
    "qa", "tester", "testing", "quality",
    "team", "member", "contributor", "intern", "junior", "mid", "associate",
    "analyst", "specialist", "technician", "support", "ops", "devops", "sre",
    "data", "ml", "ai", "scientist", "researcher",
    "writer", "content", "marketing", "community"
]


# ============ Project Config Endpoints ============

@router.get("/config")
async def get_project_config(
    tenant_id: TenantID,
    db: DBSession,
) -> Optional[ProjectConfigResponse]:
    """Get project configuration for a tenant."""
    result = await db.execute(
        select(TenantProjectConfig).where(TenantProjectConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        return None

    return ProjectConfigResponse(
        id=config.id,
        task_channel_id=config.task_channel_id,
        task_channel_name=config.task_channel_name,
        thread_name_pattern=config.thread_name_pattern,
        auto_create_projects=config.auto_create_projects,
        report_config=config.report_config,
        default_kpis=config.default_kpis,
        ai_config=config.ai_config,
    )


@router.put("/config")
async def update_project_config(
    tenant_id: TenantID,
    request: UpdateProjectConfigRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ProjectConfigResponse:
    """Update or create project configuration for a tenant."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(TenantProjectConfig).where(TenantProjectConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create new config
        config = TenantProjectConfig(tenant_id=tenant_id)
        db.add(config)

    # Update fields
    if request.task_channel_id is not None:
        config.task_channel_id = request.task_channel_id
    if request.task_channel_name is not None:
        config.task_channel_name = request.task_channel_name
    if request.thread_name_pattern is not None:
        config.thread_name_pattern = request.thread_name_pattern
    if request.auto_create_projects is not None:
        config.auto_create_projects = request.auto_create_projects
    if request.report_config is not None:
        config.report_config = request.report_config
    if request.default_kpis is not None:
        config.default_kpis = request.default_kpis
    if request.ai_config is not None:
        config.ai_config = request.ai_config

    await db.flush()

    logger.info("Project config updated", tenant_id=tenant_id)

    return ProjectConfigResponse(
        id=config.id,
        task_channel_id=config.task_channel_id,
        task_channel_name=config.task_channel_name,
        thread_name_pattern=config.thread_name_pattern,
        auto_create_projects=config.auto_create_projects,
        report_config=config.report_config,
        default_kpis=config.default_kpis,
        ai_config=config.ai_config,
    )


@router.post("/analyze")
async def analyze_and_configure(
    tenant_id: TenantID,
    membership: TenantMembership,
    db: DBSession,
) -> AnalysisResult:
    """Analyze Discord server and auto-configure project tracking."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Get the Discord bot
    from eldenops.integrations.discord.state import get_bot
    bot = get_bot()

    if not bot or not bot.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord bot is not connected. Please try again in a moment.",
        )

    # Get tenant to find the guild
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Get the guild from Discord
    guild = bot.get_guild(tenant.discord_guild_id)
    if not guild:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord server not found. Make sure the bot is in the server.",
        )

    # Analyze channels and threads
    channels_with_threads: List[ChannelWithThreads] = []
    all_thread_names: List[str] = []

    for channel in guild.text_channels:
        threads = list(channel.threads)

        # Also check archived threads
        try:
            async for thread in channel.archived_threads(limit=50):
                threads.append(thread)
        except discord.Forbidden:
            pass

        if threads:
            thread_names = [t.name for t in threads[:10]]
            all_thread_names.extend(thread_names)

            channels_with_threads.append(ChannelWithThreads(
                channel_id=channel.id,
                channel_name=channel.name,
                thread_count=len(threads),
                sample_threads=thread_names[:5],
            ))

    # Find best task channel (prioritize channels with "task", "delegation", "project" in name)
    def channel_score(ch: ChannelWithThreads) -> int:
        score = ch.thread_count
        name_lower = ch.channel_name.lower()
        if "task" in name_lower or "delegation" in name_lower:
            score += 100
        if "project" in name_lower:
            score += 50
        return score

    channels_with_threads.sort(key=channel_score, reverse=True)
    recommended_channel = channels_with_threads[0] if channels_with_threads else None

    # Detect thread naming pattern
    detected_pattern = None
    if all_thread_names:
        pattern_scores: dict[str, int] = {}
        for thread_name in all_thread_names[:20]:
            for regex, pattern in THREAD_PATTERNS:
                if re.match(regex, thread_name):
                    pattern_scores[pattern] = pattern_scores.get(pattern, 0) + 1
                    break

        if pattern_scores:
            detected_pattern = max(pattern_scores, key=pattern_scores.get)

    # Analyze roles
    detected_roles: List[DetectedRole] = []
    stakeholder_role_ids: List[int] = []
    team_role_ids: List[int] = []

    for role in guild.roles:
        role_name_lower = role.name.lower()
        if any(kw in role_name_lower for kw in STAKEHOLDER_KEYWORDS):
            detected_roles.append(DetectedRole(
                role_id=role.id,
                role_name=role.name,
                role_type="stakeholder",
            ))
            stakeholder_role_ids.append(role.id)
        elif any(kw in role_name_lower for kw in TEAM_KEYWORDS):
            detected_roles.append(DetectedRole(
                role_id=role.id,
                role_name=role.name,
                role_type="team",
            ))
            team_role_ids.append(role.id)

    # Auto-configure if we have enough info
    config_applied = False
    message = ""

    if recommended_channel and detected_pattern:
        # Get or create config
        config_result = await db.execute(
            select(TenantProjectConfig).where(TenantProjectConfig.tenant_id == tenant_id)
        )
        config = config_result.scalar_one_or_none()

        if not config:
            config = TenantProjectConfig(tenant_id=tenant_id)
            db.add(config)

        # Update config
        config.task_channel_id = recommended_channel.channel_id
        config.task_channel_name = recommended_channel.channel_name
        config.thread_name_pattern = detected_pattern
        config.auto_create_projects = True

        # Configure role-based reports
        config.report_config = {
            "stakeholder_roles": stakeholder_role_ids,
            "team_roles": team_role_ids,
            "stakeholder_reports": {
                "types": ["weekly_summary", "monthly_summary", "project_status"],
                "metrics": ["completion_rate", "blockers", "milestones", "budget_status"],
                "detail_level": "high_level",
            },
            "team_reports": {
                "types": ["daily_standup", "sprint_review", "individual_metrics"],
                "metrics": ["commits", "prs", "code_reviews", "messages", "voice_time"],
                "detail_level": "detailed",
            },
        }

        config.ai_config = {
            "analyze_frequency": "daily",
            "suggestion_types": ["blockers", "next_steps", "risks", "kudos"],
            "context_window_days": 30,
            "personalize_by_role": True,
        }

        await db.flush()
        config_applied = True

        logger.info(
            "Auto-configured project settings via API",
            tenant_id=tenant_id,
            channel=recommended_channel.channel_name,
            pattern=detected_pattern,
            stakeholder_roles=len(stakeholder_role_ids),
            team_roles=len(team_role_ids),
        )

        message = f"Configuration applied! Task channel: #{recommended_channel.channel_name}, Pattern: {detected_pattern}"
    else:
        if not channels_with_threads:
            message = "No channels with threads found. Create a task-delegation channel with threads first."
        elif not detected_pattern:
            message = "Could not detect thread naming pattern. Please configure manually."
        else:
            message = "Partial analysis complete. Some manual configuration may be needed."

    return AnalysisResult(
        success=config_applied,
        channels_with_threads=channels_with_threads[:10],
        recommended_channel=recommended_channel,
        detected_pattern=detected_pattern,
        detected_roles=detected_roles[:20],
        config_applied=config_applied,
        message=message,
    )


# ============ Project Endpoints ============

@router.get("")
async def list_projects(
    tenant_id: TenantID,
    db: DBSession,
    status_filter: Optional[str] = None,
) -> List[ProjectResponse]:
    """List all projects for a tenant."""
    query = (
        select(Project)
        .where(Project.tenant_id == tenant_id)
        .options(
            selectinload(Project.members).selectinload(ProjectMember.user),
            selectinload(Project.github_links).selectinload(ProjectGitHubLink.github_connection),
        )
    )

    if status_filter:
        query = query.where(Project.status == status_filter)

    result = await db.execute(query)
    projects = result.scalars().all()

    return [_project_to_response(p) for p in projects]


@router.post("")
async def create_project(
    tenant_id: TenantID,
    request: CreateProjectRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ProjectResponse:
    """Create a new project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    project = Project(
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        discord_thread_id=request.discord_thread_id,
        discord_thread_name=request.discord_thread_name,
        objectives=request.objectives,
    )

    if request.start_date:
        project.start_date = datetime.fromisoformat(request.start_date)
    if request.target_launch_date:
        project.target_launch_date = datetime.fromisoformat(request.target_launch_date)

    db.add(project)
    await db.flush()

    logger.info("Project created", tenant_id=tenant_id, project_id=project.id, name=project.name)

    return _project_to_response(project)


@router.get("/{project_id}")
async def get_project(
    tenant_id: TenantID,
    project_id: str,
    db: DBSession,
) -> ProjectResponse:
    """Get a project by ID."""
    result = await db.execute(
        select(Project)
        .where(Project.tenant_id == tenant_id, Project.id == project_id)
        .options(
            selectinload(Project.members).selectinload(ProjectMember.user),
            selectinload(Project.github_links).selectinload(ProjectGitHubLink.github_connection),
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return _project_to_response(project)


@router.patch("/{project_id}")
async def update_project(
    tenant_id: TenantID,
    project_id: str,
    request: UpdateProjectRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ProjectResponse:
    """Update a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(Project)
        .where(Project.tenant_id == tenant_id, Project.id == project_id)
        .options(
            selectinload(Project.members).selectinload(ProjectMember.user),
            selectinload(Project.github_links).selectinload(ProjectGitHubLink.github_connection),
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Update fields
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.status is not None:
        project.status = request.status
    if request.discord_thread_id is not None:
        project.discord_thread_id = request.discord_thread_id
    if request.discord_thread_name is not None:
        project.discord_thread_name = request.discord_thread_name
    if request.start_date is not None:
        project.start_date = datetime.fromisoformat(request.start_date)
    if request.target_launch_date is not None:
        project.target_launch_date = datetime.fromisoformat(request.target_launch_date)
    if request.objectives is not None:
        project.objectives = request.objectives
    if request.kpi_config is not None:
        project.kpi_config = request.kpi_config
    if request.launch_checklist is not None:
        project.launch_checklist = request.launch_checklist

    await db.flush()

    logger.info("Project updated", tenant_id=tenant_id, project_id=project_id)

    return _project_to_response(project)


@router.delete("/{project_id}")
async def delete_project(
    tenant_id: TenantID,
    project_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Delete a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(Project).where(Project.tenant_id == tenant_id, Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.delete(project)

    logger.info("Project deleted", tenant_id=tenant_id, project_id=project_id)

    return {"message": "Project deleted"}


# ============ Project Members Endpoints ============

@router.post("/{project_id}/members")
async def add_project_member(
    tenant_id: TenantID,
    project_id: str,
    request: AddProjectMemberRequest,
    membership: TenantMembership,
    current_user: CurrentUser,
    db: DBSession,
) -> ProjectMemberResponse:
    """Add a member to a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.tenant_id == tenant_id, Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if already a member
    existing_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == request.user_id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    member = ProjectMember(
        project_id=project_id,
        user_id=request.user_id,
        role=request.role,
        responsibilities=request.responsibilities,
        assigned_by=current_user.get("user_id"),
    )
    db.add(member)
    await db.flush()

    logger.info("Project member added", project_id=project_id, user_id=request.user_id)

    return ProjectMemberResponse(
        id=member.id,
        user_id=member.user_id,
        discord_username=user.discord_username,
        github_username=user.github_username,
        role=member.role,
        responsibilities=member.responsibilities,
        assigned_at=member.assigned_at.isoformat(),
        is_active=member.is_active,
    )


@router.patch("/{project_id}/members/{member_id}")
async def update_project_member(
    tenant_id: TenantID,
    project_id: str,
    member_id: str,
    request: UpdateProjectMemberRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ProjectMemberResponse:
    """Update a project member."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.id == member_id, ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if request.role is not None:
        member.role = request.role
    if request.responsibilities is not None:
        member.responsibilities = request.responsibilities
    if request.is_active is not None:
        member.is_active = request.is_active

    await db.flush()

    return ProjectMemberResponse(
        id=member.id,
        user_id=member.user_id,
        discord_username=member.user.discord_username,
        github_username=member.user.github_username,
        role=member.role,
        responsibilities=member.responsibilities,
        assigned_at=member.assigned_at.isoformat(),
        is_active=member.is_active,
    )


@router.delete("/{project_id}/members/{member_id}")
async def remove_project_member(
    tenant_id: TenantID,
    project_id: str,
    member_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Remove a member from a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id, ProjectMember.project_id == project_id
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(member)

    logger.info("Project member removed", project_id=project_id, member_id=member_id)

    return {"message": "Member removed"}


# ============ Project GitHub Links Endpoints ============

@router.post("/{project_id}/github")
async def link_github_repo(
    tenant_id: TenantID,
    project_id: str,
    request: LinkGitHubRepoRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ProjectGitHubLinkResponse:
    """Link a GitHub repository to a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.tenant_id == tenant_id, Project.id == project_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Verify GitHub connection exists
    conn_result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.id == request.github_connection_id,
        )
    )
    github_conn = conn_result.scalar_one_or_none()
    if not github_conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub connection not found")

    # Check if already linked
    existing_result = await db.execute(
        select(ProjectGitHubLink).where(
            ProjectGitHubLink.project_id == project_id,
            ProjectGitHubLink.github_connection_id == request.github_connection_id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Repository already linked")

    link = ProjectGitHubLink(
        project_id=project_id,
        github_connection_id=request.github_connection_id,
        branch_filter=request.branch_filter,
        is_primary=request.is_primary,
    )
    db.add(link)
    await db.flush()

    logger.info("GitHub repo linked to project", project_id=project_id, repo=github_conn.repo_full_name)

    return ProjectGitHubLinkResponse(
        id=link.id,
        github_connection_id=link.github_connection_id,
        repo_full_name=github_conn.repo_full_name,
        branch_filter=link.branch_filter,
        is_primary=link.is_primary,
    )


@router.delete("/{project_id}/github/{link_id}")
async def unlink_github_repo(
    tenant_id: TenantID,
    project_id: str,
    link_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Unlink a GitHub repository from a project."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(ProjectGitHubLink).where(
            ProjectGitHubLink.id == link_id, ProjectGitHubLink.project_id == project_id
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    await db.delete(link)

    logger.info("GitHub repo unlinked from project", project_id=project_id, link_id=link_id)

    return {"message": "Repository unlinked"}


# ============ Team Members Endpoints ============

@router.get("/team/members")
async def list_team_members(
    tenant_id: TenantID,
    db: DBSession,
) -> List[TeamMemberResponse]:
    """List all team members for a tenant with their mappings."""
    from eldenops.db.models.tenant import TenantMember

    result = await db.execute(
        select(TenantMember)
        .where(TenantMember.tenant_id == tenant_id)
        .options(
            selectinload(TenantMember.user).selectinload(User.github_identities),
            selectinload(TenantMember.user).selectinload(User.project_assignments),
        )
    )
    members = result.scalars().all()

    return [
        TeamMemberResponse(
            id=m.user.id,
            discord_id=m.user.discord_id,
            discord_username=m.user.discord_username,
            github_username=m.user.github_username,
            email=m.user.email,
            github_identities=[
                GitHubIdentityResponse(
                    id=gi.id,
                    user_id=gi.user_id,
                    committer_email=gi.committer_email,
                    committer_name=gi.committer_name,
                    is_verified=gi.is_verified,
                )
                for gi in m.user.github_identities
            ],
            project_count=len(m.user.project_assignments),
            is_active=m.user.is_active,
        )
        for m in members
    ]


@router.post("/team/github-identities")
async def add_github_identity(
    tenant_id: TenantID,
    request: AddGitHubIdentityRequest,
    membership: TenantMembership,
    db: DBSession,
) -> GitHubIdentityResponse:
    """Add a GitHub committer identity mapping for a user."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if identity already exists
    existing_result = await db.execute(
        select(GitHubIdentity).where(
            GitHubIdentity.tenant_id == tenant_id,
            GitHubIdentity.committer_email == request.committer_email,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Identity already mapped")

    identity = GitHubIdentity(
        tenant_id=tenant_id,
        user_id=request.user_id,
        committer_email=request.committer_email,
        committer_name=request.committer_name,
        is_verified=True,
    )
    db.add(identity)
    await db.flush()

    logger.info("GitHub identity added", user_id=request.user_id, email=request.committer_email)

    return GitHubIdentityResponse(
        id=identity.id,
        user_id=identity.user_id,
        committer_email=identity.committer_email,
        committer_name=identity.committer_name,
        is_verified=identity.is_verified,
    )


@router.delete("/team/github-identities/{identity_id}")
async def remove_github_identity(
    tenant_id: TenantID,
    identity_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Remove a GitHub committer identity mapping."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(GitHubIdentity).where(
            GitHubIdentity.tenant_id == tenant_id, GitHubIdentity.id == identity_id
        )
    )
    identity = result.scalar_one_or_none()

    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")

    await db.delete(identity)

    logger.info("GitHub identity removed", identity_id=identity_id)

    return {"message": "Identity removed"}


# ============ Helper Functions ============

def _project_to_response(project: Project) -> ProjectResponse:
    """Convert a Project model to response schema."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        discord_thread_id=project.discord_thread_id,
        discord_thread_name=project.discord_thread_name,
        start_date=project.start_date.isoformat() if project.start_date else None,
        target_launch_date=project.target_launch_date.isoformat() if project.target_launch_date else None,
        objectives=project.objectives,
        kpi_config=project.kpi_config,
        launch_checklist=project.launch_checklist,
        members=[
            ProjectMemberResponse(
                id=m.id,
                user_id=m.user_id,
                discord_username=m.user.discord_username if m.user else None,
                github_username=m.user.github_username if m.user else None,
                role=m.role,
                responsibilities=m.responsibilities,
                assigned_at=m.assigned_at.isoformat(),
                is_active=m.is_active,
            )
            for m in project.members
        ],
        github_links=[
            ProjectGitHubLinkResponse(
                id=gl.id,
                github_connection_id=gl.github_connection_id,
                repo_full_name=gl.github_connection.repo_full_name if gl.github_connection else "",
                branch_filter=gl.branch_filter,
                is_primary=gl.is_primary,
            )
            for gl in project.github_links
        ],
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )
