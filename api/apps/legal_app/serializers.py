from rest_framework import serializers

from .models import TermsOfService, TermsAcceptance


class TermsOfServiceSerializer(serializers.ModelSerializer):
    has_accepted = serializers.SerializerMethodField()
    accepted_at = serializers.SerializerMethodField()

    class Meta:
        model = TermsOfService
        fields = [
            "id",
            "content",
            "version",
            "created_at",
            "has_accepted",
            "accepted_at",
        ]

    def get_has_accepted(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return TermsAcceptance.objects.filter(user=request.user, terms=obj).exists()
        return False

    def get_accepted_at(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            acceptance = TermsAcceptance.objects.filter(
                user=request.user, terms=obj
            ).first()
            if acceptance:
                return acceptance.accepted_at
        return None


class AcceptTermsSerializer(serializers.Serializer):
    terms_id = serializers.IntegerField(required=True)
