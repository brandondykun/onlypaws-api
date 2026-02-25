"""
Views for the interactions API.
"""

from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
)
import logging

from apps.interactions_app.models import Like, Comment, CommentLike, Follow, FollowRequest
from apps.posts_app.models import Post
from apps.profile_app.models import Profile
from .serializers import (
    LikeSerializer,
    CommentSerializer,
    CommentDetailedSerializer,
    CommentChainSerializer,
    CommentLikeSerializer,
    FollowSerializer,
    CreateFollowSerializer,
    FollowRequestSerializer,
    SentFollowRequestSerializer,
)
from .pagination import (
    FollowListPagination,
    PostCommentsPagination,
    CommentRepliesPagination,
)
from apps.profile_app.serializers import ProfileSerializer
from core.schema_params import auth_profile_param

logger = logging.getLogger(__name__)


# ============================================================================
# Like Views
# ============================================================================

@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
    delete=extend_schema(parameters=[auth_profile_param]),
)
class CreateDestroyLikeView(generics.GenericAPIView):
    """Create or delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def post(self, request, *args, **kwargs):
        """Create a like."""
        post_id = self.kwargs.get("pk", None)
        profile_id = request.data.get("profileId")
        
        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id):
            logger.error(f"Profile {profile_id} does not belong to current authenticated user {current_profile.id}")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # prevent profile from liking own post
        post = get_object_or_404(Post, pk=post_id)
        if post.profile.id == current_profile.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Check if user can interact with this post (private profile check)
        if not post.can_profile_interact(current_profile):
            logger.warning(
                f"Profile {current_profile.id} attempted to like post {post_id} "
                f"from private profile {post.profile.id} without following"
            )
            return Response(
                {"error": "Cannot interact with posts from private profiles you don't follow"},
                status=status.HTTP_403_FORBIDDEN
            )

        new_like_data = {
            "post": post_id,
            "profile": current_profile.id,
        }
        serializer = self.get_serializer(data=new_like_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f"Like created for post {post_id} by profile {current_profile.id}")
        
        return Response(
            serializer.data, status=status.HTTP_201_CREATED
        )

    def delete(self, request, *args, **kwargs):
        """Delete a like."""
        post_id = self.kwargs.get("pk", None)
        current_profile = request.current_profile

        if post_id:
            like = get_object_or_404(Like, profile=current_profile, post=post_id)
            like.delete()
            logger.info(f"Like deleted for post {post_id} by profile {current_profile.id}")
            return Response(status=status.HTTP_204_NO_CONTENT)

        logger.warning(f"Delete like attempt with no post_id by profile {current_profile.id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Comment Views
# ============================================================================

@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateCommentView(generics.CreateAPIView):
    """Create a Comment."""

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def create(self, request, *args, **kwargs):
        post_id = self.kwargs.get("id")
        text = request.data.get("text")
        profile_id = request.data.get("profileId")
        parent_comment = request.data.get("parent_comment")
        reply_to_comment = request.data.get("reply_to_comment")

        # TODO: make sure reply_to_comment is a child comment at some level of parent_comment

        current_profile = request.current_profile

        # ensure that the profile id sent belongs to the current authenticated user profile
        if str(profile_id) != str(current_profile.id):
            logger.warning(
                f"Profile mismatch in comment creation: "
                f"provided {profile_id}, expected {current_profile.id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Check if user can interact with this post (private profile check)
        post = get_object_or_404(Post, pk=post_id)
        if not post.can_profile_interact(current_profile):
            logger.warning(
                f"Profile {current_profile.id} attempted to comment on post {post_id} "
                f"from private profile {post.profile.id} without following"
            )
            return Response(
                {"error": "Cannot interact with posts from private profiles you don't follow"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            serializer = self.get_serializer(
                data={
                    "text": text,
                    "post": post_id,
                    "profile": profile_id,
                    "parent_comment": parent_comment,
                    "reply_to_comment": reply_to_comment,
                },
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            comment = Comment.objects.get(id=serializer.data["id"])

            res_serializer = CommentDetailedSerializer(
                comment, context={"request": request}
            )
            headers = self.get_success_headers(res_serializer.data)
            
            logger.info(
                f"Comment created on post {post_id} by profile {current_profile.id}"
            )
            
            return Response(
                res_serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                f"Error creating comment on post {post_id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "Failed to create comment"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ListPostCommentsView(generics.ListAPIView):
    """List Comments for a Post."""

    serializer_class = CommentDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()
    pagination_class = PostCommentsPagination

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        comments = self.queryset.filter(
            Q(post=post_id) & Q(parent_comment=None)
        ).order_by("-created_at")
        return comments


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListCommentRepliesView(generics.ListAPIView):
    """Get replies to a comment."""

    serializer_class = CommentDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()
    pagination_class = CommentRepliesPagination

    def get_queryset(self):
        comment_id = self.kwargs.get("pk")
        replies = Comment.objects.filter(Q(parent_comment=comment_id)).order_by(
            "created_at"
        )
        return replies


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class CommentChainRetrieveView(generics.GenericAPIView):
    """
    Retrieve a comment with its entire parent comment chain.
    
    This view optimizes database queries by:
    1. Fetching the target comment with select_related for profile and post
    2. Collecting all parent comment IDs in a single traversal using only('parent_comment_id')
    3. Fetching all parent comments in a single query with select_related('profile')
    4. Including circular reference protection to handle data corruption
    
    The response includes the target comment and a parent_chain field containing
    all ancestor comments ordered from root (oldest) to immediate parent.
    
    Endpoint: GET /api/interactions/comment/<pk>/chain/
    """

    serializer_class = CommentChainSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve comment with parent chain.
        
        Query optimization strategy:
        - Query 1: Fetch target comment with profile and post
        - Query 2: Collect parent IDs using only('reply_to_comment_id') - minimal data transfer
        - Query 3: Bulk fetch all parents with select_related('profile')
        
        This results in exactly 3 queries regardless of chain depth.
        """
        comment_id = self.kwargs.get("pk")
        
        # Step 1: Fetch the target comment with related profile and post
        # This is Query #1
        comment = get_object_or_404(
            Comment.objects.select_related("profile", "post"),
            pk=comment_id
        )
        
        # Step 2: Collect all parent comment IDs by traversing up the chain
        # This is Query #2 - uses only() to minimize data transfer
        # NOTE: We traverse via reply_to_comment (immediate parent), not parent_comment (top-level root)
        parent_ids = []
        current_id = comment.reply_to_comment_id
        seen_ids = set([comment.id])  # Circular reference protection
        max_depth = 100  # Safety limit to prevent infinite loops
        depth = 0
        
        while current_id and depth < max_depth:
            if current_id in seen_ids:
                # Circular reference detected - log and break
                logger.warning(
                    f"Circular reference detected in comment chain at comment_id={current_id}"
                )
                break
            
            seen_ids.add(current_id)
            parent_ids.append(current_id)
            
            # Fetch only the reply_to_comment_id field to minimize data transfer
            parent = Comment.objects.filter(id=current_id).only("reply_to_comment_id").first()
            
            if not parent:
                # Parent comment doesn't exist (data inconsistency)
                logger.warning(
                    f"Parent comment {current_id} not found - possible data inconsistency"
                )
                break
            
            current_id = parent.reply_to_comment_id
            depth += 1
        
        # Step 3: Bulk fetch all parent comments in a single query
        # This is Query #3 - fetches all parents with their profiles
        if parent_ids:
            parent_comments = Comment.objects.filter(
                id__in=parent_ids
            ).select_related("profile", "post")
            
            # Create a lookup dictionary for efficient access
            parent_lookup = {p.id: p for p in parent_comments}
            
            # Attach parent comments to the target comment for serializer access
            # This allows the serializer to access prefetched data efficiently
            current = comment
            for parent_id in parent_ids:
                if parent_id in parent_lookup:
                    current.parent_comment = parent_lookup[parent_id]
                    current = current.parent_comment
        
        # Serialize and return the comment with its parent chain
        serializer = self.get_serializer(comment)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# Comment Like Views
# ============================================================================

@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
    delete=extend_schema(parameters=[auth_profile_param]),
)
class CreateDestroyCommentLikeView(generics.GenericAPIView):
    """Create or delete a Comment Like."""

    serializer_class = CommentLikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CommentLike.objects.all()

    def post(self, request, *args, **kwargs):
        """Create a comment like."""
        comment_id = self.kwargs.get("pk")
        profile_id = request.data.get("profileId")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile

        if str(profile_id) != str(current_profile.id):
            logger.warning(
                f"Profile mismatch in comment like creation: "
                f"provided {profile_id}, expected {current_profile.id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get the comment and check if user can interact with the post
            comment = get_object_or_404(Comment, pk=comment_id)
            if not comment.post.can_profile_interact(current_profile):
                logger.warning(
                    f"Profile {current_profile.id} attempted to like comment {comment_id} "
                    f"on a post from private profile {comment.post.profile.id} without following"
                )
                return Response(
                    {"error": "Cannot interact with posts from private profiles you don't follow"},
                    status=status.HTTP_403_FORBIDDEN
                )

            new_like_data = {
                "comment": comment_id,
                "profile": current_profile.id,
            }
            serializer = self.get_serializer(
                data=new_like_data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Comment like created for comment {comment_id} by profile {current_profile.id}")

            return Response(
                serializer.data, status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(
                f"Error creating comment like for comment {comment_id}: {str(e)}"
            )
            return Response(
                {"error": "Failed to like comment"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request, *args, **kwargs):
        """Delete a comment like."""
        comment_id = self.kwargs.get("pk", None)

        current_profile = request.current_profile
        if comment_id:
            try:
                like = get_object_or_404(
                    CommentLike, profile=current_profile, comment=comment_id
                )
                like.delete()
                logger.info(f"Comment like deleted for comment {comment_id} by profile {current_profile.id}")
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error deleting comment like for comment {comment_id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Delete comment like attempt with no comment_id by profile {current_profile.id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Follow Views
# ============================================================================

@extend_schema_view(
    post=extend_schema(
        request=CreateFollowSerializer,
        parameters=[auth_profile_param],
        summary="Create a follow or follow request",
        description="Create a follow for public profiles, or a follow request for private profiles."),
)
class CreateFollowView(generics.CreateAPIView):
    """Create a follow (for public profiles) or a follow request (for private profiles)."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def create(self, request, *args, **kwargs):
        current_profile = request.current_profile
        profile_to_follow_id = request.data.get("profileId")
        profile_to_follow = get_object_or_404(Profile, public_id=profile_to_follow_id)
        
        # profile cannot follow itself
        if profile_to_follow.id == current_profile.id:
            logger.warning(f"Profile {current_profile.id} attempted to follow itself")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Check if already following
        if Follow.objects.filter(
            followed=profile_to_follow,
            followed_by=current_profile
        ).exists():
            logger.warning(
                f"Profile {current_profile.id} already follows {profile_to_follow_id}"
            )
            return Response(
                {"error": "Already following this profile"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if a follow request already exists
        if FollowRequest.objects.filter(
            requester=current_profile,
            target=profile_to_follow
        ).exists():
            logger.warning(
                f"Profile {current_profile.id} already has a pending follow request to {profile_to_follow_id}"
            )
            return Response(
                {"error": "Follow request already pending"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # If target profile is private, create a follow request instead
            if profile_to_follow.is_private:
                follow_request = FollowRequest.objects.create(
                    requester=current_profile,
                    target=profile_to_follow
                )
                
                logger.info(
                    f"Follow request created: profile {current_profile.id} requested to follow {profile_to_follow_id}"
                )
                
                follow_request_serializer = FollowRequestSerializer(follow_request)
                return Response(
                    {
                        "status": "requested",
                        "follow_request": follow_request_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

            # For public profiles, create the follow directly
            new_follow_data = {
                "followed": profile_to_follow.id,
                "followed_by": current_profile.id,
            }
            serializer = self.get_serializer(data=new_follow_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            logger.info(
                f"Follow created: profile {current_profile.id} now follows {profile_to_follow_id}"
            )
            
            return Response(
                {
                    "status": "following",
                    "follow": serializer.data
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            logger.error(
                f"Error creating follow from {current_profile.id} to {profile_to_follow_id}: {str(e)}"
            )
            return Response(
                {"error": "Failed to create follow"},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    delete=extend_schema(
        parameters=[auth_profile_param],
        summary="Delete a follow",
        description="Delete a follow. profile_id is the id of the profile to unfollow."),
)
class DestroyFollowView(generics.DestroyAPIView):
    """Delete a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def destroy(self, request, *args, **kwargs):
        profile_public_id = self.kwargs.get("profile_public_id")  # profile id to unfollow
        current_profile = request.current_profile
        profile_to_unfollow = get_object_or_404(Profile, public_id=profile_public_id)

        if profile_public_id:
            try:
                follow = get_object_or_404(
                    Follow, followed_by=current_profile, followed=profile_to_unfollow.id
                )
                self.perform_destroy(follow)
                logger.info(
                    f"Unfollow: profile {current_profile.id} unfollowed {profile_to_unfollow.id}"
                )
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error unfollowing: profile {current_profile.id} -> {profile_to_unfollow.id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Unfollow attempt with no profile_id by profile {current_profile.id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    delete=extend_schema(
        parameters=[auth_profile_param],
        summary="Remove a follower",
        description="Remove a follower from the current profile. profile_id is the id of the follower to remove."),
)
class RemoveFollowerView(generics.DestroyAPIView):
    """Remove a follower from the current profile."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def destroy(self, request, *args, **kwargs):
        follower_profile_id = self.kwargs.get("profile_id")  # profile id of follower to remove
        current_profile = request.current_profile

        if follower_profile_id:
            try:
                follow = get_object_or_404(
                    Follow, followed=current_profile, followed_by=follower_profile_id
                )
                self.perform_destroy(follow)
                logger.info(
                    f"Remove follower: profile {current_profile.id} removed follower {follower_profile_id}"
                )
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error removing follower: profile {current_profile.id} removing {follower_profile_id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Remove follower attempt with no profile_id by profile {current_profile.id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListFollowersView(generics.ListAPIView):
    """List Profiles that follow a given Profile."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        profile_public_id = self.kwargs.get("public_id", None)
        username = self.request.query_params.get("username", None)

        try:
            profile = Profile.objects.get(public_id=profile_public_id)
            followers_objs = profile.following.all()
            if username:
                followers_objs = followers_objs.filter(
                    Q(followed_by__username__icontains=username)
                )
            sorted_objs = followers_objs.order_by("followed_by__username")
            followers = [obj.followed_by for obj in sorted_objs]
            return followers
        except Profile.DoesNotExist:
            logger.error(f"Profile {profile_public_id} not found when listing followers")
            return []


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListFollowingView(generics.ListAPIView):
    """List Profiles that a given Profile follows."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        profile_public_id = self.kwargs.get("public_id", None)
        username = self.request.query_params.get("username", None)

        try:
            profile = Profile.objects.get(public_id=profile_public_id)
            following_objs = profile.followers.all()
            if username:
                following_objs = following_objs.filter(
                    Q(followed__username__icontains=username)
                )
            sorted_objs = following_objs.order_by("followed__username")
            following = [obj.followed for obj in sorted_objs]
            return following
        except Profile.DoesNotExist:
            logger.error(f"Profile {profile_public_id} not found when listing following")
            return []


# ============================================================================
# Follow Request Views
# ============================================================================

@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListFollowRequestsView(generics.ListAPIView):
    """List pending follow requests received by the current profile."""

    serializer_class = FollowRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FollowRequest.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        current_profile = self.request.current_profile
        return FollowRequest.objects.filter(
            target=current_profile
        ).select_related(
            'requester__image',
            'requester__regularprofile',
            'requester__regularprofile__pet_type',
            'requester__businessprofile',
        ).order_by("-created_at")


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListSentFollowRequestsView(generics.ListAPIView):
    """List pending follow requests sent by the current profile."""

    serializer_class = SentFollowRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FollowRequest.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        current_profile = self.request.current_profile
        return FollowRequest.objects.filter(
            requester=current_profile
        ).select_related(
            'target__image',
            'target__regularprofile',
            'target__regularprofile__pet_type',
            'target__businessprofile',
        ).order_by("-created_at")


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class AcceptFollowRequestView(generics.GenericAPIView):
    """Accept a follow request - creates a Follow and deletes the request."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FollowRequest.objects.all()

    def post(self, request, *args, **kwargs):
        follow_request_id = self.kwargs.get("pk")
        current_profile = request.current_profile

        try:
            follow_request = get_object_or_404(
                FollowRequest,
                pk=follow_request_id,
                target=current_profile
            )

            # Check if follow already exists (shouldn't happen but be safe)
            if Follow.objects.filter(
                followed=current_profile,
                followed_by=follow_request.requester
            ).exists():
                follow_request.delete()
                logger.warning(
                    f"Follow request {follow_request_id} accepted but follow already exists"
                )
                return Response(
                    {"message": "Already following"},
                    status=status.HTTP_200_OK
                )

            # Store requester id before deleting the request
            requester_id = follow_request.requester.id

            # Create the follow
            follow = Follow.objects.create(
                followed=current_profile,
                followed_by=follow_request.requester
            )

            # Delete the follow request
            follow_request.delete()

            # Trigger notification for the requester that their request was accepted
            from apps.notifications_app.tasks import create_follow_request_accepted_notification_task
            create_follow_request_accepted_notification_task.delay(
                followed_profile_id=current_profile.id,
                follower_profile_id=requester_id
            )

            logger.info(
                f"Follow request {follow_request_id} accepted: "
                f"profile {requester_id} now follows {current_profile.id}"
            )

            serializer = self.get_serializer(follow)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error accepting follow request {follow_request_id}: {str(e)}")
            return Response(
                {"error": "Failed to accept follow request"},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DeclineFollowRequestView(generics.DestroyAPIView):
    """Decline a follow request - deletes the request without creating a Follow."""

    serializer_class = FollowRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FollowRequest.objects.all()

    def destroy(self, request, *args, **kwargs):
        follow_request_id = self.kwargs.get("pk")
        current_profile = request.current_profile

        try:
            follow_request = get_object_or_404(
                FollowRequest,
                pk=follow_request_id,
                target=current_profile
            )

            requester_id = follow_request.requester.id
            follow_request.delete()

            logger.info(
                f"Follow request {follow_request_id} declined by profile {current_profile.id} "
                f"(from profile {requester_id})"
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error declining follow request {follow_request_id}: {str(e)}")
            return Response(
                {"error": "Failed to decline follow request"},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class CancelFollowRequestView(generics.DestroyAPIView):
    """Cancel a sent follow request - allows requester to withdraw their request."""

    serializer_class = FollowRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = FollowRequest.objects.all()

    def destroy(self, request, *args, **kwargs):
        target_profile_public_id = self.kwargs.get("public_id")
        current_profile = request.current_profile

        target_profile = get_object_or_404(Profile, public_id=target_profile_public_id)

        try:
            follow_request = get_object_or_404(
                FollowRequest,
                requester=current_profile,
                target=target_profile
            )

            follow_request.delete()

            logger.info(
                f"Follow request cancelled by profile {current_profile.id} "
                f"to profile {target_profile_public_id}"
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(
                f"Error cancelling follow request from {current_profile.id} "
                f"to {target_profile_public_id}: {str(e)}"
            )
            return Response(
                {"error": "Failed to cancel follow request"},
                status=status.HTTP_400_BAD_REQUEST
            )
