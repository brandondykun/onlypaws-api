"""
Celery tasks for the user_app.
"""

import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, user_email: str, token: str):
    """
    Background task to send verification email to user.
    
    Args:
        user_email: User's email address
        token: Verification token
    """
    try:
        # Validate email address
        validate_email(user_email)
        
        subject = "Verify Your OnlyPaws Email"
        message = f"Your verification code is: {token}"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        
        logger.info(f"Verification email sent successfully to {user_email}")
        
    except ValidationError:
        logger.error(f"Invalid email address: {user_email}")
        raise  # Don't retry for invalid emails
        
    except Exception as exc:
        logger.error(f"Error sending verification email to {user_email}: {str(exc)}")
        
        # Retry with exponential backoff
        retry_delay = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=retry_delay)


@shared_task(bind=True, max_retries=3)
def send_reset_password_email_task(self, user_email: str, token: str):
    """
    Background task to send reset password email to user.
    
    Args:
        user_email: User's email address
        token: Reset password token
    """
    try:
        # Validate email address
        validate_email(user_email)
        
        subject = "Reset Your OnlyPaws Password"
        message = f"Your password reset code is: {token}"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        
        logger.info(f"Password reset email sent successfully to {user_email}")
        
    except ValidationError:
        logger.error(f"Invalid email address: {user_email}")
        raise  # Don't retry for invalid emails
        
    except Exception as exc:
        logger.error(f"Error sending password reset email to {user_email}: {str(exc)}")
        
        # Retry with exponential backoff
        retry_delay = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=retry_delay)


@shared_task(bind=True, max_retries=3)
def send_email_change_email_task(self, new_email: str, token: str):
    """
    Background task to send email change verification email.
    
    Args:
        new_email: New email address to send verification to
        token: Email change verification token
    """
    try:
        # Validate email address
        validate_email(new_email)
        
        subject = "Update Your OnlyPaws Email"
        message = f"Your email update code is: {token}"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [new_email],
            fail_silently=False,
        )
        
        logger.info(f"Email change verification sent successfully to {new_email}")
        
    except ValidationError:
        logger.error(f"Invalid email address: {new_email}")
        raise  # Don't retry for invalid emails
        
    except Exception as exc:
        logger.error(f"Error sending email change verification to {new_email}: {str(exc)}")
        
        # Retry with exponential backoff
        retry_delay = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=retry_delay)


@shared_task(bind=True, max_retries=3)
def send_email_change_confirmation_task(self, old_email: str, new_email: str):
    """
    Background task to send confirmation emails after successful email change.
    
    Args:
        old_email: Previous email address
        new_email: New email address
    """
    try:
        # Validate email addresses
        validate_email(old_email)
        validate_email(new_email)
        
        # Send confirmation to new email
        send_mail(
            "Email change successful",
            "Your email has been successfully updated.",
            settings.DEFAULT_FROM_EMAIL,
            [new_email],
            fail_silently=False,
        )
        
        # Send notification to old email
        send_mail(
            "Your email has been changed",
            f"Your email has been changed to {new_email}.",
            settings.DEFAULT_FROM_EMAIL,
            [old_email],
            fail_silently=False,
        )
        
        logger.info(f"Email change confirmation sent to both {old_email} and {new_email}")
        
    except ValidationError as e:
        logger.error(f"Invalid email address in confirmation task: {str(e)}")
        raise  # Don't retry for invalid emails
        
    except Exception as exc:
        logger.error(f"Error sending email change confirmation: {str(exc)}")
        
        # Retry with exponential backoff
        retry_delay = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=retry_delay)
