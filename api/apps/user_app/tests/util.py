"""
Test utilities for user app.
"""

from django.urls import reverse


CHANGE_PASSWORD_URL = reverse("user_app:change_password")
REQUEST_EMAIL_CHANGE_URL = reverse("user_app:request-email-change")
VERIFY_EMAIL_CHANGE_URL = reverse("user_app:verify-email-change")
CREATE_USER_URL = reverse("user_app:create_user")
VERIFY_EMAIL_URL = reverse("user_app:verify_email_token")
REQUEST_NEW_VERIFY_EMAIL_TOKEN_URL = reverse("user_app:request_new_verify_email_token")
REQUEST_RESET_URL = reverse("user_app:request_password_reset")
RESET_PASSWORD_URL = reverse("user_app:reset_password")
MY_INFO_URL = reverse("user_app:my_info")
LOGIN_URL = reverse("user_app:token_obtain_pair")
REFRESH_TOKEN_URL = reverse("user_app:token_refresh")
COMPLETE_ONBOARDING_URL = reverse("user_app:complete-onboarding")
REQUEST_ACCOUNT_DELETION_URL = reverse("user_app:request_account_deletion")
CANCEL_ACCOUNT_DELETION_URL = reverse("user_app:cancel_account_deletion")