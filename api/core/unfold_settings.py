from django.urls import reverse_lazy
from django.templatetags.static import static


UNFOLD = {
    "SITE_TITLE": "OnlyPaws Admin",
    "SITE_HEADER": "OnlyPaws Admin",
    "SITE_SUBHEADER": "Platform Management",
    "SITE_URL": None,
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
    "COLORS": {
        "base": {
            "50": "#fafafa",
            "100": "#f4f4f5",
            "200": "#e4e4e7",
            "300": "#d4d4d8",
            "400": "#a1a1aa",
            "500": "#71717a",
            "600": "#52525b",
            "700": "#3f3f46",
            "800": "#27272a",
            "900": "#18181b",
            "950": "#09090b",
        },
        "primary": {
            "50": "#f0f9ff",
            "100": "#e0f2fe",
            "200": "#bae6fd",
            "300": "#7dd3fc",
            "400": "#38bdf8",
            "500": "#0ea5e9",
            "600": "#0284c7",
            "700": "#0369a1",
            "800": "#075985",
            "900": "#0c4a6e",
            "950": "#082f49",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Users",
                "collapsible": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": reverse_lazy("admin:user_app_user_changelist"),
                    },
                    {
                        "title": "Auth Providers",
                        "icon": "key",
                        "link": reverse_lazy("admin:user_app_authprovider_changelist"),
                    },
                    {
                        "title": "Verify Email Tokens",
                        "icon": "mark_email_read",
                        "link": reverse_lazy(
                            "admin:user_app_verifyemailtoken_changelist"
                        ),
                    },
                    {
                        "title": "Reset Password Tokens",
                        "icon": "lock_reset",
                        "link": reverse_lazy(
                            "admin:user_app_resetpasswordtoken_changelist"
                        ),
                    },
                    {
                        "title": "Pending Email Changes",
                        "icon": "mail",
                        "link": reverse_lazy(
                            "admin:user_app_pendingemailchange_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Profiles",
                "collapsible": True,
                "items": [
                    {
                        "title": "Profiles",
                        "icon": "badge",
                        "link": reverse_lazy("admin:profile_app_profile_changelist"),
                    },
                    {
                        "title": "Regular Profiles",
                        "icon": "person",
                        "link": reverse_lazy(
                            "admin:profile_app_regularprofile_changelist"
                        ),
                    },
                    {
                        "title": "Business Profiles",
                        "icon": "business_center",
                        "link": reverse_lazy(
                            "admin:profile_app_businessprofile_changelist"
                        ),
                    },
                    {
                        "title": "Profile Images",
                        "icon": "account_circle",
                        "link": reverse_lazy(
                            "admin:profile_app_profileimage_changelist"
                        ),
                    },
                    {
                        "title": "Profile Images Scaled",
                        "icon": "photo_size_select_large",
                        "link": reverse_lazy(
                            "admin:profile_app_profileimagescaled_changelist"
                        ),
                    },
                    {
                        "title": "Pet Types",
                        "icon": "pets",
                        "link": reverse_lazy("admin:profile_app_pettype_changelist"),
                    },
                    {
                        "title": "Addresses",
                        "icon": "location_on",
                        "link": reverse_lazy("admin:profile_app_address_changelist"),
                    },
                ],
            },
            {
                "title": "Posts",
                "collapsible": True,
                "items": [
                    {
                        "title": "Posts",
                        "icon": "image",
                        "link": reverse_lazy("admin:posts_app_post_changelist"),
                    },
                    {
                        "title": "Post Images",
                        "icon": "photo_library",
                        "link": reverse_lazy("admin:posts_app_postimage_changelist"),
                    },
                    {
                        "title": "Post Images Scaled",
                        "icon": "photo_size_select_large",
                        "link": reverse_lazy(
                            "admin:posts_app_postimagescaled_changelist"
                        ),
                    },
                    {
                        "title": "Post Image Tags",
                        "icon": "label",
                        "link": reverse_lazy("admin:posts_app_postimagetag_changelist"),
                    },
                    {
                        "title": "Saved Posts",
                        "icon": "bookmark",
                        "link": reverse_lazy("admin:posts_app_savedpost_changelist"),
                    },
                ],
            },
            {
                "title": "Interactions",
                "collapsible": True,
                "items": [
                    {
                        "title": "Likes",
                        "icon": "favorite",
                        "link": reverse_lazy("admin:interactions_app_like_changelist"),
                    },
                    {
                        "title": "Comments",
                        "icon": "comment",
                        "link": reverse_lazy(
                            "admin:interactions_app_comment_changelist"
                        ),
                    },
                    {
                        "title": "Comment Likes",
                        "icon": "thumb_up",
                        "link": reverse_lazy(
                            "admin:interactions_app_commentlike_changelist"
                        ),
                    },
                    {
                        "title": "Follows",
                        "icon": "person_add",
                        "link": reverse_lazy(
                            "admin:interactions_app_follow_changelist"
                        ),
                    },
                    {
                        "title": "Follow Requests",
                        "icon": "person_add_disabled",
                        "link": reverse_lazy(
                            "admin:interactions_app_followrequest_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Moderation",
                "collapsible": True,
                "items": [
                    {
                        "title": "Report Reasons",
                        "icon": "report",
                        "link": reverse_lazy(
                            "admin:moderation_app_reportreason_changelist"
                        ),
                    },
                    {
                        "title": "Profile Report Reasons",
                        "icon": "report",
                        "link": reverse_lazy(
                            "admin:moderation_app_profilereportreason_changelist"
                        ),
                    },
                    {
                        "title": "Post Reports",
                        "icon": "flag",
                        "link": reverse_lazy(
                            "admin:moderation_app_postreport_changelist"
                        ),
                    },
                    {
                        "title": "Profile Reports",
                        "icon": "flag",
                        "link": reverse_lazy(
                            "admin:moderation_app_profilereport_changelist"
                        ),
                    },
                    {
                        "title": "Profanity Logs",
                        "icon": "warning",
                        "link": reverse_lazy(
                            "admin:moderation_app_profanitylog_changelist"
                        ),
                    },
                    {
                        "title": "Blocks",
                        "icon": "block",
                        "link": reverse_lazy("admin:moderation_app_block_changelist"),
                    },
                    {
                        "title": "Custom Banned Words",
                        "icon": "dangerous",
                        "link": reverse_lazy(
                            "admin:moderation_app_custombannedword_changelist"
                        ),
                    },
                    {
                        "title": "Whitelisted Words",
                        "icon": "check_circle",
                        "link": reverse_lazy(
                            "admin:moderation_app_whitelistedword_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Notifications",
                "collapsible": True,
                "items": [
                    {
                        "title": "Notifications",
                        "icon": "notifications",
                        "link": reverse_lazy(
                            "admin:notifications_app_notification_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Feedback",
                "collapsible": True,
                "items": [
                    {
                        "title": "Feedback",
                        "icon": "feedback",
                        "link": reverse_lazy("admin:feedback_app_feedback_changelist"),
                    },
                    {
                        "title": "Feedback Comments",
                        "icon": "rate_review",
                        "link": reverse_lazy(
                            "admin:feedback_app_feedbackcomment_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Announcements",
                "collapsible": True,
                "items": [
                    {
                        "title": "Announcements",
                        "icon": "campaign",
                        "link": reverse_lazy(
                            "admin:announcements_app_announcement_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Config",
                "collapsible": True,
                "items": [
                    {
                        "title": "App Configuration",
                        "icon": "settings",
                        "link": reverse_lazy(
                            "admin:config_app_appconfiguration_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Legal",
                "collapsible": True,
                "items": [
                    {
                        "title": "Terms of Service",
                        "icon": "gavel",
                        "link": reverse_lazy(
                            "admin:legal_app_termsofservice_changelist"
                        ),
                    },
                    {
                        "title": "Terms Acceptance",
                        "icon": "handshake",
                        "link": reverse_lazy(
                            "admin:legal_app_termsacceptance_changelist"
                        ),
                    },
                ],
            },
        ],
    },
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
            "href": lambda request: static("favicon.png"),
        },
    ],
}
