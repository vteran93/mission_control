from __future__ import annotations

import re

from .models import (
    AdrBootstrapDecision,
    ArchitectureSynthesis,
    NfrCandidate,
    ProjectBlueprint,
    TechnicalContract,
    TechnologyGuidance,
)


def synthesize_architecture(
    blueprint: ProjectBlueprint,
    *,
    technology_guidance: TechnologyGuidance,
    source_input_kind: str,
) -> ArchitectureSynthesis:
    signals = _detect_signals(blueprint)
    assumptions = _build_assumptions(signals=signals, source_input_kind=source_input_kind)
    open_questions = _build_open_questions(blueprint=blueprint, signals=signals)
    nfr_candidates = _build_nfr_candidates(signals=signals)
    technical_contracts = _build_technical_contracts(signals=signals)
    adr_bootstrap = _build_adr_bootstrap(
        signals=signals,
        technology_guidance=technology_guidance,
        open_questions=open_questions,
    )
    system_context = _build_system_context(signals=signals, technology_guidance=technology_guidance)

    return ArchitectureSynthesis(
        summary=(
            f"Synthesis for {blueprint.project_name}: "
            f"{len(nfr_candidates)} NFR candidates, "
            f"{len(technical_contracts)} technical contracts, "
            f"{len(adr_bootstrap)} ADR seeds."
        ),
        architectural_style=_infer_architectural_style(signals),
        system_context=system_context,
        assumptions=assumptions,
        open_questions=open_questions,
        nfr_candidates=nfr_candidates,
        technical_contracts=technical_contracts,
        adr_bootstrap=adr_bootstrap,
    )


def _collect_haystack(blueprint: ProjectBlueprint) -> str:
    chunks = [
        blueprint.project_name,
        *blueprint.capabilities,
        *(item.title for item in blueprint.requirements),
        *(item.summary for item in blueprint.requirements),
        *(document.title for document in blueprint.source_documents),
        *(section.title for document in blueprint.source_documents for section in document.sections),
        *(section.body for document in blueprint.source_documents for section in document.sections),
    ]
    return "\n".join(part for part in chunks if part).lower()


def _detect_signals(blueprint: ProjectBlueprint) -> dict[str, bool]:
    haystack = _collect_haystack(blueprint)
    return {
        "android": _contains_any(haystack, "android", "play store"),
        "ios": _contains_any(haystack, "ios", "app store", "iphone", "ipad"),
        "desktop": _contains_any(haystack, "desktop", "windows", "linux", "mac", "mac os", "macos"),
        "attendance": _contains_any(haystack, "attendance", "asistencia", "timeclock", "clock in", "clock-in"),
        "tasks": _contains_any(haystack, "task", "tasks", "tarea", "tareas", "worklog"),
        "hr": _contains_any(haystack, "hr", "human resources", "recursos humanos", "employee", "empleado"),
        "payroll": _contains_any(
            haystack,
            "payroll",
            "salary",
            "salario",
            "salarios",
            "nomina",
            "por hora",
            "tarifa por hora",
            "hourly rate",
        ),
        "contracts": _contains_any(haystack, "contract", "contrato", "signature", "firma"),
        "ethereum": _contains_any(haystack, "ethereum", "smart contract", "wallet", "blockchain"),
        "audit": _contains_any(haystack, "audit", "ledger", "evidence", "compliance"),
        "api": _contains_any(haystack, "api", "backend", "service", "servicio", "sync", "sincron"),
    }


def _build_assumptions(*, signals: dict[str, bool], source_input_kind: str) -> list[str]:
    assumptions = [
        (
            "La seleccion tecnologica sigue una politica python-first para backend, "
            "automatizacion y orquestacion, salvo incompatibilidad real con la plataforma objetivo."
        ),
        (
            "Cualquier excepcion a python-first debe documentarse como decision arquitectonica explicita antes de pasar a delivery."
        ),
        (
            "Se asume un backend central como fuente de verdad operativa para identidades, "
            "estado de negocio y trazabilidad."
        ),
    ]
    if signals["contracts"] or signals["payroll"] or signals["hr"]:
        assumptions.append(
            "Se asume autenticacion fuerte y control de permisos por rol antes de habilitar operaciones sensibles."
        )
    if signals["ethereum"]:
        assumptions.append(
            "Se asume que los datos legales y operativos pesados permanecen off-chain, y la cadena se usa para firma, evidencia o settlement puntual."
        )
    if signals["desktop"]:
        assumptions.append(
            "Se asume que los clientes desktop sincronizan con el backend y pueden requerir cola local para tolerar desconexiones temporales."
        )
    if source_input_kind != "formal_pair":
        assumptions.append(
            "Este paquete arquitectonico es derivado de input no canonico y requiere aprobacion del operador antes de pasar a delivery."
        )
    return _dedupe(assumptions)


def _build_open_questions(*, blueprint: ProjectBlueprint, signals: dict[str, bool]) -> list[str]:
    questions = list(blueprint.issues)
    if signals["contracts"] or signals["hr"]:
        questions.append(
            "¿Cual es el modelo exacto de roles y permisos para RRHH, managers, empleados y operadores?"
        )
    if signals["ethereum"]:
        questions.append(
            "¿Que partes del flujo contractual viven on-chain y cuales quedan off-chain por costo, privacidad o cumplimiento?"
        )
        questions.append(
            "¿Quien custodia wallets, gas fees y politicas de firma/revocacion?"
        )
    if signals["desktop"] or signals["attendance"]:
        questions.append(
            "¿La captura de asistencia debe funcionar offline y luego sincronizar, o requiere conexion estricta en tiempo real?"
        )
    if signals["payroll"]:
        questions.append(
            "¿Como se calculan overtime, redondeos, moneda, impuestos y aprobaciones antes de liquidar salarios?"
        )
    if signals["tasks"]:
        questions.append(
            "¿Las tareas se registran solo como timesheets o tambien necesitan workflow, estados y aprobacion?"
        )
    return _dedupe(questions)


def _build_nfr_candidates(*, signals: dict[str, bool]) -> list[NfrCandidate]:
    candidates = [
        NfrCandidate(
            nfr_id="NFR-001",
            category="operability",
            statement=(
                "Todo flujo critico debe emitir eventos estructurados con correlation_id, actor, "
                "timestamp y resultado para diagnostico y soporte."
            ),
            rationale="Permite operar el sistema y reconstruir incidentes sin depender de debugging manual.",
            source_signals=["default"],
        ),
        NfrCandidate(
            nfr_id="NFR-002",
            category="reliability",
            statement=(
                "Las operaciones de escritura y sincronizacion deben ser idempotentes o tolerantes a retry para evitar duplicados."
            ),
            rationale="El producto mezcla integraciones, sincronizacion y posibles reintentos en red inestable.",
            source_signals=["default"],
        ),
    ]
    if signals["hr"] or signals["contracts"] or signals["payroll"]:
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-003",
                category="security",
                statement=(
                    "Las operaciones sensibles deben requerir autenticacion fuerte, autorizacion por rol y registro de evidencia."
                ),
                rationale="RRHH, contratos y payroll manejan datos y acciones de alto impacto.",
                source_signals=_signal_list(signals, "hr", "contracts", "payroll"),
            )
        )
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-004",
                category="privacy",
                statement=(
                    "Los datos personales y salariales deben minimizar exposicion, segmentarse por necesidad de acceso y evitar replicacion innecesaria."
                ),
                rationale="El dominio laboral exige manejo cuidadoso de PII y compensacion.",
                source_signals=_signal_list(signals, "hr", "payroll"),
            )
        )
    if signals["ethereum"] or signals["contracts"] or signals["audit"]:
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-005",
                category="auditability",
                statement=(
                    "Toda firma o aceptacion contractual debe dejar evidencia verificable y trazable entre actor, documento, version y estado de settlement."
                ),
                rationale="Las decisiones legales y on-chain requieren trazabilidad fuerte.",
                source_signals=_signal_list(signals, "ethereum", "contracts", "audit"),
            )
        )
    if signals["desktop"] or signals["android"] or signals["ios"]:
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-006",
                category="portability",
                statement=(
                    "Los clientes deben compartir un contrato de sincronizacion consistente y soportar variaciones de plataforma sin romper el dominio central."
                ),
                rationale="Hay mas de un runtime cliente y el backend debe estabilizar la integracion.",
                source_signals=_signal_list(signals, "desktop", "android", "ios"),
            )
        )
    if signals["attendance"] or signals["tasks"]:
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-007",
                category="data_integrity",
                statement=(
                    "Registros de asistencia, tareas y horas imputadas deben conservar orden temporal, actor origen y estado de aprobacion."
                ),
                rationale="El producto usa horas registradas como insumo operativo y potencialmente salarial.",
                source_signals=_signal_list(signals, "attendance", "tasks"),
            )
        )
    if signals["payroll"]:
        candidates.append(
            NfrCandidate(
                nfr_id="NFR-008",
                category="determinism",
                statement=(
                    "El calculo salarial debe ser reproducible a partir de reglas versionadas, tarifas por individuo y registros aprobados."
                ),
                rationale="El payroll no puede depender de heuristicas no trazables.",
                source_signals=_signal_list(signals, "payroll"),
            )
        )
    return candidates


def _build_technical_contracts(*, signals: dict[str, bool]) -> list[TechnicalContract]:
    contracts = [
        TechnicalContract(
            contract_id="TC-001",
            name="Backend de Dominio y API de Orquestacion",
            boundary="Sistema central",
            summary=(
                "Expone APIs y workflows para identidades, dominios de negocio, sincronizacion de clientes y trazabilidad."
            ),
            responsibilities=[
                "Persistir estado canonico del dominio",
                "Exponer contratos de lectura y escritura estables",
                "Publicar eventos de auditoria y operacion",
            ],
            source_signals=["default"],
        )
    ]
    if signals["hr"] or signals["contracts"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-002",
                name="Servicio de Empleados y Contratos",
                boundary="Dominio laboral",
                summary="Modela empleados, versiones contractuales, estados de firma y artefactos legales relacionados.",
                responsibilities=[
                    "Gestionar lifecycle de empleados",
                    "Versionar contratos y anexos",
                    "Exponer estado de firma y vigencia",
                ],
                source_signals=_signal_list(signals, "hr", "contracts"),
            )
        )
    if signals["attendance"] or signals["desktop"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-003",
                name="Cliente de Asistencia y Sincronizacion",
                boundary="Runtime cliente",
                summary="Captura inicio de labores y eventos locales, y los sincroniza contra el backend con tolerancia a desconexion.",
                responsibilities=[
                    "Registrar inicio y fin de jornada",
                    "Mantener cola local de sincronizacion",
                    "Resolver estados pendientes y confirmados",
                ],
                source_signals=_signal_list(signals, "attendance", "desktop"),
            )
        )
    if signals["tasks"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-004",
                name="Servicio de Tareas y Worklogs",
                boundary="Dominio operativo",
                summary="Gestiona tareas, imputacion de horas, estados y aprobaciones necesarias para downstream operativo o salarial.",
                responsibilities=[
                    "Registrar trabajo por tarea",
                    "Versionar reglas de aprobacion",
                    "Publicar horas aprobadas para payroll",
                ],
                source_signals=_signal_list(signals, "tasks"),
            )
        )
    if signals["payroll"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-005",
                name="Motor de Calculo Salarial",
                boundary="Dominio financiero interno",
                summary="Calcula compensacion a partir de tarifas por individuo, reglas versionadas y horas aprobadas.",
                responsibilities=[
                    "Resolver tarifas por empleado",
                    "Calcular periodos y liquidaciones reproducibles",
                    "Emitir desglose auditable por calculo",
                ],
                source_signals=_signal_list(signals, "payroll"),
            )
        )
    if signals["ethereum"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-006",
                name="Gateway de Firma y Settlement en Ethereum",
                boundary="Integracion externa",
                summary="Encapsula interaccion on-chain para firmas, hashes de documentos y confirmacion de transacciones.",
                responsibilities=[
                    "Traducir contratos internos a transacciones o mensajes firmables",
                    "Gestionar estados pending, confirmed y failed",
                    "Mantener trazabilidad entre documentos y tx hashes",
                ],
                source_signals=_signal_list(signals, "ethereum", "contracts"),
            )
        )
    if signals["hr"] or signals["contracts"] or signals["ethereum"] or signals["payroll"]:
        contracts.append(
            TechnicalContract(
                contract_id="TC-007",
                name="Ledger de Auditoria y Evidencia",
                boundary="Cross-cutting",
                summary="Consolida evidencia operativa y legal para revisiones, debugging y cumplimiento.",
                responsibilities=[
                    "Persistir eventos relevantes de negocio",
                    "Relacionar evidencia con usuarios y artefactos",
                    "Exponer timeline verificable por entidad",
                ],
                source_signals=_signal_list(signals, "hr", "contracts", "ethereum", "payroll"),
            )
        )
    return contracts


def _build_adr_bootstrap(
    *,
    signals: dict[str, bool],
    technology_guidance: TechnologyGuidance,
    open_questions: list[str],
) -> list[AdrBootstrapDecision]:
    decisions = [
        AdrBootstrapDecision(
            adr_id="ADR-001",
            title="Backend y automatizacion python-first con excepciones justificadas",
            status="proposed",
            decision=technology_guidance.selection_policy,
            rationale=(
                "Permite mantener velocidad en backend y automatizacion sin forzar Python en targets donde no encaja como runtime principal."
            ),
            follow_up_questions=[],
        ),
        AdrBootstrapDecision(
            adr_id="ADR-002",
            title="Separar dominio central de adaptadores externos y clientes",
            status="proposed",
            decision=(
                "Mantener el backend canonico desacoplado de runtimes cliente e integraciones externas mediante contratos tecnicos explicitos."
            ),
            rationale="Reduce acoplamiento entre reglas de negocio, UI cliente y proveedores externos.",
            follow_up_questions=[],
        ),
    ]
    if signals["desktop"] or signals["android"] or signals["ios"]:
        decisions.append(
            AdrBootstrapDecision(
                adr_id="ADR-003",
                title="Modelo de sincronizacion para clientes edge",
                status="proposed",
                decision=(
                    "Definir clientes con cola local, confirmacion de entrega y reconciliacion explicita contra el backend."
                ),
                rationale="Los runtimes cliente pueden operar con conectividad parcial o variable.",
                follow_up_questions=[
                    question
                    for question in open_questions
                    if "offline" in question.lower() or "sincron" in question.lower()
                ],
            )
        )
    if signals["ethereum"]:
        decisions.append(
            AdrBootstrapDecision(
                adr_id="ADR-004",
                title="Encapsular blockchain tras un gateway de integracion",
                status="proposed",
                decision=(
                    "Mantener logica on-chain detras de un boundary dedicado para aislar costos, wallets, settlement y reintentos."
                ),
                rationale="Evita filtrar complejidad de Ethereum al dominio principal.",
                follow_up_questions=[
                    question
                    for question in open_questions
                    if "on-chain" in question.lower()
                    or "wallet" in question.lower()
                    or "gas" in question.lower()
                ],
            )
        )
    if signals["hr"] or signals["contracts"] or signals["payroll"]:
        decisions.append(
            AdrBootstrapDecision(
                adr_id="ADR-005",
                title="Evidencia auditable por defecto para operaciones sensibles",
                status="proposed",
                decision=(
                    "Toda accion contractual, laboral o salarial debe producir evidencia persistente y navegable desde una capa transversal."
                ),
                rationale="El dominio necesita trazabilidad fuerte para cumplimiento y soporte.",
                follow_up_questions=[
                    question
                    for question in open_questions
                    if "roles" in question.lower() or "salarios" in question.lower()
                ],
            )
        )
    return decisions


def _build_system_context(*, signals: dict[str, bool], technology_guidance: TechnologyGuidance) -> str:
    clients: list[str] = []
    if signals["desktop"]:
        clients.append("clientes desktop")
    if signals["android"]:
        clients.append("cliente Android")
    if signals["ios"]:
        clients.append("cliente iOS")

    integrations: list[str] = []
    if signals["ethereum"]:
        integrations.append("Ethereum")

    domain_parts = ["backend central"]
    if signals["hr"] or signals["contracts"]:
        domain_parts.append("modulo de empleados y contratos")
    if signals["attendance"]:
        domain_parts.append("captura de asistencia")
    if signals["tasks"]:
        domain_parts.append("registro de tareas y horas")
    if signals["payroll"]:
        domain_parts.append("calculo salarial")

    context = (
        "La arquitectura propuesta se organiza alrededor de "
        + ", ".join(domain_parts)
        + "."
    )
    if clients:
        context += " Los clientes esperados incluyen " + ", ".join(clients) + "."
    if integrations:
        context += " Las integraciones externas iniciales incluyen " + ", ".join(integrations) + "."
    context += " La politica tecnologica base es: " + technology_guidance.selection_policy
    return context


def _infer_architectural_style(signals: dict[str, bool]) -> str:
    if signals["desktop"] or signals["android"] or signals["ios"] or signals["ethereum"]:
        return "modular_platform_with_explicit_adapters"
    return "modular_backend_with_clear_domain_boundaries"


def _contains_any(haystack: str, *terms: str) -> bool:
    return any(re.search(rf"\b{re.escape(term.lower())}\b", haystack) for term in terms)


def _signal_list(signals: dict[str, bool], *names: str) -> list[str]:
    return [name for name in names if signals.get(name)]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item.strip())
    return deduped
