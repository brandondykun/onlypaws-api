from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.user_app.serializers import UserSerializer
from .models import Feedback, FeedbackComment
import json

User = get_user_model()


class UserBasicSerializer(UserSerializer):
    """Basic user serializer for displaying user info in feedback"""

    class Meta(UserSerializer.Meta):
        fields = ["id", "email"]


class FeedbackCommentSerializer(serializers.ModelSerializer):
    author = UserBasicSerializer(read_only=True)

    class Meta:
        model = FeedbackComment
        fields = ["id", "ticket", "content", "author", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    def validate_content(self, value):
        """Validate comment content"""
        if len(value.strip()) < 1:
            raise serializers.ValidationError("Comment content cannot be empty.")
        if len(value) > 2000:
            raise serializers.ValidationError("Comment is too long (max 2000 characters).")
        return value.strip()

    def create(self, validated_data):
        # Set the author to the current user
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class FeedbackSerializer(serializers.ModelSerializer):
    reporter = UserBasicSerializer(read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    comments = FeedbackCommentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            "id",
            "title",
            "description",
            "ticket_type",
            "status",
            "priority",
            "reporter",
            "assignee",
            "created_at",
            "updated_at",
            "app_version",
            "device_info",
            "comments",
            "comments_count",
        ]
        read_only_fields = ["id", "reporter", "created_at", "updated_at"]

    def get_comments_count(self, obj) -> int:
        """Get the total count of comments for this feedback"""
        return obj.comments.count()

    def create(self, validated_data):
        # Set the reporter to the current user
        validated_data["reporter"] = self.context["request"].user
        return super().create(validated_data)


class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating feedback - excludes admin-only fields"""

    class Meta:
        model = Feedback
        fields = ["id", "title", "description", "ticket_type", "app_version", "device_info", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_title(self, value):
        """Validate title length and content"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long.")
        if len(value) > 200:
            raise serializers.ValidationError("Title is too long (max 200 characters).")
        return value.strip()

    def validate_description(self, value):
        """Validate description length"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long.")
        if len(value) > 5000:
            raise serializers.ValidationError("Description is too long (max 5000 characters).")
        return value.strip()

    def validate_app_version(self, value):
        """Validate app version format"""
        if value and len(value) > 20:
            raise serializers.ValidationError("App version is too long (max 20 characters).")
        return value

    def validate_device_info(self, value):
        """Validate device_info structure and size"""
        if not value:
            return value
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("device_info must be a dictionary.")
        
        # Limit JSON size to prevent DoS (1KB limit)
        json_str = json.dumps(value)
        if len(json_str) > 1024:
            raise serializers.ValidationError("device_info is too large (max 1KB).")
        
        # Validate allowed keys to prevent arbitrary data storage
        allowed_keys = {"device_model", "manufacturer", "os_name", "os_version"}
        invalid_keys = set(value.keys()) - allowed_keys
        if invalid_keys:
            raise serializers.ValidationError(
                f"Invalid keys in device_info: {invalid_keys}. "
                f"Allowed keys: {sorted(allowed_keys)}"
            )
        
        # Validate individual field values
        for key, val in value.items():
            if not isinstance(val, (str, int, float, bool, type(None))):
                raise serializers.ValidationError(
                    f"device_info.{key} must be a string, number, boolean, or null."
                )
            if isinstance(val, str) and len(val) > 100:
                raise serializers.ValidationError(
                    f"device_info.{key} is too long (max 100 characters)."
                )
        
        return value

    def create(self, validated_data):
        # Set the reporter to the current user
        validated_data["reporter"] = self.context["request"].user
        return super().create(validated_data)


class FeedbackUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating feedback - allows staff to update status, priority, and assignee"""

    class Meta:
        model = Feedback
        fields = ["status", "priority", "assignee"]

    def validate_assignee(self, value):
        """Ensure assignee is staff member"""
        if value and not value.is_staff:
            raise serializers.ValidationError("Assignee must be a staff member.")
        return value


class FeedbackListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing feedback without comments"""

    reporter = UserBasicSerializer(read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            "id",
            "title",
            "ticket_type",
            "status",
            "priority",
            "reporter",
            "assignee",
            "created_at",
            "updated_at",
            "comments_count",
            "description"
        ]

    def get_comments_count(self, obj) -> int:
        """Get the total count of comments for this feedback"""
        return obj.comments.count()
