"""
Test utilities for interactions app.
"""

from django.urls import reverse


def create_like_url(post_id: int):
    """Create and return a create like post url.

    Parameters
    ----------
    post_id : str
        The post id of the Post to like.
    """
    return reverse("interactions_app:like_post", args=[post_id])


def destroy_like_url(post_id: int):
    """Create and return a destroy like url.

    Parameters
    ----------
    post_id : str
        The post id of post that is liked.
    """
    return reverse("interactions_app:like_post", args=[post_id])


def create_comment_url(post_id: int):
    """Create and return a create comment url.

    Parameters
    ----------
    post_id : int
        The id of the Post that the comment will belong to.
    """
    return reverse("interactions_app:create_comment", args=[post_id])


def list_post_comments_url(post_id: int):
    """Create and return a list post comments url.

    Parameters
    ----------
    post_id : int
        The id of the Post to fetch comments.
    """
    return reverse("interactions_app:list_post_comments", args=[post_id])


def comment_chain_url(comment_id: int):
    """Create and return a comment chain url.

    Parameters
    ----------
    comment_id : int
        The id of the Comment to fetch with its parent chain.
    """
    return reverse("interactions_app:comment_chain_retrieve", args=[comment_id])


def comment_like_url(comment_id: int):
    """Create and return a comment like url.

    Parameters
    ----------
    comment_id : int
        The id of the Comment to like/unlike.
    """
    return reverse("interactions_app:like_comment", args=[comment_id])


def create_follow_url():
    """Create and return a create follow url."""
    return reverse("interactions_app:create_follow")


def create_destroy_follow_url(profile_public_id: str):
    """Create and return a destroy follow url.

    Parameters
    ----------
    profile_public_id : str
        The public_id (ULID) of the profile being followed.
    """
    return reverse("interactions_app:destroy_follow", args=[profile_public_id])


def list_followers_url(profile_public_id: str):
    """Create and return a list followers url.

    Parameters
    ----------
    profile_public_id : str
        The public_id (ULID) of the profile to fetch followers for.
    """
    return reverse("interactions_app:list_followers", args=[profile_public_id])


def list_following_url(profile_public_id: str):
    """Create and return a list following url.

    Parameters
    ----------
    profile_public_id : str
        The public_id (ULID) of the profile to fetch following for.
    """
    return reverse("interactions_app:list_following", args=[profile_public_id])

