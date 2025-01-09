from django.urls import reverse
from rest_framework import status
from apps.core_app.models import PostReport
from .util import PostsAppTestHelper


class PublicReportReasonTests(PostsAppTestHelper):
    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_list_report_reasons_unauthenticated(self):
        """Test that unauthenticated users cannot list report reasons"""
        url = reverse("posts_app:report-reason-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_report_reasons_no_profile_header(self):
        """Test that requests without profile header are rejected"""
        self.client.force_authenticate(user=self.user)

        url = reverse("posts_app:report-reason-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateReportReasonTests(PostsAppTestHelper):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_list_report_reasons_authenticated(self):
        """Test that authenticated users can list report reasons"""
        url = reverse("posts_app:report-reason-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][1]["name"], self.reason1.name)


class PrivatePostReportTests(PostsAppTestHelper):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_create_report(self):
        """Test creating a new report"""
        url = reverse("posts_app:report-list")
        data = {
            "post": self.post_3.id,
            "reason": self.reason1.id,
            "details": "This is spam content",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostReport.objects.count(), 3)
        self.assertEqual(PostReport.objects.first().reporter, self.profile)

    def test_duplicate_report(self):
        """Test that a user cannot report the same post twice"""
        url = reverse("posts_app:report-list")
        data = {
            "post": self.post_4.id,
            "reason": self.reason1.id,
            "details": "Another report",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PostReport.objects.count(), 2)

    def test_list_own_reports(self):
        """Test that users can list their own reports"""
        url = reverse("posts_app:report-my-reports")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.report1.id)

    def test_staff_resolve_report(self):
        """Test that staff can resolve reports"""
        report = PostReport.objects.create(
            post=self.post_5, reporter=self.profile_4, reason=self.reason1
        )

        url = reverse("posts_app:report-resolve", kwargs={"pk": report.id})
        data = {"status": "RESOLVED", "resolution_note": "Content removed"}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, "RESOLVED")
        self.assertEqual(report.resolution_note, "Content removed")
        self.assertEqual(report.resolved_by, self.profile)

    def test_list_reported_posts(self):
        """Test listing reports on user's posts"""
        url = reverse("posts_app:report-reported-posts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.report2.id)

    def test_staff_list_all_reports(self):
        """Test that staff can see all reports"""
        url = reverse("posts_app:report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

    def test_invalid_report_status(self):
        """Test that invalid status values are rejected"""
        report = PostReport.objects.create(
            post=self.post_3, reporter=self.profile, reason=self.reason1
        )

        url = reverse("posts_app:report-resolve", kwargs={"pk": report.id})
        data = {"status": "INVALID_STATUS", "resolution_note": "Test note"}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PrivateNonStaffPostReportTests(PostsAppTestHelper):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user_2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile_2.id)

    def test_non_staff_cannot_resolve_report(self):
        """Test that non-staff users cannot resolve reports"""
        report = PostReport.objects.create(
            post=self.post_8, reporter=self.profile, reason=self.reason1
        )

        url = reverse("posts_app:report-resolve", kwargs={"pk": report.id})
        data = {"status": "RESOLVED", "resolution_note": "Content removed"}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        report.refresh_from_db()
        self.assertEqual(report.status, "PENDING")


class PrivateBadHeadersPostReportTests(PostsAppTestHelper):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.client.force_authenticate(user=self.user_3)
        # user attached to profile 1 is authenticated. Send profile 2's id in the header
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile_2.id)

    def test_invalid_profile_id(self):
        """Test that requests with invalid profile IDs are rejected"""
        url = reverse("posts_app:report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
