from rest_framework import permissions


class IsStaffOrReadOnlyForReporter(permissions.BasePermission):
    """
    Permission that allows:
    - Staff members to perform any action
    - Regular users (reporters) to only read their own feedback
    """

    def has_permission(self, request, view):
        # Allow authenticated users to access the endpoint
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff can do anything
        if request.user.is_staff:
            return True

        # Regular users can only read their own feedback
        if request.method in permissions.SAFE_METHODS:
            return obj.reporter == request.user

        # No write permissions for regular users on existing feedback
        return False


class IsStaffForComments(permissions.BasePermission):
    """
    Permission for feedback comments:
    - Only staff can create/update/delete comments
    - Regular users can read comments on their own feedback
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Only staff can create comments
        if request.method == "POST":
            return request.user.is_staff

        return True

    def has_object_permission(self, request, view, obj):
        # Staff can do anything with comments
        if request.user.is_staff:
            return True

        # Regular users can only read comments on their own feedback
        if request.method in permissions.SAFE_METHODS:
            return obj.ticket.reporter == request.user

        return False
