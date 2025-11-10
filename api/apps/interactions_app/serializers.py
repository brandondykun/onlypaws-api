"""
Serializers for the interactions app.
"""

from rest_framework import serializers
from apps.interactions_app.models import Like, Comment, CommentLike, Follow
from apps.profile_app.serializers import ProfileSerializer
from apps.posts_app.models import Post
from drf_spectacular.utils import extend_schema_field


class LikeSerializer(serializers.ModelSerializer):
    """Serializer for Likes."""

    class Meta:
        model = Like
        fields = [
            "id",
            "post",
            "profile",
            "liked_at",
        ]
        read_only_fields = ["id", "liked_at"]


class CommentLikeSerializer(serializers.ModelSerializer):
    """Serializer for Comment Likes."""

    class Meta:
        model = CommentLike
        fields = [
            "id",
            "comment",
            "profile",
            "liked_at",
        ]
        read_only_fields = ["id", "liked_at"]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comments."""

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class CommentDetailedSerializer(serializers.ModelSerializer):
    """Detailed serializer for Comments."""

    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    parent_comment_username = serializers.SerializerMethodField()
    reply_to_comment_username = serializers.SerializerMethodField()

    profile = ProfileSerializer()

    class Meta:
        model = Comment
        fields = [
            "id",
            "text",
            "profile",
            "post",
            "created_at",
            "likes_count",
            "liked",
            "replies_count",
            "replies",
            "parent_comment_username",
            "reply_to_comment_username",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "likes_count",
            "liked",
            "replies_count",
            "replies",
            "parent_comment_username",
            "reply_to_comment_username",
        ]

    def get_likes_count(self, obj) -> bool:
        return obj.likes.count()

    def get_liked(self, obj) -> bool:
        # boolean - has requesting profile liked the comment being fetched
        auth_profile_id = self.context["request"].headers["auth-profile-id"]
        if auth_profile_id:
            return obj.likes.filter(profile=auth_profile_id).exists()
        return False

    def get_replies_count(self, obj) -> int:
        replies_count = obj.all_replies.count()
        return replies_count

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_replies(self, obj):
        return []

    def get_parent_comment_username(self, obj) -> str | None:
        if obj.parent_comment:
            return obj.parent_comment.profile.username
        return None

    def get_reply_to_comment_username(self, obj) -> str | None:
        if obj.reply_to_comment:
            return obj.reply_to_comment.profile.username
        return None


class CommentChainSerializer(serializers.ModelSerializer):
    """
    Serializer for a Comment with its parent chain.
    
    This serializer provides the target comment along with its full ancestor context,
    organized into clear top-level fields.
    
    Top-level fields returned:
    - post: Full post object that this comment thread belongs to (PostDetailedSerializer)
            Includes all post details: id, caption, profile, images, likes_count, comments_count, etc.
    
    - target_comment: The requested comment with all its details
        - id: Unique identifier of the target comment
        - text: Text content of the target comment
        - profile: Full profile object of the user who created the target comment (ProfileSerializer)
        - post: ID of the post this comment belongs to
        - created_at: Timestamp when the target comment was created
        - parent_comment: ID of the top-level (root) parent comment, or null if this is a top-level comment
        - reply_to_comment: ID of the immediate parent comment (the comment this directly replies to), or null if top-level
        - reply_to_comment_username: Username of the immediate parent comment's author, or null if top-level
        - likes_count: Total number of likes on the target comment
        - liked: Boolean indicating whether the requesting user has liked the target comment
    
    - root_parent_comment: Full comment object of the top-level (root) parent, or null if this is a top-level comment
                           (includes: id, text, profile, post, created_at, parent_comment, reply_to_comment, 
                            reply_to_comment_username, likes_count, liked)
    
    - parent_chain: List of up to 10 most recent ancestor comments EXCLUDING the root, ordered from oldest to 
                    immediate parent. Each ancestor includes the same fields as root_parent_comment. Empty if 
                    there are no intermediate ancestors.
    
    - omitted_count: Number of ancestor comments omitted between root and parent_chain due to the 10-comment limit.
                     Returns 0 if all ancestors fit within the limit.
    
    Note: root_parent_comment is NEVER included in parent_chain to avoid duplication.
    
    UI can display: [post] → [root] → "X replies hidden" → [parent_chain] → [target_comment]
    
    Example with 50 ancestors:
    - post: The full post object with all details
    - target_comment: The requested comment
    - root_parent_comment: Ancestor #1 (the original top-level comment)
    - parent_chain: Ancestors #40-49 (the last 10 before the target comment)
    - omitted_count: 39 (ancestors #2-40 that were omitted)
    """

    post = serializers.SerializerMethodField()
    target_comment = serializers.SerializerMethodField()
    root_parent_comment = serializers.SerializerMethodField()
    parent_chain = serializers.SerializerMethodField()
    omitted_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "post",
            "target_comment",
            "root_parent_comment",
            "parent_chain",
            "omitted_count",
        ]
        read_only_fields = [
            "post",
            "target_comment",
            "root_parent_comment",
            "parent_chain",
            "omitted_count",
        ]

    def _build_full_chain(self, obj):
        """
        Helper method to build the complete parent chain and cache results.
        
        This traverses the entire tree to find the root and all ancestors,
        then caches the results for use by multiple getter methods.
        
        NOTE: We traverse using reply_to_comment (immediate parent), not parent_comment (top-level root).
        """
        if hasattr(self, '_chain_cache'):
            return self._chain_cache
        
        if not obj.reply_to_comment:
            self._chain_cache = {
                'root': None,
                'all_ancestors': [],
                'last_10': [],
                'omitted_count': 0
            }
            return self._chain_cache

        # Get the requesting profile once
        auth_profile_id = self.context.get("request").headers.get("auth-profile-id")

        # Build complete parent chain by traversing up the tree via reply_to_comment
        all_ancestors = []
        current_comment = obj.reply_to_comment
        seen_ids = set([obj.id])  # Track seen IDs to prevent infinite loops
        
        while current_comment:
            # Circular reference protection
            if current_comment.id in seen_ids:
                break
            seen_ids.add(current_comment.id)
            
            # Get likes count and liked status
            likes_count = current_comment.likes.count()
            liked = False
            if auth_profile_id:
                liked = current_comment.likes.filter(profile=auth_profile_id).exists()
            
            # Get reply_to_comment_username if applicable
            reply_to_comment_username = None
            if current_comment.reply_to_comment:
                reply_to_comment_username = current_comment.reply_to_comment.profile.username
            
            # Serialize the parent comment
            parent_data = {
                "id": current_comment.id,
                "text": current_comment.text,
                "profile": ProfileSerializer(current_comment.profile).data,
                "post": current_comment.post_id,
                "created_at": current_comment.created_at,
                "parent_comment": current_comment.parent_comment_id,
                "reply_to_comment": current_comment.reply_to_comment_id,
                "reply_to_comment_username": reply_to_comment_username,
                "likes_count": likes_count,
                "liked": liked,
            }
            all_ancestors.append(parent_data)
            
            # Move to next parent via reply_to_comment (the immediate parent)
            if not current_comment.reply_to_comment:
                break
            current_comment = current_comment.reply_to_comment
        
        # Reverse to get root-to-parent order
        all_ancestors.reverse()
        
        # Extract root (first ancestor)
        root = all_ancestors[0] if all_ancestors else None
        
        # Get remaining ancestors (excluding root) for the chain
        # The parent_chain should NOT include the root since it's returned separately
        remaining_ancestors = all_ancestors[1:] if len(all_ancestors) > 1 else []
        
        # Get last 10 from remaining ancestors (not including root)
        if len(remaining_ancestors) <= 10:
            last_10 = remaining_ancestors
            omitted_count = 0
        else:
            last_10 = remaining_ancestors[-10:]
            omitted_count = len(remaining_ancestors) - 10
        
        self._chain_cache = {
            'root': root,
            'all_ancestors': all_ancestors,
            'last_10': last_10,
            'omitted_count': omitted_count
        }
        
        return self._chain_cache

    @extend_schema_field(serializers.DictField())
    def get_post(self, obj):
        """
        Returns the full post object that this comment belongs to.
        Uses PostDetailedSerializer to include all post details.
        """
        # Avoid circular import by importing here
        from apps.posts_app.serializers import PostDetailedSerializer
        
        post = obj.post
        return PostDetailedSerializer(post, context=self.context).data

    @extend_schema_field(serializers.DictField())
    def get_target_comment(self, obj):
        """
        Returns the target comment (the comment that was requested).
        Includes all comment details plus likes_count, liked, and reply_to_comment_username.
        """
        auth_profile_id = self.context.get("request").headers.get("auth-profile-id")
        
        # Get likes info
        likes_count = obj.likes.count()
        liked = False
        if auth_profile_id:
            liked = obj.likes.filter(profile=auth_profile_id).exists()
        
        # Get reply_to_comment_username if applicable
        reply_to_comment_username = None
        if obj.reply_to_comment:
            reply_to_comment_username = obj.reply_to_comment.profile.username
        
        return {
            "id": obj.id,
            "text": obj.text,
            "profile": ProfileSerializer(obj.profile).data,
            "post": obj.post_id,
            "created_at": obj.created_at,
            "parent_comment": obj.parent_comment_id,
            "reply_to_comment": obj.reply_to_comment_id,
            "reply_to_comment_username": reply_to_comment_username,
            "likes_count": likes_count,
            "liked": liked,
        }

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_root_parent_comment(self, obj):
        """
        Returns the top-level (root) parent comment.
        Returns None if this comment has no parent (is itself a top-level comment).
        """
        cache = self._build_full_chain(obj)
        return cache['root']
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_parent_chain(self, obj):
        """
        Returns up to the last 10 messages in the parent chain, EXCLUDING the root.
        
        This provides the most recent ancestors leading to this comment,
        ordered from oldest to immediate parent. The root_parent_comment is
        never included in this list to avoid duplication.
        
        Returns:
            List of up to 10 serialized parent comments (excluding root).
        """
        cache = self._build_full_chain(obj)
        return cache['last_10']
    
    def get_omitted_count(self, obj) -> int:
        """
        Returns the number of comments omitted between root and the last 10 shown.
        Returns 0 if all ancestors are included in parent_chain.
        """
        cache = self._build_full_chain(obj)
        return cache['omitted_count']


class CreateFollowSerializer(serializers.Serializer):
    profileId = serializers.IntegerField(
        required=True,
        help_text="The ID of the profile to follow."
    )


class FollowSerializer(serializers.ModelSerializer):
    """Serializer for Follow."""

    class Meta:
        model = Follow
        fields = ["id", "followed", "followed_by", "created_at"]
        read_only_fields = ["id", "created_at"]

