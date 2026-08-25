import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    DRF only formats exceptions it recognizes (APIException subclasses).
    A genuine bug (an AttributeError, a KeyError, ...) falls straight through
    to Django's default handler, which returns a raw HTML error page - fine
    for a browser app, but the frontend here just displays that HTML verbatim
    to the customer. Catch anything DRF doesn't handle and return JSON instead.
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    logger.exception('Unhandled exception in API view', exc_info=exc)
    return Response(
        {'error': 'Something went wrong on our end. Please try again.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
