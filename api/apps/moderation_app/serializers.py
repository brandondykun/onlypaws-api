"""
Serializers for the moderation app.
"""
from rest_framework import serializers
from apps.moderation_app.models import ReportReason, PostReport


class ReportReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReason
        fields = ["id", "name", "description"]


class PostReportPreviewSerializer(serializers.ModelSerializer):

    reason = ReportReasonSerializer()

    class Meta:
        model = PostReport
        fields = ["id", "reason", "status"]


class CreatePostReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReport
        fields = ["post", "reason", "details"]

    def validate(self, data):
        # Check if user has already reported this post
        request = self.context.get("request")
        current_profile = request.current_profile
        if PostReport.objects.filter(
            post=data["post"], reporter=current_profile
        ).exists():
            raise serializers.ValidationError("You have already reported this post.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["reporter"] = request.current_profile
        return super().create(validated_data)


class PostReportDetailSerializer(serializers.ModelSerializer):
    reason = ReportReasonSerializer()
    reporter = serializers.StringRelatedField()

    class Meta:
        model = PostReport
        fields = [
            "id",
            "post",
            "reporter",
            "reason",
            "details",
            "status",
            "created_at",
            "resolution_note",
        ]

