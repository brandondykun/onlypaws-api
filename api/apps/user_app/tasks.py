"""
Celery tasks for the user_app.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

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
        context = {"code": token}
        html_body = render_to_string("verify_email_template.html", context)
        text_body = (
            f"Welcome to OnlyPaws!\n\n"
            f"Your verification code is: {token}\n\n"
            f"This code will expire in 15 minutes. "
            f"If you didn't request this verification, please ignore this email."
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Verification email sent successfully to {user_email}")

    except ValidationError:
        logger.error(f"Invalid email address: {user_email}")
        raise  # Don't retry for invalid emails

    except Exception as exc:
        logger.error(f"Error sending verification email to {user_email}: {str(exc)}")

        # Retry with exponential backoff
        retry_delay = 30 * (2**self.request.retries)  # 30s, 60s, 120s
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
        context = {"user_email": user_email, "token": token}
        html_body = render_to_string("password_reset_template.html", context)
        text_body = (
            f"We received a request to reset your OnlyPaws password.\n\n"
            f"Account email: {user_email}\n"
            f"Password reset code: {token}\n\n"
            f"This code will expire in 15 minutes. "
            f"If you didn't request this password reset, please ignore this email."
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Password reset email sent successfully to {user_email}")

    except ValidationError:
        logger.error(f"Invalid email address: {user_email}")
        raise  # Don't retry for invalid emails

    except Exception as exc:
        logger.error(f"Error sending password reset email to {user_email}: {str(exc)}")

        # Retry with exponential backoff
        retry_delay = 30 * (2**self.request.retries)  # 30s, 60s, 120s
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
        context = {"new_email": new_email, "code": token}
        html_body = render_to_string(
            "email_change_verification_template.html",
            context,
        )
        text_body = (
            f"We received a request to update your OnlyPaws account email.\n\n"
            f"New email: {new_email}\n"
            f"Email update code: {token}\n\n"
            f"This code will expire in 15 minutes. "
            f"If you didn't request this email change, please ignore this email."
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[new_email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Email change verification sent successfully to {new_email}")

    except ValidationError:
        logger.error(f"Invalid email address: {new_email}")
        raise  # Don't retry for invalid emails

    except Exception as exc:
        logger.error(
            f"Error sending email change verification to {new_email}: {str(exc)}"
        )

        # Retry with exponential backoff
        retry_delay = 30 * (2**self.request.retries)  # 30s, 60s, 120s
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

        success_context = {"new_email": new_email}
        success_html_body = render_to_string(
            "email_change_success_template.html",
            success_context,
        )
        success_text_body = (
            f"Your OnlyPaws account email has been successfully updated.\n\n"
            f"New email: {new_email}\n\n"
            f"If you didn't make this change, contact support immediately."
        )

        success_email = EmailMultiAlternatives(
            subject="Email change successful",
            body=success_text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[new_email],
        )
        success_email.attach_alternative(success_html_body, "text/html")
        success_email.send(fail_silently=False)

        notification_context = {
            "old_email": old_email,
            "new_email": new_email,
        }
        notification_html_body = render_to_string(
            "email_change_notification_template.html",
            notification_context,
        )
        notification_text_body = (
            f"The email address on your OnlyPaws account has been changed.\n\n"
            f"Previous email: {old_email}\n"
            f"New email: {new_email}\n\n"
            f"If you didn't make this change, contact support immediately."
        )

        notification_email = EmailMultiAlternatives(
            subject="Your email has been changed",
            body=notification_text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[old_email],
        )
        notification_email.attach_alternative(notification_html_body, "text/html")
        notification_email.send(fail_silently=False)

        logger.info(
            f"Email change confirmation sent to both {old_email} and {new_email}"
        )

    except ValidationError as e:
        logger.error(f"Invalid email address in confirmation task: {str(e)}")
        raise  # Don't retry for invalid emails

    except Exception as exc:
        logger.error(f"Error sending email change confirmation: {str(exc)}")

        # Retry with exponential backoff
        retry_delay = 30 * (2**self.request.retries)  # 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=retry_delay)


@shared_task(bind=True, max_retries=3)
def delete_expired_accounts_task(self):
    """
    Delete user accounts whose pending deletion grace period has expired.
    Runs daily via Celery Beat.
    """
    from apps.user_app.models import PendingAccountDeletion

    try:
        cutoff = timezone.now() - timedelta(
            days=PendingAccountDeletion.GRACE_PERIOD_DAYS
        )
        due_deletions = PendingAccountDeletion.objects.filter(
            created_at__lte=cutoff
        ).select_related("user")

        count = 0
        for pending in due_deletions:
            user_email = pending.user.email
            user_id = pending.user.id
            try:
                pending.user.delete()  # CASCADE handles all related data
                count += 1
                logger.info(f"Deleted account for user {user_email} (id={user_id})")
            except Exception as e:
                logger.error(
                    f"Error deleting account for user {user_email} (id={user_id}): {str(e)}"
                )

        logger.info(f"Expired account deletion complete: {count} accounts deleted")
        return {"success": True, "deleted_count": count}

    except Exception as exc:
        logger.error(f"Error in delete_expired_accounts_task: {str(exc)}")
        retry_delay = 30 * (2**self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)
