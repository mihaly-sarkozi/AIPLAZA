from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_processing.adapters.ProcessingStepOutputEnricher import ProcessingStepOutputEnricher
from apps.kb.kb_processing.adapters.KbProcessingFlowRecorder import KbProcessingFlowRecorder
from apps.kb.kb_processing.adapters.ProcessingEventReaderAdapter import ProcessingEventReaderAdapter
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository
from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.kb_processing.service.ProcessingEventService import ProcessingEventService
from apps.kb.kb_processing.service.ProcessingIssueService import ProcessingIssueService
from apps.kb.kb_processing.service.ProcessingMetricsService import ProcessingMetricsService
from apps.kb.kb_processing.service.ProcessingStatusService import ProcessingStatusService


@dataclass(frozen=True)
class ProcessingServices:
    event_repository: ProcessingEventRepository
    issue_repository: ProcessingIssueRepository
    metrics_repository: ProcessingMetricsRepository
    event_service: ProcessingEventService
    issue_service: ProcessingIssueService
    metrics_service: ProcessingMetricsService
    flow_recorder: KbProcessingFlowRecorder
    status_service: ProcessingStatusService
    event_reader: ProcessingEventReaderAdapter
    output_enricher: ProcessingStepOutputEnricher


def build_processing_services(*, session_factory) -> ProcessingServices:
    event_repository = ProcessingEventRepository(session_factory)
    issue_repository = ProcessingIssueRepository(session_factory)
    metrics_repository = ProcessingMetricsRepository(session_factory)
    event_service = ProcessingEventService(event_repository)
    issue_service = ProcessingIssueService(issue_repository)
    metrics_service = ProcessingMetricsService(metrics_repository, issue_repository)
    flow_recorder = KbProcessingFlowRecorder(event_service, issue_service, metrics_service)
    event_reader = ProcessingEventReaderAdapter(event_repository)
    output_enricher = ProcessingStepOutputEnricher(session_factory)
    status_service = ProcessingStatusService(
        metrics_service,
        event_repository,
        issue_repository,
        output_enricher=output_enricher,
    )
    return ProcessingServices(
        event_repository=event_repository,
        issue_repository=issue_repository,
        metrics_repository=metrics_repository,
        event_service=event_service,
        issue_service=issue_service,
        metrics_service=metrics_service,
        flow_recorder=flow_recorder,
        status_service=status_service,
        event_reader=event_reader,
        output_enricher=output_enricher,
    )


__all__ = ["ProcessingServices", "build_processing_services"]
