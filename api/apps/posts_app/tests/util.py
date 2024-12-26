from rest_framework.test import APIClient
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core_app.models import Profile, Post, Like, Follow, User

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


#
# Create url helper functions
#


def get_explore_posts_url(profile_id):
    """
    Create and return a get explore posts url.

    Parameters
    ----------
    profile_id : str
        The id of the profile that is used to fetch explore posts.
    """
    return reverse("posts_app:list_explore", args=[profile_id])


#
# Test helper class
#


class PostsAppTestHelper(TestCase):
    """
    Posts App tests setup helper class.
    Creates 4 user/profile combinations with 2 posts each.
    self.profile follows profile_2 leaving profile_3 and profile_4 un-followed.
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

        self.client = APIClient()
