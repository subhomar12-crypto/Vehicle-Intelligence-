# KIMI PROMPT: Android App Fixes (Separate from Server Phases)

## Your Role
You are fixing minor issues in the PREDICT Android app to ensure compatibility with the server after Phase 1 and Phase 2 server fixes are applied. These are small, targeted changes - do NOT refactor or restructure anything else.

## Project Location
`C:\New APK\`

## IMPORTANT: Only make the changes listed below. Do NOT modify anything else.

---

## FIX 1: FCM Endpoint Path Inconsistency (CRITICAL)

### Problem
Two files register FCM tokens but use different endpoint paths:
- `EnhancedPredictApiService.kt` uses: `@POST("fcm/register")` (relative, no `/api` prefix)
- `PredictFirebaseService.kt` hardcodes: `URL("$serverUrl/api/fcm/register")` (absolute with `/api`)

These don't match. The server's FCM endpoint will be at `/api/v1/fcm/register` (mounted under the v1 API router).

### Fix

**File: `app/src/main/java/com/predict/app/network/PredictFirebaseService.kt`**

Find lines ~104 and ~140 where it hardcodes the URL:
```kotlin
URL("$serverUrl/api/fcm/register")
```

Change both occurrences to use the Retrofit service instead of raw URL construction. If that's not feasible (because it's in a non-Retrofit context like a Firebase service), change the path to match the correct server route:
```kotlin
URL("$serverUrl/api/v1/fcm/register")
```

**File: `app/src/main/java/com/predict/app/network/EnhancedPredictApiService.kt`**

Find the FCM registration endpoint:
```kotlin
@POST("fcm/register")
```

Change to:
```kotlin
@POST("api/v1/fcm/register")
```

Both files must use the SAME path.

---

## FIX 2: Verify AI Smart Chat Path

### Check
**File: `app/src/main/java/com/predict/app/network/PredictApiService.kt`**

Verify this endpoint exists:
```kotlin
@POST("/api/ai/smart-chat")
```

The server will add `/ai/smart-chat` as an alias for `/ai/chat`. Confirm the Android path matches. If the server mounts the AI router at `/api/v1/ai`, then the full path would be `/api/v1/ai/smart-chat`. Check which prefix pattern the Android app uses for other AI endpoints in the same file and make sure smart-chat matches.

If the other AI endpoints in the same file use:
- `/api/ai/status` -> then `/api/ai/smart-chat` is correct
- `/api/v1/ai/status` -> then change to `/api/v1/ai/smart-chat`

The key rule: **all AI endpoints must use the same prefix**.

---

## FIX 3: Standardize Path Slashes (Low Priority, Cosmetic)

### Problem
`EnhancedPredictApiService.kt` mixes relative and absolute paths:
```kotlin
@POST("api/register")     // relative (no leading slash)
@POST("api/telemetry")    // relative
@GET("api/app/version")   // relative
@POST("fcm/register")     // relative BUT missing api/ prefix
```

### Fix
Ensure all paths in `EnhancedPredictApiService.kt` consistently use the same pattern. Since Retrofit appends relative paths to the base URL, and the base URL is `https://predict.previlium.com/`, paths like `api/v1/fcm/register` will resolve correctly.

Go through the file and verify all endpoints have the correct `api/` or `api/v1/` prefix based on what the server expects.

---

## VERIFICATION

After fixes:
1. Build the Android app (no compile errors)
2. The FCM token registration should use ONE consistent path
3. AI smart-chat endpoint path should match server

---

## STOP AFTER THESE FIXES
These are the only Android changes needed. Do NOT modify any UI, business logic, or other network calls. Present the changed files for review.
