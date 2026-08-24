import logging
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


@dataclass
class TracingRuntime:
    provider: TracerProvider | None = None

    def shutdown(self) -> None:
        if self.provider is not None:
            self.provider.shutdown()


def configure_tracing(app, engine, settings) -> TracingRuntime:
    if not settings.otel_enabled or not settings.otel_exporter_otlp_endpoint:
        return TracingRuntime()
    try:
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": settings.release_sha,
                "deployment.environment.name": settings.app_environment,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=settings.otel_exporter_otlp_endpoint.startswith("http://"),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            tracer_provider=provider,
            enable_commenter=False,
        )
        logger.info("OpenTelemetry tracing enabled")
        return TracingRuntime(provider)
    except Exception:  # telemetry must never prevent application startup
        logger.exception("OpenTelemetry setup failed; application continues without tracing")
        return TracingRuntime()
