"""Validate correlation headers and record one event per completed request."""

from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpRequest, HttpResponse

from apps.common.observability import event, log_context


class RequestLoggingMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.is_async = iscoroutinefunction(get_response)
        if self.is_async:
            markcoroutinefunction(self)

    @staticmethod
    def identifiers(request: HttpRequest) -> tuple[str, str]:
        def valid(value: str | None) -> str:
            return (
                value if value and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) else uuid4().hex
            )

        request_id = valid(request.headers.get("x-request-id"))
        return request_id, valid(request.headers.get("x-trace-id", request_id))

    @staticmethod
    def finish(
        request: HttpRequest,
        response: HttpResponse,
        started: float,
        request_id: str,
        trace_id: str,
    ) -> HttpResponse:
        response["x-request-id"] = request_id
        response["x-trace-id"] = trace_id
        level = (
            logging.ERROR
            if response.status_code >= 500
            else logging.WARNING
            if response.status_code >= 400
            else logging.INFO
        )
        event(
            "api.request.completed",
            route=request.resolver_match.route if request.resolver_match else "unmatched",
            method=request.method,
            status=response.status_code,
            duration_ms=round((time.monotonic() - started) * 1000),
            level=level,
        )
        return response

    def __call__(self, request: HttpRequest):
        if self.is_async:
            return self.async_call(request)
        request_id, trace_id = self.identifiers(request)
        with log_context(request_id=request_id, trace_id=trace_id):
            started = time.monotonic()
            return self.finish(request, self.get_response(request), started, request_id, trace_id)

    async def async_call(self, request: HttpRequest):
        request_id, trace_id = self.identifiers(request)
        with log_context(request_id=request_id, trace_id=trace_id):
            started = time.monotonic()
            return self.finish(
                request, await self.get_response(request), started, request_id, trace_id
            )
