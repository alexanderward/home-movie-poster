from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import HttpRequest
from ninja import NinjaAPI

from apps.server.apps.posters.controllers import router
from apps.server.apps.posters.services import ConflictError, DependencyUnavailableError

api = NinjaAPI(title="Frame", version="1.0.0")


@api.exception_handler(PermissionDenied)
def forbidden(request: HttpRequest, error: PermissionDenied):
    return api.create_response(request, {"detail": str(error)}, status=403)


@api.exception_handler(ValueError)
@api.exception_handler(ValidationError)
def invalid(request: HttpRequest, error: Exception):
    if isinstance(error, ValidationError):
        detail = "; ".join(error.messages)
    else:
        detail = str(error)
    return api.create_response(request, {"detail": detail}, status=400)


@api.exception_handler(ObjectDoesNotExist)
def missing(request: HttpRequest, error: ObjectDoesNotExist):
    del error
    return api.create_response(request, {"detail": "Resource not found."}, status=404)


@api.exception_handler(ConflictError)
def conflict(request: HttpRequest, error: ConflictError):
    return api.create_response(request, {"detail": str(error)}, status=409)


@api.exception_handler(DependencyUnavailableError)
def unavailable(request: HttpRequest, error: DependencyUnavailableError):
    return api.create_response(request, {"detail": str(error)}, status=503)


api.add_router("", router)
