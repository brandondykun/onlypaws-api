# API Endpoint Changes - Profile App Refactor

## Summary
Profile-related endpoints have been moved from multiple locations to a dedicated `/api/v1/profile/` prefix for better organization.

## Frontend Changes Required

### 1. Profile CRUD Operations
**OLD:** `/api/v1/auth/profile/`
**NEW:** `/api/v1/profile/`
- POST to create a new profile

**OLD:** `/api/v1/auth/profile/<id>/`
**NEW:** `/api/v1/profile/<id>/`
- PATCH to update profile
- DELETE to delete profile

**OLD:** `/api/v1/posts/profile/<id>/`
**NEW:** `/api/v1/profile/<id>/detail/`
- GET to retrieve profile details

### 2. Profile Images
**OLD:** `/api/v1/auth/profile-image/`
**NEW:** `/api/v1/profile/image/`
- POST to create profile image

**OLD:** `/api/v1/auth/profile-image/<id>/`
**NEW:** `/api/v1/profile/image/<id>/`
- PATCH to update profile image

### 3. Pet Types
**OLD:** `/api/v1/auth/pet-type-options/`
**NEW:** `/api/v1/profile/pet-types/`
- GET list of pet types

### 4. Profile Search
**OLD:** `/api/v1/posts/profile/<id>/search?username=<query>`
**NEW:** `/api/v1/profile/<id>/search/?username=<query>`
- GET to search profiles by username

### 5. Follow Operations
**OLD:** `/api/v1/posts/profile/<id>/follow/`
**NEW:** `/api/v1/profile/<id>/follow/`
- POST to follow a profile

**OLD:** `/api/v1/posts/profile/<id>/followers/`
**NEW:** `/api/v1/profile/<id>/followers/`
- GET list of followers

**OLD:** `/api/v1/posts/profile/<id>/following/`
**NEW:** `/api/v1/profile/<id>/following/`
- GET list of following

**OLD:** `/api/v1/posts/profile/<auth_profile_id>/follow/<pk>/`
**NEW:** `/api/v1/profile/<auth_profile_id>/follow/<pk>/`
- DELETE to unfollow a profile

## Endpoints That Did NOT Change

### User/Auth Endpoints (still under `/api/v1/auth/`)
- `/api/v1/auth/create-user/` - Create user account
- `/api/v1/auth/login/` - Login (JWT token)
- `/api/v1/auth/refresh/` - Refresh JWT token
- `/api/v1/auth/my-info/` - Get current user info with profiles
- `/api/v1/auth/verify-email-token/` - Verify email
- `/api/v1/auth/resend-verify-email-token/` - Resend verification email
- `/api/v1/auth/request-password-reset/` - Request password reset
- `/api/v1/auth/reset-password/` - Reset password with token
- `/api/v1/auth/change-password/` - Change password (authenticated)
- `/api/v1/auth/request-email-change/` - Request email change
- `/api/v1/auth/verify-email-change/` - Verify email change

### Post Endpoints (still under `/api/v1/`)
- `/api/v1/profile/<id>/posts/` - Get posts by profile (STAYED)
- `/api/v1/profile/<id>/feed/` - Get feed for profile (STAYED)
- `/api/v1/profile/<id>/explore/` - Get explore posts (STAYED)
- All other post, comment, like endpoints unchanged

## Migration Notes

1. **No Database Changes**: This is purely a routing refactor. No migrations needed for existing data.
2. **Fixture Updates**: Fixture files need model references updated from `user_app.Profile` to `profile_app.Profile`
3. **Settings Update**: Add `'apps.profile_app'` to `INSTALLED_APPS` in settings.py

## Testing
After updating frontend API calls, test:
1. Profile creation
2. Profile updates
3. Profile image uploads
4. Profile search
5. Follow/unfollow operations
6. Pet type selection

All functionality should work identically, just with new URLs.

