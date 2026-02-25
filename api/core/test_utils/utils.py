"""
Shared test utilities for all apps.
"""

import tempfile
import io
from PIL import Image
from django.contrib.auth import get_user_model
from apps.user_app.models import User
from apps.profile_app.models import Profile, RegularProfile, ProfileImage, PetType
from apps.posts_app.models import Post, PostImage
from apps.interactions_app.models import Like, Follow, Comment, CommentLike
from apps.feedback_app.models import Feedback
from apps.moderation_app.models import PostReport, ReportReason, ProfanityLog
from apps.announcements_app.models import Announcement
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone


def create_test_image(name='test_image.jpg', size=(100, 100), color='red'):
    """
    Helper function to create a test image file in memory.
    
    Parameters
    ----------
    name : str
        Name of the image file.
    size : tuple
        Size of the image (width, height).
    color : str
        Color of the image.
        
    Returns
    -------
    SimpleUploadedFile
        A test image file ready to be uploaded.
    """
    image = Image.new('RGB', size, color=color)
    image_io = io.BytesIO()
    image.save(image_io, 'JPEG')
    image_io.seek(0)
    return SimpleUploadedFile(
        name,
        image_io.getvalue(),
        content_type="image/jpeg"
    )


def create_user(email: str, password: str = "test_password_123", is_staff=False) -> User:
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


def create_pet_type(name: str) -> PetType:
    """Create and return new PetType.

    Parameters
    ----------
    name : str
        Name of the pet type (e.g., 'Dog', 'Cat').
    """
    return PetType.objects.create(name=name)


def create_profile(
    username: str,
    user: User,
    about: str = "",
    name: str = "",
    pet_type: PetType = None,
    breed: str = "",
) -> Profile:
    """Create and return new Profile (via RegularProfile creation).

    Parameters
    ----------
    username : str
        Username of the Profile.
    user : User
        The User that owns the Profile.
    about : str
        About text for the Profile.
    name : str
        Name of the Profile (pet's name).
    pet_type : PetType, optional
        The type of pet for this profile.
    breed : str
        The breed of the pet.
    
    Returns
    -------
    Profile
        The base Profile instance (for consistency with ForeignKey relationships).
    """
    regular_profile = RegularProfile.objects.create(
        username=username,
        about=about,
        user=user,
        name=name,
        pet_type=pet_type,
        breed=breed,
    )
    # Return the base Profile instance to match what ForeignKey relationships return
    return Profile.objects.get(pk=regular_profile.pk)


def create_post(caption: str, profile: Profile, aspect_ratio: str = Post.AspectRatio.SQUARE) -> Post:
    """
    Create and return new Post.

    Parameters
    ----------
    caption : str
        The caption of the Post.
    profile : Profile
        The Profile that owns/created the Post.
    aspect_ratio : str
        The aspect ratio for all images in this post. Options: Post.AspectRatio.SQUARE (default), Post.AspectRatio.PORTRAIT.
    """
    return Post.objects.create(caption=caption, profile=profile, aspect_ratio=aspect_ratio)


def create_post_image(post: Post, image_file=None, embedding=None) -> PostImage:
    """
    Create and return new PostImage.

    Parameters
    ----------
    post : Post
        The Post that owns the PostImage.
    image_file : file, optional
        The image file. If None, creates with a mock file.
    embedding : list, optional
        A 512-dimensional embedding vector for similarity testing. If None, no embedding is set.
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
    
    post_image = PostImage.objects.create(post=post, image=image_file)
    
    # Set embedding if provided (useful for similarity testing)
    if embedding is not None:
        post_image.embedding = embedding
        post_image.save(update_fields=['embedding'])
    
    return post_image


def create_mock_embedding(base_value=0.5, variation=0.0, dimensions=512, seed=None):
    """
    Create a mock embedding vector for testing similarity search.
    
    Parameters
    ----------
    base_value : float
        The base value for all dimensions (default: 0.5).
    variation : float
        Variation to add to each dimension. For more realistic embeddings
        with actual cosine distance differences, use a larger variation (default: 0.0).
    dimensions : int
        Number of dimensions in the vector (default: 512).
    seed : int, optional
        Random seed for reproducibility (default: None).
        
    Returns
    -------
    list
        A list of floats representing the embedding vector.
        
    Notes
    -----
    To create similar embeddings, use similar seed values and base_value.
    To create different embeddings, use different seed values.
    For deterministic results, always pass a seed value.
    
    Note: Cosine distance measures angular difference, not magnitude.
    To get meaningful differences, use variation > 0.1 or different seeds.
    """
    import random
    if seed is not None:
        random.seed(seed)
    
    # If variation is 0, create slight controlled variation based on seed
    if variation == 0.0 and seed is not None:
        # Create reproducible but varied embeddings
        return [base_value + (hash(f"{seed}_{i}") % 1000) / 10000.0 for i in range(dimensions)]
    
    return [base_value + random.uniform(-variation, variation) for _ in range(dimensions)]


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


def create_profile_image(profile):
    """Helper function to create a profile image."""
    # Create a temporary image file
    image_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    image = Image.new("RGB", (100, 100))
    image.save(image_file, "JPEG")
    image_file.seek(0)

    # Create the profile image
    return ProfileImage.objects.create(
        profile=profile,
        image=SimpleUploadedFile(
            name="test_image.jpg", content=image_file.read(), content_type="image/jpeg"
        ),
    )


def create_feedback(
    title: str,
    description: str,
    ticket_type: str,
    reporter,
    status: str = Feedback.FeedbackStatus.OPEN,
    priority: str = Feedback.Priority.MEDIUM,
) -> Feedback:
    """Create and return new Feedback.

    Parameters
    ----------
    title : str
        Title of the feedback ticket.
    description : str
        Description of the feedback.
    ticket_type : str
        Type of ticket (Feedback.TicketType.BUG, FEATURE, or GENERAL).
    reporter : User
        The User who reported the feedback.
    status : str
        Status of the feedback. Defaults to OPEN.
    priority : str
        Priority of the feedback. Defaults to MEDIUM.
    """
    return Feedback.objects.create(
        title=title,
        description=description,
        ticket_type=ticket_type,
        reporter=reporter,
        status=status,
        priority=priority,
    )


def create_report_reason(
    name: str,
    description: str = "",
    is_active: bool = True,
) -> ReportReason:
    """Create and return new ReportReason.

    Parameters
    ----------
    name : str
        Name of the report reason.
    description : str
        Description of the report reason.
    is_active : bool
        Whether the report reason is active.
    """
    return ReportReason.objects.create(
        name=name,
        description=description,
        is_active=is_active,
    )


def create_post_report(
    post: Post,
    reporter: Profile,
    reason: ReportReason,
    status: str = PostReport.ReportStatus.PENDING,
    details: str = "",
) -> PostReport:
    """Create and return new PostReport.

    Parameters
    ----------
    post : Post
        The Post being reported.
    reporter : Profile
        The Profile reporting the post.
    reason : ReportReason
        The reason for the report.
    status : str
        The status of the report. Defaults to PENDING.
    details : str
        Additional details about the report.
    """
    return PostReport.objects.create(
        post=post,
        reporter=reporter,
        reason=reason,
        status=status,
        details=details,
    )


def create_announcement(
    title: str,
    message: str,
    start_date=None,
    end_date=None,
    priority: str = "normal",
    is_active: bool = True,
    announcement_type: str = "general",
) -> Announcement:
    """Create and return new Announcement.

    Parameters
    ----------
    title : str
        Title of the announcement.
    message : str
        Message content of the announcement.
    start_date : datetime, optional
        When the announcement starts. Defaults to now.
    end_date : datetime, optional
        When the announcement ends. Defaults to None (no end date).
    priority : str
        Priority level ('low', 'normal', 'high'). Defaults to 'normal'.
    is_active : bool
        Whether the announcement is active. Defaults to True.
    announcement_type : str
        Type of announcement. Defaults to 'general'.
    """
    if start_date is None:
        start_date = timezone.now()

    return Announcement.objects.create(
        title=title,
        message=message,
        start_date=start_date,
        end_date=end_date,
        priority=priority,
        is_active=is_active,
        announcement_type=announcement_type,
    )


def create_profanity_log(
    original_text: str,
    content_type: str = "COMMENT",
    detection_method: str = "WORD_MATCH",
    detection_details: dict = None,
    profile=None,
) -> ProfanityLog:
    """Create and return new ProfanityLog.

    Parameters
    ----------
    original_text : str
        The text that was flagged.
    content_type : str
        The type of content (e.g., COMMENT, USERNAME, CAPTION).
    detection_method : str
        The method used for detection (e.g., WORD_MATCH, ML).
    detection_details : dict, optional
        Additional details about the detection.
    profile : Profile, optional
        The profile associated with the log entry.
    """
    return ProfanityLog.objects.create(
        original_text=original_text,
        content_type=content_type,
        detection_method=detection_method,
        detection_details=detection_details or {},
        profile=profile,
    )
