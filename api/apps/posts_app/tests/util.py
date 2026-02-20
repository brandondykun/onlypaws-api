"""
Test utilities for posts app.
"""

from django.urls import reverse


CREATE_POST_URL = reverse("posts_app:create_post")


def get_explore_posts_url():
    """
    Create and return a get explore posts url.

    Parameters
    ----------
    profile_id : int
        The id of the profile that is used to fetch explore posts.
    """
    return reverse("posts_app:list_explore")


def get_feed_url():
    """Create and return a get feed url.

    Parameters
    ----------
    profile_id : int
        The id of the profile that is used to fetch feed posts.
    """
    return reverse("posts_app:retrieve_feed")


def retrieve_destroy_post_url(post):
    """Create and return a retrieve/destroy Post url.

    Parameters
    ----------
    post : Post or str
        The Post instance or its public_id (string).
    """
    public_id = str(post.public_id) if hasattr(post, "public_id") else post
    return reverse("posts_app:retrieve_update_destroy_post", args=[public_id])


def destroy_post_image_url(post_image):
    """
    Create and return a destroy post image url.

    Parameters
    ----------
    post_image : PostImage or str
        The PostImage instance or its public_id (string).
    """
    public_id = str(post_image.public_id) if hasattr(post_image, "public_id") else post_image
    return reverse("posts_app:destroy_post_image", args=[public_id])


def list_similar_posts_url(post):
    """
    Create and return a list similar posts url.

    Parameters
    ----------
    post : Post or str
        The Post instance or its public_id (string).
    """
    public_id = str(post.public_id) if hasattr(post, "public_id") else post
    return reverse("posts_app:lists_similar_posts", args=[public_id])


def list_create_saved_post_url():
    """
    Create and return a list/create saved posts url.
    """
    return reverse("posts_app:list_create_saved_post")


def destroy_saved_post_url(post):
    """
    Create and return a destroy saved post url.

    Parameters
    ----------
    post : Post or str
        The Post instance or its public_id (string).
    """
    public_id = str(post.public_id) if hasattr(post, "public_id") else post
    return reverse("posts_app:destroy_saved_post", args=[public_id])
