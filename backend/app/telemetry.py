"""
OpenTelemetry distributed tracing setup.

Instruments FastAPI, SQLAlchemy, and httpx automatically.
Exports traces via OTLP gRPC when OTEL_EXPORTER_OTLP_ENDPOINT is set;
falls back to a no-op tracer in development.

Usage in main.py:
    from app.telemetry import setup_telemetry
    setup_telemetry(app)
"""

import logging
import os

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(app: FastAPI, service_name: str = "convoai-api") -> None:
    """Configure OpenTelemetry. Safe no-op when packages are absent."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        logger.info("OpenTelemetry tracing enabled → %s (service: %s)", endpoint, service_name)

    except ImportError as exc:
        logger.warning(
            "OpenTelemetry packages missing (%s) — tracing disabled. "
            "Add opentelemetry-* packages to requirements.txt.", exc
        )
