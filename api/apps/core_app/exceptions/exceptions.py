import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exception: APIException, context: dict) -> Response:
    response = exception_handler(exception, context)

    if response and response.status_code == status.HTTP_400_BAD_REQUEST:
        logger.warning("Bad Request: %s", context["request"].path)
        setattr(response, "_has_been_logged", True)

    return response
