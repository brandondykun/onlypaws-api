# Profile Serializers Guide

This document explains the new profile serializer architecture that separates Regular (Pet) Profiles from Business Profiles.

## Architecture Overview

The profile system uses **multi-table inheritance** with Django models:
- `Profile` - Base model with common fields (username, user, is_active, timestamps)
- `RegularProfile` - Extends Profile for pet accounts (name, about, breed, pet_type)
- `BusinessProfile` - Extends Profile for business accounts (business_name, category, website, etc.)

## Serializer Categories

### 1. Regular Profile Serializers

#### `RegularProfileSerializer` (READ)
Used for returning regular profile data.

**Fields:**
- `id`, `username`, `user` (from parent Profile)
- `name`, `about`, `breed`, `pet_type` (RegularProfile fields)
- `image` (from parent Profile via SerializerMethodField)
- `is_active`, `created_at`, `updated_at` (from parent)
- `profile_type` (always returns "regular")

**Usage:**
```python
from apps.user_app.serializers import RegularProfileSerializer

regular_profile = RegularProfile.objects.get(id=profile_id)
serializer = RegularProfileSerializer(regular_profile)
return Response(serializer.data)
```

#### `RegularProfileCreateSerializer` (CREATE)
Used for creating new regular profiles.

**Input Fields:**
- `username` (required)
- `user` (required - user ID)
- `name`, `about`, `breed`, `pet_type` (optional)

**Usage:**
```python
from apps.user_app.serializers import RegularProfileCreateSerializer

data = {
    'username': 'fluffy_cat',
    'user': request.user.id,
    'name': 'Fluffy',
    'about': 'A cute cat',
    'breed': 'Persian',
    'pet_type': pet_type_id
}
serializer = RegularProfileCreateSerializer(data=data)
if serializer.is_valid():
    profile = serializer.save()
    return Response(serializer.data, status=201)
```

#### `RegularProfileUpdateSerializer` (UPDATE)
Used for updating regular profiles.

**Input Fields:**
- `username` (optional)
- `name`, `about`, `breed`, `pet_type` (optional)

**Usage:**
```python
from apps.user_app.serializers import RegularProfileUpdateSerializer

regular_profile = RegularProfile.objects.get(id=profile_id)
serializer = RegularProfileUpdateSerializer(
    regular_profile, 
    data=request.data, 
    partial=True
)
if serializer.is_valid():
    serializer.save()
    return Response(serializer.data)
```

#### `RegularProfileDetailedSerializer` (DETAILED READ)
Used for detailed profile views with counts and relationships.

**Additional Fields:**
- `is_following` - Whether the requesting user follows this profile
- `posts_count` - Number of posts
- `followers_count` - Number of followers
- `following_count` - Number of profiles being followed

**Usage:**
```python
from apps.user_app.serializers import RegularProfileDetailedSerializer

regular_profile = RegularProfile.objects.get(id=profile_id)
serializer = RegularProfileDetailedSerializer(
    regular_profile,
    context={'request': request}  # Required for is_following
)
return Response(serializer.data)
```

---

### 2. Business Profile Serializers

#### `BusinessProfileSerializer` (READ)
Used for returning business profile data.

**Fields:**
- `id`, `username`, `user` (from parent Profile)
- `business_name`, `business_category`, `about`
- `website`, `phone`, `address`
- `verified`, `subscription_tier`, `analytics_enabled`, `business_hours`
- `image` (from parent Profile via SerializerMethodField)
- `is_active`, `created_at`, `updated_at` (from parent)
- `profile_type` (always returns "business")

**Usage:**
```python
from apps.user_app.serializers import BusinessProfileSerializer

business_profile = BusinessProfile.objects.get(id=profile_id)
serializer = BusinessProfileSerializer(business_profile)
return Response(serializer.data)
```

#### `BusinessProfileCreateSerializer` (CREATE)
Used for creating new business profiles.

**Input Fields:**
- `username` (required)
- `user` (required - user ID)
- `business_name` (required)
- `business_category` (required - choice field)
- `about`, `website`, `phone`, `business_hours` (optional)

**Usage:**
```python
from apps.user_app.serializers import BusinessProfileCreateSerializer

data = {
    'username': 'pawsome_vet',
    'user': request.user.id,
    'business_name': 'Pawsome Veterinary Clinic',
    'business_category': 'VETERINARY',
    'about': 'Full service veterinary clinic',
    'website': 'https://pawsome.com',
    'phone': '+1-555-0123'
}
serializer = BusinessProfileCreateSerializer(data=data)
if serializer.is_valid():
    profile = serializer.save()
    return Response(serializer.data, status=201)
```

#### `BusinessProfileUpdateSerializer` (UPDATE)
Used for updating business profiles.

**Input Fields:**
- `username` (optional)
- `business_name`, `business_category`, `about` (optional)
- `website`, `phone`, `business_hours` (optional)

**Note:** `verified`, `subscription_tier`, and `analytics_enabled` are read-only (admin only).

#### `BusinessProfileDetailedSerializer` (DETAILED READ)
Similar to BusinessProfileSerializer but includes relationship counts.

---

### 3. Generic/Polymorphic Serializers

These serializers work with mixed profile types (when querying `Profile.objects.all()`).

#### `ProfileSerializer`
Generic serializer that works with both profile types using conditional logic.

**Usage:**
```python
from apps.user_app.serializers import ProfileSerializer

# Works with mixed profile types
profiles = Profile.objects.select_related('regularprofile', 'businessprofile').all()
serializer = ProfileSerializer(profiles, many=True)
return Response(serializer.data)
```

#### `ProfileOptionSerializer`
Minimal profile info for selection/listing (used in user profile lists).

#### `ProfileDetailedSerializer`
Detailed view that works with both profile types.

---

### 4. Legacy/Compatibility Serializers

Maintained for backward compatibility with existing code.

#### `ProfileCreateSerializer`
Creates RegularProfile by default (for backward compatibility).

#### `ProfileUpdateSerializer`
Updates either profile type based on instance.

---

## Helper Functions

### Getting the Right Serializer for a Profile

```python
def get_profile_serializer_class(profile):
    """Return the appropriate serializer class for a profile."""
    if hasattr(profile, 'regularprofile'):
        return RegularProfileSerializer
    elif hasattr(profile, 'businessprofile'):
        return BusinessProfileSerializer
    return ProfileSerializer  # fallback

def get_detailed_serializer_class(profile):
    """Return the appropriate detailed serializer class."""
    if hasattr(profile, 'regularprofile'):
        return RegularProfileDetailedSerializer
    elif hasattr(profile, 'businessprofile'):
        return BusinessProfileDetailedSerializer
    return ProfileDetailedSerializer  # fallback
```

### Serializing Mixed Profile Types

```python
def serialize_profiles(profiles, context=None):
    """Serialize a queryset of mixed profile types."""
    serialized = []
    for profile in profiles:
        specific_profile = profile.get_specific_profile()
        serializer_class = get_profile_serializer_class(profile)
        serializer = serializer_class(specific_profile, context=context)
        serialized.append(serializer.data)
    return serialized
```

---

## QuerySet Optimization

Always use `select_related()` to avoid N+1 queries:

```python
# Good - Single query
profiles = Profile.objects.select_related('regularprofile', 'businessprofile').all()

# Bad - N+1 queries
profiles = Profile.objects.all()  # Then accessing .regularprofile causes extra queries
```

For related data:
```python
# Include pet_type for regular profiles
RegularProfile.objects.select_related('profile_ptr', 'pet_type')

# Include address for business profiles
BusinessProfile.objects.select_related('profile_ptr', 'address')
```

---

## API Endpoint Recommendations

### Current Structure (Backward Compatible)
```
POST   /api/profiles/          - Create profile (defaults to regular)
PATCH  /api/profiles/{id}/     - Update profile (any type)
DELETE /api/profiles/{id}/     - Delete profile
GET    /api/profiles/{id}/     - Get profile details
```

### Recommended Future Structure
```
# Regular Profiles
POST   /api/profiles/regular/           - Create regular profile
GET    /api/profiles/regular/{id}/      - Get regular profile
PATCH  /api/profiles/regular/{id}/      - Update regular profile
DELETE /api/profiles/regular/{id}/      - Delete regular profile

# Business Profiles
POST   /api/profiles/business/          - Create business profile
GET    /api/profiles/business/{id}/     - Get business profile
PATCH  /api/profiles/business/{id}/     - Update business profile
DELETE /api/profiles/business/{id}/     - Delete business profile

# Generic (polymorphic)
GET    /api/profiles/                   - List all profiles
GET    /api/profiles/{id}/              - Get any profile type
```

---

## Migration Notes

### For New Endpoints
When creating new views/endpoints, use the type-specific serializers:
- Use `RegularProfileSerializer`, `RegularProfileCreateSerializer`, etc. for regular profiles
- Use `BusinessProfileSerializer`, `BusinessProfileCreateSerializer`, etc. for business profiles

### For Existing Endpoints
Legacy serializers (`ProfileSerializer`, `ProfileCreateSerializer`, `ProfileUpdateSerializer`) continue to work for backward compatibility.

---

## Testing

### Testing Regular Profiles
```python
from apps.user_app.models import RegularProfile
from apps.user_app.serializers import RegularProfileCreateSerializer

def test_create_regular_profile(self):
    data = {
        'username': 'test_pet',
        'user': self.user.id,
        'name': 'Test Pet',
        'about': 'A test pet'
    }
    serializer = RegularProfileCreateSerializer(data=data)
    self.assertTrue(serializer.is_valid())
    profile = serializer.save()
    self.assertIsInstance(profile, RegularProfile)
    self.assertEqual(profile.name, 'Test Pet')
```

### Testing Business Profiles
```python
from apps.user_app.models import BusinessProfile
from apps.user_app.serializers import BusinessProfileCreateSerializer

def test_create_business_profile(self):
    data = {
        'username': 'test_business',
        'user': self.user.id,
        'business_name': 'Test Business',
        'business_category': 'VETERINARY'
    }
    serializer = BusinessProfileCreateSerializer(data=data)
    self.assertTrue(serializer.is_valid())
    profile = serializer.save()
    self.assertIsInstance(profile, BusinessProfile)
    self.assertEqual(profile.business_name, 'Test Business')
```

---

## Common Patterns

### Creating a Profile Based on User Choice
```python
def create_profile(request):
    profile_type = request.data.get('profile_type', 'regular')
    
    if profile_type == 'business':
        serializer = BusinessProfileCreateSerializer(data=request.data)
    else:
        serializer = RegularProfileCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        profile = serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)
```

### Updating a Profile
```python
def update_profile(request, profile_id):
    try:
        profile = Profile.objects.select_related(
            'regularprofile', 'businessprofile'
        ).get(id=profile_id)
        
        if hasattr(profile, 'regularprofile'):
            instance = profile.regularprofile
            serializer = RegularProfileUpdateSerializer(
                instance, data=request.data, partial=True
            )
        elif hasattr(profile, 'businessprofile'):
            instance = profile.businessprofile
            serializer = BusinessProfileUpdateSerializer(
                instance, data=request.data, partial=True
            )
        else:
            return Response({'error': 'Invalid profile'}, status=400)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    except Profile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)
```

---

## Benefits of This Architecture

1. **Type Safety**: Each serializer works directly with its specific model
2. **No Conditional Logic**: Clean, readable code without `if hasattr()` checks
3. **Complete Field Support**: All BusinessProfile fields are properly serialized
4. **Better Validation**: Different validation rules for each type
5. **Easier Testing**: Test each type independently
6. **Better API Documentation**: Clear contract for each profile type
7. **Future-Proof**: Easy to add new profile types or fields

---

## Questions?

For questions or issues with the profile serializers, please:
1. Check this guide first
2. Review the serializer code in `apps/user_app/serializers.py`
3. Check the model definitions in `apps/user_app/models.py`
4. Consult with the development team

