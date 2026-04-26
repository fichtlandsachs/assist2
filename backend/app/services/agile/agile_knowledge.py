# app/services/agile/agile_knowledge.py
"""
Agile Knowledge Model for HeyKarl Workspace.

Structured, canonical knowledge for Scrum, Kanban, Scrumban and hybrid
delivery models — not as methodology documentation but as actionable
project setup knowledge.

Canonical Entity Types
----------------------
Method               → Scrum, Kanban, Scrumban, Lean
DeliveryModel        → Sprint, Continuous Flow, Release Train
Role                 → Product Owner, Scrum Master, Team, Service Request Manager
Event                → Daily, Planning, Review, Retrospective, Replenishment
Artifact             → Product Backlog, Sprint Backlog, Kanban Board, DoD
FlowRule             → WIP Limit, Service Class, Pull Policy, Cycle Time Target
PlanningElement      → Epic, Story, Task, Bug, Work Item
GovernanceElement    → Definition of Done, Definition of Ready, Review Criteria
TeamPattern          → Cross-Functional, Dedicated Stream, Component Team
ProjectSetupRecommendation → full setup output produced by the engine
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ── Canonical types ───────────────────────────────────────────────────────────

MethodId = Literal["scrum", "kanban", "scrumban", "lean", "iterative"]

CanonicalEntityType = Literal[
    "Method", "DeliveryModel", "Role", "Event", "Artifact",
    "FlowRule", "PlanningElement", "GovernanceElement",
    "TeamPattern", "ProjectSetupRecommendation",
]

HeyKarlMapping = Literal[
    "ProcessStep", "Artifact", "Role", "GovernanceElement",
    "FlowRule", "Capability", "Process", "Event",
]


# ── Base dataclasses ──────────────────────────────────────────────────────────

@dataclass
class AgileEntity:
    id:            str
    name:          str
    canonical_type: CanonicalEntityType
    heykarl_type:  HeyKarlMapping
    description:   str
    source:        str = ""         # "Scrum Guide", "Kanban Method", etc.
    tags:          list[str] = field(default_factory=list)


@dataclass
class AgileRole(AgileEntity):
    responsibilities: list[str] = field(default_factory=list)
    anti_patterns:    list[str] = field(default_factory=list)


@dataclass
class AgileEvent(AgileEntity):
    cadence:       str = ""
    duration_hint: str = ""
    inputs:        list[str] = field(default_factory=list)
    outputs:       list[str] = field(default_factory=list)
    purpose:       str = ""
    anti_patterns: list[str] = field(default_factory=list)


@dataclass
class AgileArtifact(AgileEntity):
    owner:         str = ""
    maintained_by: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)


@dataclass
class AgileFlowRule(AgileEntity):
    applies_to:   list[MethodId] = field(default_factory=list)
    enforcement:  str = "recommended"


@dataclass
class Method:
    id:             MethodId
    name:           str
    tagline:        str
    core_idea:      str
    ideal_contexts: list[str] = field(default_factory=list)
    team_forms:     list[str] = field(default_factory=list)
    roles:          list[str] = field(default_factory=list)
    artifacts:      list[str] = field(default_factory=list)
    events:         list[str] = field(default_factory=list)
    flow_rules:     list[str] = field(default_factory=list)
    governance:     list[str] = field(default_factory=list)
    planning_model: str = ""
    control_logic:  str = ""
    risk_patterns:  list[str] = field(default_factory=list)
    project_types:  list[str] = field(default_factory=list)
    combinations:   list[str] = field(default_factory=list)
    source:         str = ""


# ══════════════════════════════════════════════════════════════════════════════
# SCRUM
# ══════════════════════════════════════════════════════════════════════════════

SCRUM = Method(
    id="scrum",
    name="Scrum",
    tagline="Iterative, time-boxed delivery with dedicated roles and ceremonies",
    source="Scrum Guide 2020",
    core_idea=(
        "Scrum is a lightweight framework that helps teams deliver complex products "
        "incrementally. Work is organised in fixed-length Sprints (1–4 weeks). "
        "The team commits to a Sprint Goal and delivers a potentially shippable Increment "
        "at the end of each Sprint. Inspect & Adapt is the core feedback loop."
    ),
    ideal_contexts=[
        "Product development with evolving requirements",
        "Cross-functional teams of 3–9 people",
        "Deliveries where customer feedback cycles matter",
        "Complex problems where the full scope is not yet known",
        "Initiatives with a clear Product Owner who can prioritise",
    ],
    team_forms=[
        "Cross-functional (design + dev + test in one team)",
        "Self-organising — team decides how to implement",
        "Co-located or well-connected remote teams",
    ],
    roles=["scrum_product_owner", "scrum_master", "scrum_developers"],
    artifacts=["product_backlog", "sprint_backlog", "increment", "definition_of_done"],
    events=["sprint", "sprint_planning", "daily_scrum", "sprint_review", "sprint_retrospective"],
    flow_rules=["sprint_goal_immutability", "velocity_tracking"],
    governance=["definition_of_done", "definition_of_ready", "sprint_review_criteria"],
    planning_model="Sprint-based time boxes (1–4 weeks), Sprint Planning at start",
    control_logic=(
        "Inspect & Adapt at every Sprint boundary. Burndown / velocity as leading "
        "indicators. Product Owner controls backlog priority; team controls how."
    ),
    risk_patterns=[
        "Scrum without a real Product Goal — just tasks disguised as stories",
        "Daily Scrum as a status meeting for management",
        "Sprint scope changed mid-Sprint without Sprint Goal renegotiation",
        "Product Owner unavailable — team makes priority decisions alone",
        "Retrospective without actionable improvement items",
        "Definition of Done as aspiration, not gate",
        "Team larger than 9 → coordination overhead kills effectiveness",
    ],
    project_types=[
        "New product development",
        "Feature development on existing product",
        "Complex R&D with iterative discovery",
        "Internal digital transformation initiatives",
    ],
    combinations=[
        "Kanban board within Sprint for task-level flow visualisation",
        "Scrumban: remove time boxes for teams needing continuous flow",
        "OKR as goal layer above Scrum",
        "Shape Up for discovery phase, Scrum for delivery",
    ],
)


# ── Scrum Roles ───────────────────────────────────────────────────────────────

SCRUM_ROLES: list[AgileRole] = [
    AgileRole(
        id="scrum_product_owner",
        name="Product Owner",
        canonical_type="Role",
        heykarl_type="Role",
        description=(
            "Accountable for maximising product value. Owns and orders the Product Backlog. "
            "Represents stakeholder needs. Is a real decision-maker — not a messenger."
        ),
        source="Scrum Guide 2020",
        responsibilities=[
            "Define and communicate the Product Goal",
            "Create, refine and prioritise Product Backlog items",
            "Make backlog transparent and visible",
            "Accept or reject Sprint output at Sprint Review",
            "Represent stakeholders — not just relay their requests",
        ],
        anti_patterns=[
            "PO acts as a pure requirement relay ('the customer said...')",
            "PO unavailable to the team during Sprint",
            "Multiple people acting as PO without single authority",
            "Backlog has no clear prioritisation logic",
        ],
        tags=["scrum", "product", "backlog", "stakeholder"],
    ),
    AgileRole(
        id="scrum_master",
        name="Scrum Master",
        canonical_type="Role",
        heykarl_type="Role",
        description=(
            "Accountable for Scrum effectiveness. Coaches team and organisation. "
            "Removes impediments. Is a servant leader — not a project manager."
        ),
        source="Scrum Guide 2020",
        responsibilities=[
            "Coach the team on Scrum practices and self-organisation",
            "Facilitate Scrum events efficiently",
            "Remove impediments that block the team",
            "Help the organisation understand agile practices",
            "Shield the team from external interference during Sprint",
        ],
        anti_patterns=[
            "Scrum Master assigns tasks — undermines self-organisation",
            "Scrum Master as admin/secretary who books rooms and takes minutes",
            "No Scrum Master at all ('we're agile, we don't need that role')",
            "Scrum Master also acts as Product Owner or Developer",
        ],
        tags=["scrum", "coaching", "facilitation", "impediment"],
    ),
    AgileRole(
        id="scrum_developers",
        name="Developers (Scrum Team)",
        canonical_type="Role",
        heykarl_type="Role",
        description=(
            "Cross-functional group accountable for delivering a releasable Increment every Sprint. "
            "Self-organising — they decide how to implement the Sprint Backlog."
        ),
        source="Scrum Guide 2020",
        responsibilities=[
            "Create and maintain the Sprint Backlog",
            "Adapt the plan daily toward the Sprint Goal",
            "Hold each other accountable as professionals",
            "Maintain the Definition of Done",
        ],
        anti_patterns=[
            "Team members specialised silos ('I only do backend')",
            "Team does not own quality — testing outsourced",
            "Team does not participate in Sprint Planning meaningfully",
        ],
        tags=["scrum", "development", "cross-functional", "self-organising"],
    ),
]


# ── Scrum Events ──────────────────────────────────────────────────────────────

SCRUM_EVENTS: list[AgileEvent] = [
    AgileEvent(
        id="sprint",
        name="Sprint",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Fixed time box (1–4 weeks) in which the team creates a usable Increment.",
        source="Scrum Guide 2020",
        cadence="Fixed, recurring",
        duration_hint="1–4 weeks (2 weeks most common)",
        inputs=["Product Backlog", "Sprint Goal (from Planning)"],
        outputs=["Increment", "Updated Sprint Backlog"],
        purpose="Create cadence and enable inspect & adapt",
        anti_patterns=[
            "Sprint length changed ad-hoc",
            "Sprint cancelled routinely — signals instability",
            "Unplanned work added without Sprint Goal discussion",
        ],
        tags=["scrum", "time-box", "cadence"],
    ),
    AgileEvent(
        id="sprint_planning",
        name="Sprint Planning",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Team selects work and creates the Sprint Goal and Sprint Backlog.",
        source="Scrum Guide 2020",
        cadence="Start of each Sprint",
        duration_hint="Up to 2h per week of Sprint (4h for 2-week Sprint)",
        inputs=["Product Backlog (refined)", "Team capacity", "Previous velocity"],
        outputs=["Sprint Goal", "Sprint Backlog"],
        purpose="Align on what to deliver and why (Sprint Goal is mandatory)",
        anti_patterns=[
            "Planning without a Sprint Goal — just a list of tasks",
            "Team has no capacity to challenge PO priority",
            "Stories not refined — planning turns into analysis session",
        ],
        tags=["scrum", "planning", "sprint-goal"],
    ),
    AgileEvent(
        id="daily_scrum",
        name="Daily Scrum",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="15-minute daily event for Developers to inspect progress toward Sprint Goal and adapt.",
        source="Scrum Guide 2020",
        cadence="Daily",
        duration_hint="Max 15 minutes",
        inputs=["Sprint Backlog", "Sprint Goal"],
        outputs=["Adapted plan for next 24h"],
        purpose="Inspect & adapt daily — not a status update",
        anti_patterns=[
            "Manager attends and team reports to them",
            "Daily as stand-up status report ('yesterday I did X, today X')",
            "Daily skipped because 'we talk anyway'",
            "Duration expands to 30–60 minutes",
        ],
        tags=["scrum", "daily", "inspect-adapt"],
    ),
    AgileEvent(
        id="sprint_review",
        name="Sprint Review",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Team demonstrates the Increment to stakeholders and collects feedback.",
        source="Scrum Guide 2020",
        cadence="End of each Sprint",
        duration_hint="Up to 1h per week of Sprint",
        inputs=["Increment (Done)", "Product Backlog", "Stakeholder availability"],
        outputs=["Updated Product Backlog", "Stakeholder feedback"],
        purpose="Inspect the product and adapt the backlog based on feedback",
        anti_patterns=[
            "Review is a demo without feedback collection",
            "Only PO and SM attend — no real stakeholders",
            "Items shown are not Done by DoD",
            "Review skipped when Sprint was 'rough'",
        ],
        tags=["scrum", "review", "demo", "feedback"],
    ),
    AgileEvent(
        id="sprint_retrospective",
        name="Sprint Retrospective",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Team reflects on process, collaboration and tools — creates actionable improvement items.",
        source="Scrum Guide 2020",
        cadence="End of each Sprint",
        duration_hint="Up to 45min per week of Sprint",
        inputs=["Team experience", "Previous improvement items"],
        outputs=["Improvement actions (minimum 1 actionable item)"],
        purpose="Continuous improvement of team process and collaboration",
        anti_patterns=[
            "Retrospective without actionable output",
            "Same issues raised every Retro — no follow-through",
            "Retrospective skipped due to time pressure",
            "Blame culture — individuals targeted instead of systemic issues",
        ],
        tags=["scrum", "retrospective", "improvement", "kaizen"],
    ),
]


# ── Scrum Artifacts ───────────────────────────────────────────────────────────

SCRUM_ARTIFACTS: list[AgileArtifact] = [
    AgileArtifact(
        id="product_backlog",
        name="Product Backlog",
        canonical_type="Artifact",
        heykarl_type="Artifact",
        description=(
            "Ordered list of everything needed to improve the product. "
            "Single source of work for the Scrum Team. Owned by Product Owner."
        ),
        source="Scrum Guide 2020",
        owner="Product Owner",
        maintained_by=["Product Owner", "Developers (refinement)"],
        anti_patterns=[
            "Backlog with thousands of items and no prioritisation",
            "Backlog as requirements dump — items never refined",
            "Multiple backlogs for one team",
            "Backlog not visible to all stakeholders",
        ],
        tags=["scrum", "backlog", "requirements", "prioritisation"],
    ),
    AgileArtifact(
        id="sprint_backlog",
        name="Sprint Backlog",
        canonical_type="Artifact",
        heykarl_type="Artifact",
        description="Sprint Goal + selected Product Backlog items + plan for the Sprint.",
        source="Scrum Guide 2020",
        owner="Developers",
        maintained_by=["Developers"],
        anti_patterns=[
            "Sprint Backlog owned by PO or SM — not the team",
            "Items added to Sprint Backlog mid-Sprint without team decision",
            "Sprint Backlog not visible — team works from memory",
        ],
        tags=["scrum", "sprint", "plan"],
    ),
    AgileArtifact(
        id="increment",
        name="Increment",
        canonical_type="Artifact",
        heykarl_type="Artifact",
        description=(
            "Concrete stepping stone toward the Product Goal. "
            "Must meet the Definition of Done. Additive — each Sprint adds to all previous Increments."
        ),
        source="Scrum Guide 2020",
        owner="Developers",
        maintained_by=["Developers"],
        anti_patterns=[
            "Increment not releasable — 'almost done' items presented",
            "Increment without DoD — quality undefined",
        ],
        tags=["scrum", "done", "delivery", "releasable"],
    ),
    AgileArtifact(
        id="definition_of_done",
        name="Definition of Done",
        canonical_type="Artifact",
        heykarl_type="GovernanceElement",
        description=(
            "Formal description of quality requirements that must be met for an Increment to be Done. "
            "Creates shared understanding of quality. Non-negotiable gate."
        ),
        source="Scrum Guide 2020",
        owner="Developers (or organisation if set at org level)",
        maintained_by=["Developers", "Scrum Master"],
        anti_patterns=[
            "DoD as aspiration — not enforced at review",
            "No DoD at all — quality subjective",
            "DoD not updated when quality standards rise",
        ],
        tags=["scrum", "quality", "done", "governance"],
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# KANBAN
# ══════════════════════════════════════════════════════════════════════════════

KANBAN = Method(
    id="kanban",
    name="Kanban",
    tagline="Visualise work, limit WIP, improve flow continuously",
    source="Kanban Method (Anderson 2010) / Kanban Guide for Scrum Teams",
    core_idea=(
        "Kanban is an evolutionary change management method. It starts with what you do now "
        "and incrementally improves flow by making work visible, limiting work-in-progress, "
        "and continuously measuring and improving. No prescribed roles or events."
    ),
    ideal_contexts=[
        "Service and operations teams with unpredictable incoming work",
        "Support teams handling bugs, incidents and maintenance",
        "Teams where work arrives continuously without fixed cadence",
        "Teams that need to balance planned work with urgent requests",
        "Mature teams that want to optimise existing processes",
    ],
    team_forms=[
        "Service teams (support, ops, platform)",
        "Mixed planned/unplanned work environments",
        "Teams without dedicated product ownership",
    ],
    roles=["kanban_service_request_manager", "kanban_service_delivery_manager"],
    artifacts=["kanban_board", "work_item", "service_class", "flow_metrics"],
    events=["kanban_replenishment", "kanban_flow_review", "kanban_retrospective"],
    flow_rules=["wip_limit", "pull_policy", "service_class_policy", "cycle_time_target"],
    governance=["service_level_expectation", "flow_efficiency_target"],
    planning_model="Continuous flow — work pulled when capacity available, no sprints",
    control_logic=(
        "Flow metrics: Cycle Time, Lead Time, Throughput, WIP, Aging Work Items. "
        "Monte Carlo / probabilistic forecasting for delivery dates. "
        "Throughput as primary improvement indicator."
    ),
    risk_patterns=[
        "Kanban board without WIP limits — visual task board only, not Kanban",
        "No explicit pull policy — work pushed instead of pulled",
        "No flow metrics — improvement based on gut feeling",
        "Service classes ignored — everything treated as same priority",
        "Board not reviewed regularly — stale items accumulate",
        "No explicit process policies on the board",
    ],
    project_types=[
        "Operations and support",
        "Platform/infrastructure teams",
        "QA teams",
        "Content or marketing teams with continuous output",
    ],
    combinations=[
        "Scrum for product development + Kanban for bug/support flow",
        "Scrumban: add WIP limits and flow metrics to Scrum",
        "Kanban with OKRs for strategic goal layer",
    ],
)


# ── Kanban Elements ───────────────────────────────────────────────────────────

KANBAN_ROLES: list[AgileRole] = [
    AgileRole(
        id="kanban_service_request_manager",
        name="Service Request Manager",
        canonical_type="Role",
        heykarl_type="Role",
        description=(
            "Manages the demand side — understands customer needs, "
            "filters and prioritises incoming work items."
        ),
        source="Kanban Method",
        responsibilities=[
            "Manage incoming requests and filter by service class",
            "Prioritise replenishment queue",
            "Communicate service expectations to requestors",
        ],
        anti_patterns=["No clear ownership of demand — everyone adds work"],
        tags=["kanban", "demand", "service"],
    ),
    AgileRole(
        id="kanban_service_delivery_manager",
        name="Service Delivery Manager",
        canonical_type="Role",
        heykarl_type="Role",
        description="Manages the supply side — ensures flow, removes blockers, coaches on Kanban.",
        source="Kanban Method",
        responsibilities=[
            "Monitor flow metrics and WIP",
            "Identify and resolve bottlenecks",
            "Facilitate Kanban cadences",
        ],
        anti_patterns=["No one monitors flow — blockers persist unresolved"],
        tags=["kanban", "flow", "delivery"],
    ),
]

KANBAN_ARTIFACTS: list[AgileArtifact] = [
    AgileArtifact(
        id="kanban_board",
        name="Kanban Board",
        canonical_type="Artifact",
        heykarl_type="Artifact",
        description=(
            "Visual representation of the workflow. Columns = process steps. "
            "Cards = work items. WIP limits on columns control flow."
        ),
        source="Kanban Method",
        owner="Team",
        maintained_by=["Team", "Service Delivery Manager"],
        anti_patterns=[
            "Board with no WIP limits — just a visual task list",
            "Board not updated in real time — data stale",
            "Columns don't match real workflow steps",
            "Board with 20+ columns — too granular to manage",
        ],
        tags=["kanban", "board", "visualisation", "flow"],
    ),
    AgileArtifact(
        id="flow_metrics",
        name="Flow Metrics",
        canonical_type="Artifact",
        heykarl_type="GovernanceElement",
        description=(
            "Cycle Time, Lead Time, Throughput, WIP, Flow Efficiency, Aging Work Items. "
            "Quantitative basis for improvement decisions."
        ),
        source="Kanban Guide",
        owner="Team",
        maintained_by=["Service Delivery Manager"],
        anti_patterns=[
            "No metrics tracked — improvement is anecdotal",
            "Only Cycle Time without Throughput — incomplete picture",
        ],
        tags=["kanban", "metrics", "flow", "improvement"],
    ),
]

KANBAN_EVENTS: list[AgileEvent] = [
    AgileEvent(
        id="kanban_replenishment",
        name="Replenishment Meeting",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Regular meeting to pull new work items into the flow based on capacity.",
        source="Kanban Method",
        cadence="Weekly or bi-weekly",
        duration_hint="30–60 min",
        inputs=["Input queue", "Current WIP", "Service class priorities"],
        outputs=["Newly authorised work items pulled to 'In Progress'"],
        purpose="Demand management — controlled pull into the system",
        anti_patterns=["Work added without replenishment meeting — push instead of pull"],
        tags=["kanban", "replenishment", "pull"],
    ),
    AgileEvent(
        id="kanban_flow_review",
        name="Flow Review (Kanban Review)",
        canonical_type="Event",
        heykarl_type="ProcessStep",
        description="Regular review of flow metrics: bottlenecks, aging items, cycle time trends.",
        source="Kanban Method",
        cadence="Weekly",
        duration_hint="30–60 min",
        inputs=["Flow metrics", "Cumulative Flow Diagram", "Aging Work Items"],
        outputs=["Improvement actions", "Policy changes"],
        purpose="Inspect system health and improve flow",
        anti_patterns=["No flow review — problems only noticed when they escalate"],
        tags=["kanban", "metrics", "flow", "review"],
    ),
]

KANBAN_FLOW_RULES: list[AgileFlowRule] = [
    AgileFlowRule(
        id="wip_limit",
        name="WIP Limit",
        canonical_type="FlowRule",
        heykarl_type="FlowRule",
        description=(
            "Maximum number of work items allowed in a given workflow stage. "
            "Reduces multitasking, surfaces bottlenecks, improves cycle time. "
            "Start conservative (1–2x team size) and adjust based on data."
        ),
        source="Kanban Method",
        applies_to=["kanban", "scrumban"],
        enforcement="mandatory",
        tags=["kanban", "wip", "flow", "bottleneck"],
    ),
    AgileFlowRule(
        id="pull_policy",
        name="Pull Policy",
        canonical_type="FlowRule",
        heykarl_type="FlowRule",
        description="Explicit rule for when and how work is pulled from one stage to the next.",
        source="Kanban Method",
        applies_to=["kanban", "scrumban"],
        enforcement="recommended",
        tags=["kanban", "pull", "policy"],
    ),
    AgileFlowRule(
        id="service_class",
        name="Service Class",
        canonical_type="FlowRule",
        heykarl_type="FlowRule",
        description=(
            "Categorisation of work items by urgency and cost-of-delay. "
            "E.g.: Expedite (P0), Fixed Date, Standard, Intangible. "
            "Each class has different queue and WIP handling rules."
        ),
        source="Kanban Method",
        applies_to=["kanban"],
        enforcement="recommended",
        tags=["kanban", "service-class", "prioritisation", "cost-of-delay"],
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# SCRUMBAN
# ══════════════════════════════════════════════════════════════════════════════

SCRUMBAN = Method(
    id="scrumban",
    name="Scrumban",
    tagline="Scrum structure meets Kanban flow — pragmatic hybrid for mixed workloads",
    source="Scrumban (Ladas 2008) / Practical agile hybrid",
    core_idea=(
        "Scrumban takes the role clarity and retrospective rhythm of Scrum "
        "and adds Kanban's flow metrics and WIP limits. "
        "Suitable when teams have both planned product work and continuous service obligations."
    ),
    ideal_contexts=[
        "Product teams with significant support/bug load alongside feature work",
        "Teams transitioning from Scrum to Kanban (or vice versa)",
        "Teams with mixed workloads: planned + unplanned",
        "Mature teams that find Scrum overhead excessive",
    ],
    team_forms=["Mixed product/support teams", "Stable teams evolving their process"],
    roles=["scrum_product_owner", "scrum_master", "scrum_developers"],
    artifacts=["product_backlog", "kanban_board", "definition_of_done", "flow_metrics"],
    events=["sprint_planning", "daily_scrum", "sprint_review", "sprint_retrospective", "kanban_replenishment"],
    flow_rules=["wip_limit", "sprint_capacity_buffer", "service_class"],
    governance=["definition_of_done", "wip_limit_enforcement"],
    planning_model="Sprint cadence for planned work + continuous pull for unplanned work",
    control_logic=(
        "Sprint velocity for planned work. Cycle time + throughput for unplanned flow. "
        "Buffer capacity in Sprint reserved for unplanned items (typically 20–30%)."
    ),
    risk_patterns=[
        "Scrumban as excuse to avoid both Scrum discipline and Kanban rigor",
        "Sprint buffer for unplanned work never enforced — team always overloaded",
        "WIP limits added but Sprint structure removed — loss of review cadence",
        "Two separate processes for planned/unplanned — team split in practice",
    ],
    project_types=[
        "Product with continuous release + support obligations",
        "Platform teams building features AND maintaining infrastructure",
    ],
    combinations=["OKRs above Scrumban for strategic alignment"],
)


# ══════════════════════════════════════════════════════════════════════════════
# LEAN / CONTINUOUS FLOW
# ══════════════════════════════════════════════════════════════════════════════

LEAN = Method(
    id="lean",
    name="Lean / Continuous Flow",
    tagline="Eliminate waste, optimise flow, deliver value continuously",
    source="Lean Thinking (Womack & Jones) / Toyota Production System",
    core_idea=(
        "Lean focuses on maximising customer value while minimising waste. "
        "In knowledge work this means: small batches, short feedback loops, "
        "explicit process, reduced handoffs, and continuous improvement (Kaizen)."
    ),
    ideal_contexts=[
        "Teams optimising existing delivery systems",
        "Operations and DevOps teams",
        "Organisations seeking to reduce lead time and waste",
        "Teams with stable, well-understood processes",
    ],
    team_forms=["Stream-aligned teams", "Platform teams", "DevOps teams"],
    roles=["lean_value_stream_owner"],
    artifacts=["value_stream_map", "kaizen_backlog"],
    events=["kaizen_event", "gemba_walk"],
    flow_rules=["batch_size_reduction", "single_piece_flow", "queue_management"],
    governance=["cycle_time_sla", "waste_identification"],
    planning_model="Pull-based, small batch, continuous delivery",
    control_logic="Lead time, cycle time, waste ratio, value-added vs non-value-added time",
    risk_patterns=[
        "Lean tools applied without cultural change",
        "Value stream mapping as one-off exercise — not continuously updated",
        "Waste identified but not acted upon due to organisational inertia",
    ],
    project_types=["Operations", "DevOps/Platform", "Process improvement"],
    combinations=["Kanban for visualisation", "Scrum for iterative development"],
)


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

METHODS: dict[MethodId, Method] = {
    "scrum":    SCRUM,
    "kanban":   KANBAN,
    "scrumban": SCRUMBAN,
    "lean":     LEAN,
}

ALL_ROLES: dict[str, AgileRole] = {r.id: r for r in SCRUM_ROLES + KANBAN_ROLES}
ALL_EVENTS: dict[str, AgileEvent] = {e.id: e for e in SCRUM_EVENTS + KANBAN_EVENTS}
ALL_ARTIFACTS: dict[str, AgileArtifact] = {a.id: a for a in SCRUM_ARTIFACTS + KANBAN_ARTIFACTS}
ALL_FLOW_RULES: dict[str, AgileFlowRule] = {r.id: r for r in KANBAN_FLOW_RULES}


def get_method(method_id: MethodId) -> Method | None:
    return METHODS.get(method_id)


def get_all_methods() -> list[Method]:
    return list(METHODS.values())


def get_role(role_id: str) -> AgileRole | None:
    return ALL_ROLES.get(role_id)


def get_event(event_id: str) -> AgileEvent | None:
    return ALL_EVENTS.get(event_id)


def get_artifact(artifact_id: str) -> AgileArtifact | None:
    return ALL_ARTIFACTS.get(artifact_id)


def get_roles_for_method(method_id: MethodId) -> list[AgileRole]:
    method = METHODS.get(method_id)
    if not method:
        return []
    return [ALL_ROLES[r] for r in method.roles if r in ALL_ROLES]


def get_events_for_method(method_id: MethodId) -> list[AgileEvent]:
    method = METHODS.get(method_id)
    if not method:
        return []
    return [ALL_EVENTS[e] for e in method.events if e in ALL_EVENTS]


def get_artifacts_for_method(method_id: MethodId) -> list[AgileArtifact]:
    method = METHODS.get(method_id)
    if not method:
        return []
    return [ALL_ARTIFACTS[a] for a in method.artifacts if a in ALL_ARTIFACTS]
