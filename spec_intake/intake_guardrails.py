from __future__ import annotations

from .models import (
    ArchitectureSynthesis,
    ConfidenceAssessment,
    ConfidenceFactor,
    ProjectBlueprint,
    QuestionBudget,
    HumanEscalationDecision,
)


READY_FOR_PLANNING = "ready_for_planning"
NEEDS_OPERATOR_REVIEW = "needs_operator_review"
INSUFFICIENT_INPUT = "insufficient_input"

READY_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.55

QUESTION_BUDGET_BY_INPUT_KIND = {
    "formal_pair": 3,
    "roadmap_dossier": 5,
    "multi_artifact_brief": 6,
    "use_case_only": 5,
    "chat_web": 7,
    "unknown": 4,
}

CRITICAL_QUESTION_TOKENS = (
    "rol",
    "permiso",
    "wallet",
    "gas",
    "on-chain",
    "off-chain",
    "offline",
    "autentic",
    "salary",
    "salario",
    "salarios",
    "payroll",
    "impuesto",
    "tax",
    "moneda",
    "compliance",
    "privacy",
    "seguridad",
)


def assess_confidence(
    *,
    blueprint: ProjectBlueprint,
    source_input_kind: str,
    architecture_synthesis: ArchitectureSynthesis,
    traceability_entries: int,
) -> ConfidenceAssessment:
    score = 1.0
    factors: list[ConfidenceFactor] = []

    def penalize(label: str, impact: float, rationale: str) -> None:
        nonlocal score
        score -= impact
        factors.append(
            ConfidenceFactor(
                label=label,
                impact=round(-impact, 2),
                rationale=rationale,
            )
        )

    requirements_count = len(blueprint.requirements)
    epics_count = len(blueprint.roadmap_epics)
    tickets_count = sum(len(epic.tickets) for epic in blueprint.roadmap_epics)
    acceptance_count = len(blueprint.acceptance_items)
    open_questions_count = len(architecture_synthesis.open_questions)

    if requirements_count == 0:
        penalize("requirements_missing", 0.30, "No hay requerimientos parseables.")
    elif requirements_count < 3:
        penalize(
            "requirements_sparse",
            0.10,
            "El paquete tiene muy pocos requerimientos y sigue siendo fragil para planning.",
        )

    if epics_count == 0:
        penalize("roadmap_missing", 0.30, "No hay epics parseables.")
    elif tickets_count == 0:
        penalize("tickets_missing", 0.20, "El roadmap no contiene tickets ejecutables.")
    elif tickets_count < max(2, requirements_count):
        penalize(
            "ticket_density_low",
            0.08,
            "La densidad de tickets es baja respecto a los requerimientos detectados.",
        )

    if source_input_kind in {"use_case_only", "multi_artifact_brief", "chat_web"}:
        if (
            requirements_count <= 1
            and tickets_count <= 1
            and len(architecture_synthesis.technical_contracts) <= 2
        ):
            penalize(
                "evidence_thin",
                0.20,
                "El input sigue siendo demasiado delgado para formalizar un backlog confiable.",
            )
        elif len(blueprint.capabilities) <= 1:
            penalize(
                "capability_signal_thin",
                0.08,
                "Hay muy pocas capacidades detectadas para confiar en el cierre del gap.",
            )

    if any(not epic.tickets for epic in blueprint.roadmap_epics):
        penalize(
            "empty_epic",
            0.08,
            "Hay epics sin tickets parseables y eso introduce huecos de ejecucion.",
        )

    if acceptance_count == 0:
        penalize(
            "acceptance_missing",
            0.06,
            "No hay criterios de aceptacion suficientes para validar el backlog derivado.",
        )

    expected_traceability = requirements_count + tickets_count
    if expected_traceability > 0:
        traceability_ratio = traceability_entries / expected_traceability
        if traceability_ratio < 0.75:
            penalize(
                "traceability_partial",
                0.10,
                "La trazabilidad del input certificado es parcial respecto a requerimientos y tickets.",
            )

    issue_penalty = min(0.25, len(blueprint.issues) * 0.05)
    if issue_penalty > 0:
        penalize(
            "blueprint_issues",
            issue_penalty,
            "Hay issues detectados por el intake que siguen abiertos.",
        )

    open_question_penalty = min(0.15, open_questions_count * 0.02)
    if open_question_penalty > 0:
        penalize(
            "open_questions",
            open_question_penalty,
            "Todavia existen preguntas abiertas no resueltas por el arquitecto.",
        )

    source_penalty = {
        "formal_pair": 0.00,
        "roadmap_dossier": 0.07,
        "multi_artifact_brief": 0.10,
        "use_case_only": 0.15,
        "chat_web": 0.10,
        "unknown": 0.12,
    }.get(source_input_kind, 0.12)
    if source_penalty > 0:
        penalize(
            "non_canonical_input",
            source_penalty,
            "El paquete deriva de input no canonico y depende mas de inferencia.",
        )

    rounded_score = round(max(0.0, min(1.0, score)), 2)
    if rounded_score >= READY_THRESHOLD:
        recommended_status = READY_FOR_PLANNING
    elif rounded_score >= REVIEW_THRESHOLD:
        recommended_status = NEEDS_OPERATOR_REVIEW
    else:
        recommended_status = INSUFFICIENT_INPUT

    return ConfidenceAssessment(
        score=rounded_score,
        ready_threshold=READY_THRESHOLD,
        review_threshold=REVIEW_THRESHOLD,
        recommended_status=recommended_status,
        factors=factors,
    )


def build_question_budget(
    *,
    source_input_kind: str,
    open_questions: list[str],
) -> QuestionBudget:
    max_questions = QUESTION_BUDGET_BY_INPUT_KIND.get(
        source_input_kind,
        QUESTION_BUDGET_BY_INPUT_KIND["unknown"],
    )
    blocking_questions = [
        question
        for question in open_questions
        if _is_critical_question(question)
    ]
    remaining_questions = max(0, max_questions - len(open_questions))
    return QuestionBudget(
        max_questions=max_questions,
        open_questions_count=len(open_questions),
        critical_questions_count=len(blocking_questions),
        remaining_questions=remaining_questions,
        exceeded=len(open_questions) > max_questions,
        blocking_questions=blocking_questions,
    )


def decide_human_escalation(
    *,
    blueprint: ProjectBlueprint,
    source_input_kind: str,
    confidence_assessment: ConfidenceAssessment,
    question_budget: QuestionBudget,
) -> HumanEscalationDecision:
    reasons: list[str] = []

    if source_input_kind != "formal_pair":
        reasons.append("Input derivado desde formato no canonico; requiere aprobacion humana.")
    if blueprint.issues:
        reasons.append("El intake detecto gaps o inconsistencias que siguen abiertas.")
    if question_budget.critical_questions_count > 0:
        reasons.append(
            f"Hay {question_budget.critical_questions_count} preguntas criticas sin resolver."
        )
    if question_budget.exceeded:
        reasons.append(
            f"El paquete excede el question budget ({question_budget.open_questions_count}/{question_budget.max_questions})."
        )
    if confidence_assessment.score < confidence_assessment.ready_threshold:
        reasons.append(
            f"El confidence_score ({confidence_assessment.score:.2f}) esta por debajo del umbral de ready_for_planning."
        )

    if confidence_assessment.recommended_status == INSUFFICIENT_INPUT:
        recommended_action = "collect_more_input"
    elif question_budget.critical_questions_count > 0 or question_budget.exceeded:
        recommended_action = "operator_review"
    elif reasons:
        recommended_action = "operator_review"
    else:
        recommended_action = "proceed_to_planning"

    return HumanEscalationDecision(
        required=bool(reasons),
        recommended_action=recommended_action,
        reasons=reasons,
    )


def determine_certification_status(
    *,
    blueprint: ProjectBlueprint,
    confidence_assessment: ConfidenceAssessment,
    question_budget: QuestionBudget,
    human_escalation: HumanEscalationDecision,
) -> str:
    if not blueprint.requirements or not blueprint.roadmap_epics:
        return INSUFFICIENT_INPUT

    if confidence_assessment.recommended_status == INSUFFICIENT_INPUT:
        return INSUFFICIENT_INPUT

    if (
        question_budget.exceeded
        and question_budget.critical_questions_count > 0
        and confidence_assessment.score < confidence_assessment.review_threshold
    ):
        return INSUFFICIENT_INPUT

    if human_escalation.required:
        return NEEDS_OPERATOR_REVIEW

    return READY_FOR_PLANNING


def _is_critical_question(question: str) -> bool:
    lowered = question.lower()
    return any(token in lowered for token in CRITICAL_QUESTION_TOKENS)
