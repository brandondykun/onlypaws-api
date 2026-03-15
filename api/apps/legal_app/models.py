from django.conf import settings
from django.db import models


class TermsOfService(models.Model):
    content = models.TextField()
    version = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
        ]

    def __str__(self):
        return f"Terms of Service v{self.version}"


class TermsAcceptance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="terms_acceptances",
    )
    terms = models.ForeignKey(
        TermsOfService,
        on_delete=models.CASCADE,
        related_name="acceptances",
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "terms")]
        indexes = [
            models.Index(fields=["user", "terms"]),
        ]

    def __str__(self):
        return f"{self.user} accepted {self.terms}"
