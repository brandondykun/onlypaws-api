from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.user_app.models import User
from apps.profile_app.models import Profile, RegularProfile
from apps.posts_app.models import Post, PostImage
from apps.interactions_app.models import Like, Follow, Comment, CommentLike

#
# Create model objects helper functions
#


def create_user(email: str, password: str, is_staff=False) -> User:
    """Create and return new User.

    Parameters
    ----------
    email : str
        Email for the User.
    password : str
        Password text for the User.
    """
    return get_user_model().objects.create_user(
        email=email, password=password, is_staff=is_staff
    )


def create_profile(username: str, about: str, user: User) -> Profile:
    """Create and return new Profile (via RegularProfile creation).

    Parameters
    ----------
    username : str
        Username of the Profile.
    about : str
        About text for the Profile.
    user : User
        The User that owns the Profile.
    
    Returns
    -------
    Profile
        The base Profile instance (for consistency with ForeignKey relationships).
    """
    regular_profile = RegularProfile.objects.create(username=username, about=about, user=user)
    # Return the base Profile instance to match what ForeignKey relationships return
    return Profile.objects.get(pk=regular_profile.pk)


def create_post(caption: str, profile: Profile) -> Post:
    """
    Create and return new Post.

    Parameters
    ----------
    caption : str
        The caption of the Post.
    profile : Profile
        The Profile that owns/created the Post.
    """
    return Post.objects.create(caption=caption, profile=profile)


def create_post_image(post: Post, image_file=None) -> PostImage:
    """
    Create and return new PostImage.

    Parameters
    ----------
    post : Post
        The Post that owns the PostImage.
    image_file : file, optional
        The image file. If None, creates with a mock file.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    import io

    if image_file is None:
        # Create a simple test image
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, 'JPEG')
        image_io.seek(0)
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            image_io.getvalue(),
            content_type="image/jpeg"
        )
    
    return PostImage.objects.create(post=post, image=image_file)


def create_follow(followed_by: Profile, followed: Profile) -> Follow:
    """Create and return new Follow.

    Parameters
    ----------
    followed_by : Profile
        Profile that is following the other Profile.
    followed : Profile
        Profile that is being followed.
    """
    return Follow.objects.create(followed_by=followed_by, followed=followed)


def create_like(profile: Profile, post: Post):
    """Create and return new post Like.

    Parameters
    ----------
    profile : Profile
        Profile to like Post.
    post : Post
        Post being liked.
    """
    return Like.objects.create(profile=profile, post=post)


def create_comment(
    profile: Profile,
    text: str,
    post: Post,
    parent_comment: Comment | None = None,
    reply_to_comment: Comment | None = None,
):
    """Create and return new Comment.

    Parameters
    ----------
    profile : Profile
        Profile creating the Comment.
    text : str
        Comment text.
    post : Post
        Post that the comment belongs to.
    parent_comment : Comment | None
        Highest level comment that the comment belongs to if it is a reply comment.
    reply_to_comment : Comment | None
        Comment that this comment is directly replying to.
    """
    return Comment.objects.create(
        profile=profile,
        text=text,
        post=post,
        parent_comment=parent_comment,
        reply_to_comment=reply_to_comment,
    )


def create_comment_like(profile: Profile, comment: Comment):
    """Create and return new comment Like.

    Parameters
    ----------
    profile : Profile
        Profile to like Comment.
    comment : Comment
        Comment being liked.
    """
    return CommentLike.objects.create(profile=profile, comment=comment)


#
# Create url helper functions
#


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


def create_destroy_follow_url(followed_profile_id: int):
    """Create and return a destroy follow url.

    Parameters
    ----------
    followed_profile_id : int
        The id of the profile being followed.
    """
    return reverse("interactions_app:destroy_follow", args=[followed_profile_id])


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


#
# Import shared test helper classes from their original locations
# to avoid duplication
#

# Import PostsAppTestHelper for Like, Comment, and CommentLike tests
from apps.posts_app.tests.util import PostsAppTestHelper

# Import ProfileAppTestHelper for Follow tests  
from apps.profile_app.tests.util import ProfileAppTestHelper
