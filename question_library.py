from typing import Dict, List

QUESTION_LIBRARY: Dict[str, Dict[str, List[str]]] = {
    "interactive_dashboard": {
        "business_objective": [
            "What business decision or action should this dashboard support?",
            "What question should this dashboard help the business answer first?",
        ],
        "scope": [
            "Should this dashboard stay focused on the core KPIs only, or also include drilldowns and supporting views?",
            "For the first version, should this dashboard stay narrow, or include additional breakdowns like {breakdowns}?",
        ],
        "stakeholders": [
            "Who is the primary audience for this dashboard: executives, operations, finance, or analysts?",
            "Who will use this dashboard or make decisions from it?",
        ],
        "data_sources": [
            "What source systems or datasets should this dashboard rely on?",
            "Which data sources are required for this dashboard in the first version?",
        ],
        "frequency": [
            "How often should this dashboard be refreshed or reviewed in practice?",
            "What cadence should this dashboard support: daily, weekly, monthly, or on demand?",
        ],
        "success_criteria": [
            "How will you know this dashboard was delivered successfully in business terms?",
            "What outcome would make this dashboard clearly valuable to the business?",
        ],
    },
    "reporting_output": {
        "business_objective": [
            "What business decision or action should this report support?",
            "What question should this report help the business answer?",
        ],
        "scope": [
            "Should this report stay focused on the core view only, or also include breakdowns like {breakdowns}?",
            "For the first version, should this report stay narrow, or include drilldowns and adjacent views?",
        ],
        "stakeholders": [
            "Who will use this report or make decisions from it?",
            "Who is the primary audience for this report: executives, operations, finance, or analysts?",
        ],
        "data_sources": [
            "What source systems, datasets, or tables should this report rely on?",
            "Which data sources are required for this report in the first version?",
        ],
        "frequency": [
            "How often should this report be refreshed, reviewed, or used in practice?",
            "What cadence should this report support: daily, weekly, monthly, or on demand?",
        ],
        "success_criteria": [
            "How will you know this report was delivered successfully in business terms?",
            "What outcome would make this report clearly valuable to the business?",
        ],
    },
    "structured_extract": {
        "business_objective": [
            "What will this extract or dataset be used for once delivered?",
            "What downstream use case should this extract support first?",
        ],
        "scope": [
            "What should each row in this extract represent, and what core fields need to be included?",
            "For the first version, what is the minimum useful shape of this extract?",
        ],
        "stakeholders": [
            "Who will consume this extract or dataset once it is delivered?",
            "Which users or teams need this extract first?",
        ],
        "data_sources": [
            "Which source tables, systems, or datasets should this extract pull from?",
            "What source data is required for this extract to be usable?",
        ],
        "frequency": [
            "How often should this extract be produced or refreshed?",
            "What delivery cadence should this extract support in practice?",
        ],
        "success_criteria": [
            "How will you know this extract was delivered successfully?",
            "What outcome would make this extract clearly useful to downstream users?",
        ],
    },
    "data_view": {
        "business_objective": [
            "What should this database view enable users or downstream systems to do?",
            "What problem should this view solve once it is available?",
        ],
        "scope": [
            "What should each row in this view represent, and what core columns need to be included?",
            "Should this view stay focused on one subject area, or combine multiple related entities?",
        ],
        "stakeholders": [
            "Who will query or depend on this view once it is created?",
            "Which users or teams are the primary consumers of this view?",
        ],
        "data_sources": [
            "Which source tables or source systems should feed this view?",
            "What source structures need to be combined to build this view correctly?",
        ],
        "frequency": [
            "How often does the underlying data for this view need to refresh?",
            "What update cadence should this view effectively support?",
        ],
        "success_criteria": [
            "How will you know this view is successful once delivered?",
            "What would make this view clearly useful and trusted by consumers?",
        ],
    },
    "data_pipeline": {
        "business_objective": [
            "What business or operational outcome should this pipeline support?",
            "What problem should this data movement solve for the business or downstream teams?",
        ],
        "scope": [
            "What should be included in scope for this pipeline, and what should explicitly stay out of scope?",
            "Should this pipeline cover only the core source-to-target flow, or also include enrichment and validation?",
        ],
        "stakeholders": [
            "Who owns this pipeline, and who depends on its output?",
            "Which teams will consume or rely on this pipeline once it is delivered?",
        ],
        "data_sources": [
            "What source systems and target destinations are in scope for this pipeline?",
            "Which systems should this pipeline connect between in the first version?",
        ],
        "frequency": [
            "What latency or cadence does this pipeline need to support?",
            "Should this pipeline run in batch, near real time, or on demand?",
        ],
        "success_criteria": [
            "How will you measure success for this pipeline: timeliness, quality, reliability, or something else?",
            "What outcome would make this pipeline implementation successful?",
        ],
    },
    "integration_request": {
        "business_objective": [
            "What business or operational outcome should this integration support?",
            "What problem should this integration solve between systems or teams?",
        ],
        "scope": [
            "What systems or flows should this integration cover in the first version?",
            "Should this integration stay narrow to one exchange, or include broader synchronization logic?",
        ],
        "stakeholders": [
            "Who depends on this integration once it is in place?",
            "Which teams or users are affected by this integration first?",
        ],
        "data_sources": [
            "Which systems, endpoints, or feeds need to be connected?",
            "What source and target structures need to be integrated here?",
        ],
        "frequency": [
            "How often should this integration run or exchange data?",
            "Should this integration be event-driven, scheduled, or on demand?",
        ],
        "success_criteria": [
            "How will you know this integration is successful once delivered?",
            "What measurable result would make this integration clearly valuable?",
        ],
    },
    "workflow_automation": {
        "business_objective": [
            "What business outcome or process improvement should this workflow support?",
            "What friction or manual effort should this workflow reduce?",
        ],
        "scope": [
            "What part of the process should this workflow cover in the first version?",
            "Where should this workflow start and stop for the initial release?",
        ],
        "stakeholders": [
            "Who participates in this workflow, and who is affected by it?",
            "Which users or teams should this workflow support first?",
        ],
        "data_sources": [
            "What systems, forms, or data inputs should this workflow rely on?",
            "Which source inputs are required for this workflow to operate?",
        ],
        "frequency": [
            "How often does this workflow happen in practice?",
            "What volume or cadence should this workflow support?",
        ],
        "success_criteria": [
            "How will you know this workflow is successful once delivered?",
            "What measurable improvement should this workflow create?",
        ],
    },
    "analytical_model": {
        "business_objective": [
            "What decision or prediction should this model support?",
            "What analytical outcome should this capability deliver?",
        ],
        "scope": [
            "Should this stay focused on the core model output, or also include supporting views and monitoring?",
            "What is the first meaningful scope for this analytical capability?",
        ],
        "stakeholders": [
            "Who will consume or act on the model output?",
            "Which users or teams need this analytical capability first?",
        ],
        "data_sources": [
            "What data sources or features should this model rely on?",
            "Which systems hold the data needed for this analytical capability?",
        ],
        "frequency": [
            "How often should this model be refreshed, scored, or reviewed?",
            "What cadence does this analytical capability need to support?",
        ],
        "success_criteria": [
            "How will you define success for this model in business terms?",
            "What outcome would make this analytical capability valuable and trustworthy?",
        ],
    },
    "generic_business_request": {
        "business_objective": [
            "What business outcome should this request support?",
            "What decision, action, or improvement should this request enable?",
        ],
        "scope": [
            "What should be included in the first version of this request, and what should stay out of scope?",
            "What is the practical boundary for this request in the first release?",
        ],
        "stakeholders": [
            "Who will use this output or make decisions from it?",
            "Which business users are the primary audience for this request?",
        ],
        "data_sources": [
            "What systems or data inputs should this request rely on?",
            "Which source data is required for this request to be feasible?",
        ],
        "frequency": [
            "How often should this output be refreshed, reviewed, or used?",
            "What cadence should this request support in practice?",
        ],
        "success_criteria": [
            "How will you know this request was delivered successfully?",
            "What business result would make this request clearly successful?",
        ],
    },
}

DEFAULT_BREAKDOWNS = ["product", "segment", "region"]

ARTIFACT_BY_SUBTYPE = {
    "interactive_dashboard": "dashboard",
    "reporting_output": "report",
    "structured_extract": "extract",
    "data_view": "view",
    "data_pipeline": "pipeline",
    "integration_request": "integration",
    "workflow_automation": "workflow",
    "analytical_model": "model",
    "generic_business_request": "solution",
}