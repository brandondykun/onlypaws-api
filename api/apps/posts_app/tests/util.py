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


def retrieve_destroy_post_url(post_id: int):
    """Create and return a retrieve/destroy Post url.

    Parameters
    ----------
    post_id : int
        The id of the Post to fetch or destroy.
    """
    return reverse("posts_app:retrieve_update_destroy_post", args=[post_id])


def destroy_post_image_url(post_image_id: int):
    """
    Create and return a destroy post image url.

    Parameters
    ----------
    post_image_id : int
        The id of the post image that is used to build the url.
    """
    return reverse("posts_app:destroy_post_image", args=[post_image_id])

def destroy_post_image_url(post_image_id: int):
    """
    Create and return a destroy post image url.

    Parameters
    ----------
    post_image_id : int
        The id of the post image that is used to build the url.
    """
    return reverse("posts_app:destroy_post_image", args=[post_image_id])
