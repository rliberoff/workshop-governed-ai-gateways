"""Instrumented chat completion helper shared by every lab.

Each call opens an OpenTelemetry client span that follows the GenAI semantic conventions and propagates
the W3C trace context to the gateway, so the client span, the gateway request and the Foundry call share
one trace. When tracing is not configured, the tracer is a no-op and the helper still works.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from openai import APIConnectionError, APIStatusError, OpenAI
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, Status, StatusCode

from workshop.config import Settings

tracer = trace.get_tracer("workshop.chat")

# Response headers that the gateways use to report budgets and throttling.
GOVERNANCE_HEADERS = (
    "x-tokens-consumed",
    "x-ratelimit-remaining-tokens",
    "x-quota-remaining-tokens",
    "retry-after",
)

# Longest wait between two attempts of a throttled call, whatever retry-after asks for.
MAX_RETRY_WAIT_SECONDS = 60


@dataclass
class ChatResult:
    """Outcome of one chat completion call, successful or not."""

    status_code: int
    text: str
    elapsed_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    trace_id: str | None = None
    attempt_status_codes: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def _governance_headers(headers) -> dict[str, str]:
    return {name: headers[name] for name in GOVERNANCE_HEADERS if name in headers}


def chat(
    client: OpenAI,
    settings: Settings,
    prompt: str,
    *,
    gateway: str,
    system: str | None = None,
    max_completion_tokens: int = 800,
) -> ChatResult:
    """Send one chat completion request and capture status, text, usage and governance headers."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    optional_arguments = {}
    if settings.reasoning_effort:
        optional_arguments["reasoning_effort"] = settings.reasoning_effort

    server = urlparse(str(client.base_url))
    with tracer.start_as_current_span(f"chat {settings.model}", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "azure.ai.openai")
        span.set_attribute("gen_ai.request.model", settings.model)
        span.set_attribute("gen_ai.request.max_tokens", max_completion_tokens)
        span.set_attribute("server.address", server.hostname or "")
        span.set_attribute("workshop.gateway", gateway)

        # traceparent lets API Management and Unity Gateway join the trace started here.
        trace_headers: dict[str, str] = {}
        inject(trace_headers)
        trace_id = f"{span.get_span_context().trace_id:032x}" if span.get_span_context().is_valid else None

        started = time.perf_counter()
        try:
            raw = client.chat.completions.with_raw_response.create(
                model=settings.model,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
                extra_headers=trace_headers,
                **optional_arguments,
            )
        except APIStatusError as error:
            elapsed_ms = (time.perf_counter() - started) * 1000
            span.set_attribute("http.response.status_code", error.status_code)
            span.set_attribute("error.type", str(error.status_code))
            span.set_status(Status(StatusCode.ERROR, f"HTTP {error.status_code}"))
            return ChatResult(
                status_code=error.status_code,
                text=error.response.text,
                elapsed_ms=elapsed_ms,
                headers=_governance_headers(error.response.headers),
                trace_id=trace_id,
            )
        except APIConnectionError as error:
            elapsed_ms = (time.perf_counter() - started) * 1000
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, "connection error"))
            return ChatResult(status_code=0, text=str(error), elapsed_ms=elapsed_ms, trace_id=trace_id)

        elapsed_ms = (time.perf_counter() - started) * 1000
        completion = raw.parse()
        usage = completion.usage
        choice = completion.choices[0] if completion.choices else None

        span.set_attribute("http.response.status_code", raw.status_code)
        span.set_attribute("gen_ai.response.model", completion.model)
        span.set_attribute("gen_ai.response.id", completion.id)
        if choice is not None and choice.finish_reason:
            span.set_attribute("gen_ai.response.finish_reasons", [choice.finish_reason])
        if usage is not None:
            span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)

        return ChatResult(
            status_code=raw.status_code,
            text=(choice.message.content or "") if choice is not None else "",
            elapsed_ms=elapsed_ms,
            input_tokens=usage.prompt_tokens if usage is not None else None,
            output_tokens=usage.completion_tokens if usage is not None else None,
            headers=_governance_headers(raw.headers),
            trace_id=trace_id,
        )


def _retry_wait_seconds(result: ChatResult, attempt: int) -> float:
    """Seconds to wait before retrying a throttled call: retry-after when present, exponential otherwise."""
    try:
        wait = float(result.headers["retry-after"])
    except (KeyError, ValueError):
        wait = 2.0 ** (attempt + 1)
    return min(max(wait, 1.0), MAX_RETRY_WAIT_SECONDS)


def chat_with_retry(
    client: OpenAI,
    settings: Settings,
    prompt: str,
    *,
    gateway: str,
    system: str | None = None,
    attempts: int = 5,
) -> ChatResult:
    """Send one chat completion request and repeat it while a token rate limit answers 429.

    The burst commands call chat() directly so that every 429 is visible. Evaluations and AI red teaming measure
    what the model answers, so they wait out the throttling instead of taking a 429 as a result. Any other status,
    including the 403 of an exhausted token quota, is returned as it is.
    """

    def send() -> ChatResult:
        return chat(client, settings, prompt, gateway=gateway, system=system)

    result = send()
    status_codes = [result.status_code]
    for attempt in range(1, attempts):
        if result.status_code != 429:
            break
        time.sleep(_retry_wait_seconds(result, attempt))
        result = send()
        status_codes.append(result.status_code)
    result.attempt_status_codes = tuple(status_codes)
    return result


def describe(result: ChatResult, *, max_text: int = 300) -> str:
    """One-line, human-readable summary of a chat result for the console (in Spanish, the workshop language)."""
    text = " ".join(result.text.split())
    if len(text) > max_text:
        text = text[:max_text] + "…"
    tokens = ""
    if result.input_tokens is not None:
        tokens = f" | tokens entrada={result.input_tokens} salida={result.output_tokens}"
    headers = "".join(f" | {name}={value}" for name, value in result.headers.items())
    return f"HTTP {result.status_code} | {result.elapsed_ms:.0f} ms{tokens}{headers}\n    {text}"
