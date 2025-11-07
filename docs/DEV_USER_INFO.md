# Development User Credentials

## Overview

This document contains the login credentials for all users included in the development fixture data (`api/fixtures/dev/`). These credentials can be used to authenticate and test various features of the application with pre-populated user accounts.

## Purpose

The development fixtures provide a consistent set of test data that allows developers to:
- Quickly spin up a local environment with realistic data
- Test features from different user perspectives
- Debug issues with specific user scenarios
- Develop and test social features (follows, posts, interactions, etc.)

## How to Use

1. Load the development fixtures using the appropriate script:
   ```bash
   ./scripts/load_db.sh
   ```

2. Use any of the credentials below to authenticate through the API or admin interface

## Credentials

### Admin User

| Field    | Value              |
|----------|-------------------|
| Email    | admin@email.com   |
| Password | adminpassword     |

**Note:** The admin user has superuser privileges and access to the Django admin panel.

---

### Regular Users

| User     | Email                     | Password              |
|----------|---------------------------|-----------------------|
| User 1   | userone@email.com         | useronepassword       |
| User 2   | usertwo@email.com         | usertwopassword       |
| User 3   | userthree@email.com       | userthreepassword     |
| User 4   | userfour@email.com        | userfourpassword      |
| User 5   | userfive@email.com        | userfivepassword      |
| User 6   | usersix@email.com         | usersixpassword       |
| User 7   | userseven@email.com       | usersevenpassword     |
| User 8   | usereight@email.com       | usereightpassword     |
| User 9   | usernine@email.com        | userninepassword      |
| User 10  | userten@email.com         | usertenpassword       |
| User 11  | usereleven@email.com      | userelevenpassword    |
| User 12  | usertwelve@email.com      | usertwelvepassword    |
| User 13  | userthirteen@email.com    | userthirteenpassword  |
| User 14  | userfourteen@email.com    | userfourteenpassword  |
| User 15  | userfifteen@email.com     | userfifteenpassword   |
| User 16  | usersixteen@email.com     | usersixteenpassword   |
| User 17  | userseventeen@email.com   | userseventeenpassword |
| User 18  | usereighteen@email.com    | usereighteenpassword  |
| User 19  | usernineteen@email.com    | usernineteenpassword  |
| User 20  | usertwenty@email.com      | usertwentypassword    |

---

## Security Note

⚠️ **These credentials are for development use only.** Never use these passwords or similar weak passwords in staging or production environments.

**Note:** This data may be updated in the future. Check the fixtures in the `api/fixtures/dev/` directory for the most up to date user options. For new users, all passwords will follow the {email}{password} format - ie: userseventy@email.com would have the password userseventypassword.