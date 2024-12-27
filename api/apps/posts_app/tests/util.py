from rest_framework.test import APIClient
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core_app.models import Profile, Post, Like, Follow, User, Comment

#
# Create model objects helper functions
#


def create_user(email: str, password: str) -> User:
    """Create and return new User.

    Parameters
    ----------
    email : str
        Email for the User.
    password : str
        Password text for the User.
    """
    return get_user_model().objects.create_user(email=email, password=password)


def create_profile(username: str, about: str, user: User) -> Profile:
    """Create and return new Profile.

    Parameters
    ----------
    username : str
        Username of the Profile.
    about : str
        About text for the Profile.
    user : User
        The User that owns the Profile.
    """
    return Profile.objects.create(username=username, about=about, user=user)


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


#
# Create url helper functions
#


CREATE_POST_URL = reverse("posts_app:create_post")


def get_explore_posts_url(profile_id: int):
    """
    Create and return a get explore posts url.

    Parameters
    ----------
    profile_id : str
        The id of the profile that is used to fetch explore posts.
    """
    return reverse("posts_app:list_explore", args=[profile_id])


def create_like_url(post_id: int):
    """Create and return a create like post url.

    Parameters
    ----------
    post_id : str
        The post id of the Post to like.
    """
    return reverse("posts_app:create_like", args=[post_id])


def destroy_like_url(post_id: int, profile_id: int):
    """Create and return a destroy like url.

    Parameters
    ----------
    post_id : str
        The post id of post that is liked.
    profile_id : str
        The profile id requesting the delete.
    """
    return reverse("posts_app:destroy_like", args=[post_id, profile_id])


def get_feed_url(profile_id: int):
    """Create and return a get feed url.

    Parameters
    ----------
    profile_id : str
        The id of the profile that is used to fetch feed posts.
    """
    return reverse("posts_app:retrieve_feed", args=[profile_id])


def create_comment_url(post_id: int):
    """Create and return a create comment url.

    Parameters
    ----------
    post_id : int
        The id of the Post that the comment will belong to.
    """
    return reverse("posts_app:create_comment", args=[post_id])


def list_post_comments_url(post_id: int):
    """Create and return a list post comments url.

    Parameters
    ----------
    post_id : int
        The id of the Post to fetch comments.
    """
    return reverse("posts_app:list_post_comments", args=[post_id])


def create_follow_url(auth_profile_id: int):
    """Create and return a create follow url.

    Parameters
    ----------
    auth_profile_id : int
        The id of the authenticated user profile.
    """
    return reverse("posts_app:create_follow", args=[auth_profile_id])


# profile id of authenticated user profile and profile id of profile being followed
def create_destroy_follow_url(auth_profile_id: int, followed_profile_id: int):
    """Create and return a destroy follow url.

    Parameters
    ----------
    auth_profile_id : int
        The id of the authenticated user profile.
    followed_profile_id : int
        The id of the profile being followed.
    """
    return reverse(
        "posts_app:destroy_follow", args=[auth_profile_id, followed_profile_id]
    )


#
# Test helper class
#


class PostsAppTestHelper(TestCase):
    """
    Posts App tests setup helper class.
    Creates 4 user/profile combinations with 2 posts each.
    self.profile follows profile_2 leaving profile_3 and profile_4 un-followed.
    Create 2 comments for post_1.

    setUp() method does not authenticate a user. To authenticate a user add the
    following in the setUp() method of the child class:

    self.client.force_authenticate(user=self.user)
    self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)
    """

    def setUp(self):
        # Profile 1
        self.user = create_user("test@example.com", "user1-password-123")
        self.profile = create_profile("username_1", "About text 1.", self.user)
        self.post_1 = create_post("Post 1 caption", self.profile)
        self.post_2 = create_post("Post 2 caption", self.profile)
        # Profile 2
        self.user_2 = create_user("test2@example.com", "user2-password-123")
        self.profile_2 = create_profile("username_2", "About text 2.", self.user_2)
        self.post_3 = create_post("Post 3 caption", self.profile_2)
        self.post_4 = create_post("Post 4 caption", self.profile_2)
        # Profile 3
        self.user_3 = create_user("test3@example.com", "user3-password-123")
        self.profile_3 = create_profile("username_3", "About text 3.", self.user_3)
        self.post_5 = create_post("Post 5 caption", self.profile_3)
        self.post_6 = create_post("Post 6 caption", self.profile_3)
        # Profile 4
        self.user_4 = create_user("test4@example.com", "user4-password-123")
        self.profile_4 = create_profile("username_4", "About text 4.", self.user_4)
        self.post_7 = create_post("Post 7 caption", self.profile_4)
        self.post_8 = create_post("Post 8 caption", self.profile_4)

        # self.profile follows profile 2
        self.follow = create_follow(self.profile, self.profile_2)

        # create 2 comments for post_1
        self.comment_1 = create_comment(self.profile, "Comment One", self.post_1)
        self.comment_2 = create_comment(self.profile, "Comment Two", self.post_1)

        self.client = APIClient()

    def get_follows_count(self):
        """Get and return the number of Follows in the database."""
        return len(Follow.objects.all())

    def get_likes_count(self):
        """Get and return the number of Likes in the database."""
        return len(Like.objects.all())
