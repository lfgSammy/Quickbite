"""
Small serializers for endpoints that answer with a plain dict rather than a
model.

They exist so /api/docs/ can describe every endpoint. drf-spectacular reads
`serializer_class` off a plain APIView, so declaring one is all a view needs -
no need to move anything to GenericAPIView.
"""

from rest_framework import serializers


class MessageSerializer(serializers.Serializer):
    """A bare confirmation, e.g. {"message": "Cart cleared"}."""

    message = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    """The shape hand-written failures use, e.g. {"error": "Order not found"}."""

    error = serializers.CharField()
