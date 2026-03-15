from django.http import Http404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import TermsOfService, TermsAcceptance
from .serializers import TermsOfServiceSerializer, AcceptTermsSerializer


class CurrentTermsView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TermsOfServiceSerializer

    @extend_schema(
        summary="Get current terms of service",
        description="Returns the most recent active Terms of Service with acceptance status.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        try:
            return TermsOfService.objects.filter(is_active=True).latest("created_at")
        except TermsOfService.DoesNotExist:
            raise Http404


class AcceptTermsView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AcceptTermsSerializer

    @extend_schema(
        summary="Accept terms of service",
        description="Records the user's acceptance of a specific Terms of Service version.",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        terms_id = serializer.validated_data["terms_id"]

        try:
            terms = TermsOfService.objects.get(id=terms_id, is_active=True)
        except TermsOfService.DoesNotExist:
            return Response(
                {"detail": "Terms of service not found or inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ip_address = request.META.get("HTTP_X_FORWARDED_FOR")
        if ip_address:
            ip_address = ip_address.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        _, created = TermsAcceptance.objects.get_or_create(
            user=request.user,
            terms=terms,
            defaults={"ip_address": ip_address},
        )

        if created:
            return Response(
                {"detail": "Terms accepted successfully."},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"detail": "Terms already accepted."},
            status=status.HTTP_200_OK,
        )
