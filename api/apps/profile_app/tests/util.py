from rest_framework.test import APIClient
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.user_app.models import User
from apps.profile_app.models import Profile, RegularProfile
from apps.posts_app.models import Post
from apps.interactions_app.models import Follow

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


def create_follow_url(auth_profile_id: int):
    """Create and return a create follow url.

    Parameters
    ----------
    auth_profile_id : int
        The id of the authenticated user profile.
    """
    return reverse("profile_app:create_follow", args=[auth_profile_id])


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
        "profile_app:destroy_follow", args=[auth_profile_id, followed_profile_id]
    )


def search_profiles_url(profile_id: int, search_text: str):
    """Create and return a search profiles url.

    Parameters
    ----------
    profile_id : int
        The id of the authenticated user profile performing the search.
    search_text : str
        Search text of username (partial or full) to be searched.
    """
    return f"{reverse('profile_app:search_profiles', args=[profile_id])}?username={search_text}"


#
# Test helper class
#


class ProfileAppTestHelper(TestCase):
    """
    Profile App tests setup helper class.
    Creates 4 user/profile combinations with 2 posts each.
    self.profile follows profile_2 leaving profile_3 and profile_4 un-followed.

    setUp() method does not authenticate a user. To authenticate a user add the
    following in the setUp() method of the child class:

    self.client.force_authenticate(user=self.user)
    self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)
    """

    def setUp(self):
        # Profile 1
        self.user = create_user("test@example.com", "user1-password-123", is_staff=True)
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

    def get_follows_count(self):
        """Get and return the number of Follows in the database."""
        return len(Follow.objects.all())

