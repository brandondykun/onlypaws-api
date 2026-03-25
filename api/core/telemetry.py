"""
OpenTelemetry initialization for Only Paws API.

Instruments Django, psycopg2, Redis, Celery, and logging when
OTEL_EXPORTER_OTLP_ENDPOINT is set. Does nothing otherwise,
so tests and local dev without SigNoz are unaffected.
"""

import os
import logging

_initialized = False

logger = logging.getLogger(__name__)


def init_telemetry():
    global _initialized

    if _initialized:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

    _initialized = True

    service_name = os.environ.get("OTEL_SERVICE_NAME", "onlypaws-api")

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource

    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
        OTLPLogExporter,
    )
    from opentelemetry._logs import set_logger_provider

    resource = Resource.create({"service.name": service_name})

    # --- Traces ---
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True, timeout=30))
    )
    trace.set_tracer_provider(tracer_provider)

    # --- Logs ---
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True, timeout=30))
    )
    set_logger_provider(logger_provider)

    # Attach OTel log handler to root logger so existing logs are exported
    otel_handler = LoggingHandler(
        level=logging.NOTSET, logger_provider=logger_provider
    )
    logging.getLogger().addHandler(otel_handler)

    # Also attach to loggers with propagate=False, since their logs
    # won't reach the root logger's OTel handler otherwise.
    for name in list(logging.root.manager.loggerDict):
        lgr = logging.getLogger(name)
        if not lgr.propagate and lgr.handlers:
            lgr.addHandler(otel_handler)

    # --- Auto-instrumentation ---
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    DjangoInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Suppress noisy retry/failure logs from the gRPC exporter — the
    # BatchSpanProcessor and BatchLogRecordProcessor handle retries silently.
    logging.getLogger("opentelemetry.exporter.otlp.proto.grpc.exporter").setLevel(
        logging.CRITICAL
    )

    logger.info("OpenTelemetry initialized — exporting to %s", endpoint)
