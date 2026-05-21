# Test Coverage Summary

> **Total: 562 tests across 62 test files - all passing**
> Server Frontend: 174 tests (22 files) | Server Backend: 106 tests (11 files) | Desktop Frontend: 223 tests (23 files) | Desktop Backend: 59 tests (7 files)

---

## Server Frontend Tests (174 tests)

### `apiFetch.test.ts` - 13 tests

API fetch wrapper with CSRF protection and credentials.

- Prepends API URL to path
- Includes credentials
- Adds CSRF header on POST
- Adds CSRF header on DELETE
- Does NOT add CSRF on GET
- Sets Content-Type for string body
- Uses no-store cache
- Adds CSRF header on PUT
- Adds CSRF header on PATCH
- Does not override existing Content-Type header
- Does not set Content-Type when body is not a string
- Returns the raw Response object
- Handles empty CSRF cookie gracefully

### `AuthContext.test.tsx` - 12 tests

Authentication context with user state, roles, logout, and refresh.

- Shows loading state initially
- Sets user when `/auth/me` returns 200
- Sets user to null when `/auth/me` returns 401
- Handles fetch error gracefully
- Identifies issuer role correctly
- Identifies root admin correctly
- Identifies regular user correctly
- Sets user to null after logout
- Calls `/auth/logout` endpoint with POST
- Handles logout error gracefully
- refreshUser re-fetches and updates context
- Throws when useAuth is used outside AuthProvider

### `ThemeContext.test.tsx` - 8 tests

Dark/light theme toggle with localStorage persistence.

- Defaults to light theme
- Reads stored theme from localStorage
- Toggles theme and saves to localStorage
- Toggles back to light after two toggles
- Adds dark class to documentElement when toggled to dark
- Removes dark class when toggled back to light
- Respects system dark mode preference
- Throws when useTheme is used outside ThemeProvider

### `LoginPage.test.tsx` - 9 tests

Login page with bootstrap detection, passkey auth, and role-based redirects.

- Renders login button
- Redirects to bootstrap when needed
- Redirects authenticated admin to `/admin`
- Redirects issuer with event to `/calendar`
- Redirects regular user with event to `/calendar`
- Redirects user without event to `/admin`
- Shows heading and subtitle
- Button is not disabled by default
- Stays on login when bootstrap check fails

### `BootstrapPage.test.tsx` - 12 tests

Initial setup page with WebAuthn passkey registration.

- Shows checking status initially
- Shows register button when bootstrap is needed
- Shows already-done message when bootstrap not needed
- Shows error when bootstrap check fails
- Shows error on network failure
- Handles successful passkey registration
- Navigates to login after successful registration
- Shows error when registration begin fails
- Returns to ready state when user cancels passkey prompt
- Shows Welcome heading
- Retries on error
- Navigates to login from already-done state

### `reauth.test.ts` - 9 tests

Re-authentication ceremony and 403 retry logic.

- Completes the full reauth ceremony
- Throws when begin endpoint fails
- Throws with default message when begin returns no detail
- Throws when complete endpoint fails
- Propagates browser passkey error
- Returns response directly when not 403
- Retries action after reauth on 403 with reauth-required detail
- Returns 403 as-is when detail is not reauth-required
- Propagates reauth error on retry

### `UIComponents.test.tsx` - 31 tests

Core UI primitives: Button, Card, Input.

- **Button (13):** renders children, variant classes (primary/secondary/outline/ghost/danger with inline styles), click events, disabled state, fullWidth, size classes (sm/lg), custom className, does not fire click when disabled
- **Card (5):** renders children, hover class, custom className, no hover class when false, border/background classes
- **Input (10):** renders with/without label, error message + styling, helper text, hides helper when error present, HTML attributes passthrough, disabled state, error/normal border classes, generated/provided id

### `Logo.test.tsx` - 9 tests

Themed logo with light/dark mode, links, and custom colours.

- Renders an image with alt text
- Uses light logo in light mode
- Uses dark logo in dark mode
- Applies custom height
- Wraps in link when href is provided
- Does not wrap in link when href is not provided
- Applies custom className
- Uses custom colours when provided
- Falls back to brand colours when custom colours are null

### `ThemeToggle.test.tsx` - 4 tests

Theme toggle button with Moon/Sun icons.

- Renders a button with toggle theme label
- Shows Moon icon in light mode
- Shows Sun icon in dark mode
- Calls toggleTheme on click

### `Footer.test.tsx` - 7 tests

Page footer with copyright, links, and version.

- Renders copyright notice with current year
- Renders About link
- Renders Privacy link
- Renders Terms link
- Renders Disclaimer link
- Renders footer element
- Renders version placeholder

### `ActivationCampaignCard.test.tsx` - 4 tests

Server activation campaign confidence card.

- No-user state and primary action
- Progress bar and count row
- Compact needs-attention list
- Generate-links action routing

### `activationCampaign.test.ts` - 6 tests

Server activation campaign derivation helpers.

- Empty, blocked, in-progress, and healthy summaries
- Activation filters
- Human-readable timestamp formatting

### `AnnouncementBanner.test.tsx` - 8 tests

Announcement banner with fetch, dismiss, and sessionStorage persistence.

- Renders announcements from API
- Renders announcement body when present
- Renders nothing when no announcements
- Renders nothing when API fails
- Dismisses an announcement on click
- Saves dismissed IDs to sessionStorage
- Loads previously dismissed IDs from sessionStorage
- Does not fetch when eventId is 0

### `DeleteMyDataLink.test.tsx` - 12 tests

Data deletion request modal with auth gating.

- Renders delete button when authenticated
- Renders nothing when not authenticated
- Opens modal on click
- Modal has cancel and submit buttons
- Closes modal on cancel
- Closes modal on close button
- Submits deletion request successfully
- Shows error on failed submission
- Shows generic error when response has no detail
- Shows network error message
- Shows loading state during submission
- Displays explanation steps in the modal

### `WebEditReviewModal.test.tsx` - 4 tests

Server web-edit review modal and revert actions.

- Review list grouping and original/current comparison
- Single web-edit revert confirmation and API payload
- Selected bulk revert payload
- Permission-aware hiding of revert controls

### `webEditTaskMarkers.test.tsx` - 2 tests

Server calendar web-edit task marker styling.

- Uses the desktop-style pencil indicator on calendar tasks
- Uses the same pencil indicator in the task detail modal

### `webEditConfidence.test.ts` - 4 tests

Server web-edit confidence helper behaviour.

- Formats human-readable edit timestamps
- Summarises healthy, review, and unknown web-edit states
- Describes task-level web edits without exposing raw data
- Groups review-list items by schedule day

### `WebEditSummaryBar.test.tsx` - 4 tests

Compact admin web-edit operations summary.

- Renders one compact review summary and review action
- Shows grouped details only after expansion
- Filters edits to the current user
- Shows a quiet loading state

---

## Server Backend Tests (106 tests)

FastAPI server backend behaviour for activation, admin operations, calendar data, GDPR, history, notifications, publishing, security, middleware, and web-edit visibility.

- `test_admin_activation.py` - 8 tests for activation links and activation flows
- `test_admin_events.py` - 9 tests for event creation, listing, deletion, and publish-secret regeneration
- `test_admin_users.py` - 20 tests for user management, activation campaign metadata, and role permissions
- `test_calendar.py` - 3 tests for calendar data and authentication
- `test_gdpr.py` - 9 tests for data export and deletion requests
- `test_history.py` - 12 tests for publish snapshots and history access
- `test_middleware.py` - 6 tests for security middleware behaviour
- `test_notifications.py` - 7 tests for announcements and push subscriptions
- `test_publish.py` - 6 tests for server publish ingestion
- `test_security.py` - 16 tests for authentication and security controls
- `test_web_edits.py` - 10 tests for event-level web-edit state, review metadata, issuer access, calendar task markers, and web-edit revert actions

---

## Desktop Frontend Tests (223 tests)

### `dateFormat.test.ts` - 7 tests

Date formatting utilities (Swiss DD.MM.YYYY format).

- formatDateShort formats as DD.MM.YYYY
- formatDateWithWeekday prepends weekday abbreviation
- formatDateLong uses full weekday name
- formatDateTime appends HH:MM time
- Handles various date strings correctly
- Pads single-digit days and months
- Handles edge-case dates

### `startupScreen.test.ts` - 7 tests

Desktop startup integrity checklist helper.

- Renders the compact Integrity, Backend, and Interface checklist
- Shows pending, checking, complete, warning, failed, and skipped states
- Escapes status and step detail text before rendering
- Maps running, development, successful, and failed integrity states

### `securityPolicy.test.ts` - 4 tests

Packaged desktop Content Security Policy.

- Allows Next.js inline bootstrap scripts without allowing eval
- Allows local backend and Google integration endpoints
- Does not depend on remote Google font stylesheets
- Keeps renderer hardening directives enabled

### `userDataPaths.test.ts` - 5 tests

Desktop user-data preservation during app updates.

- Stores persistent data under the stable user-data directory
- Creates only the data directory before backend startup
- Reuses existing database and key paths without overwriting files
- Passes absolute persistent paths to the backend environment
- Does not log encryption key contents

### `importPreview.test.tsx` - 7 tests

Safe import preview helpers and modal.

- Builds a blocking validation result for invalid JSON
- Formats recognised import entity counts
- Uses application-settings wording when no project records are present
- Renders project counts, schedule metadata, and the new-project action
- Disables confirmation when blocking errors exist
- Shows warnings without blocking the import action
- Calls confirm, cancel, and choose-another handlers

### `publishPreview.test.tsx` - 9 tests

Publish preview derivation and modal confirmation.

- Summarises selected-day publishing without implying full-event publishing
- Shows ready and skipped days for all-day publishing
- Blocks publishing when no destination is configured
- Shows already-published timestamps in local time
- Maps publish target labels without exposing credentials
- Renders the calm preview summary and precise publish action
- Disables confirmation when no day is publishable
- Calls confirm and cancel handlers
- Hides day details while keeping the main confirmation summary

### `publishStateApi.test.ts` - 4 tests

Backend-backed desktop publish-state API client.

- Fetches publish state from the backend instead of localStorage
- Saves successful publish metadata with day records
- Records failed publish metadata for affected days
- Clears publish metadata through the backend

### `presentationModePolish.test.tsx` - 5 tests

Presentation-mode polish for calendar, task detail slides, and navigation.

- Renders presentation calendars without the editing toolbar
- Passes compact density through the presentation calendar slide
- Shows readable task detail hierarchy for presentation slides
- Keeps the presentation task sidebar compact and task-focused
- Keeps shortcut help available without showing it by default

### `environment.test.ts` - 3 tests

Desktop app detection and API URL resolution.

- isDesktopApp returns true when window.electron exists
- isDesktopApp returns false in browser
- getApiUrl returns localhost for desktop

### `AuthContext.test.tsx` - 3 tests

Static local user context (no login needed in desktop).

- Provides a static local user (id=0, username="local")
- isLoading is always false
- Works without a provider (uses default context value)

### `EventContext.test.tsx` - 7 tests

Event selection with API fetching and sessionStorage persistence.

- Fetches events on mount
- Starts with no selection
- Selects an event and persists to sessionStorage
- Clears selection and removes from sessionStorage
- Handles fetch failure gracefully
- Clears stale selection when event no longer exists
- Throws when useEvent is used outside EventProvider

### `ThemeContext.test.tsx` - 8 tests

Theme fetching from API, CSS custom property application, dark mode.

- Fetches and applies theme on mount
- Applies CSS custom properties to document root (7 variables)
- Applies dark class when dark_mode is "dark"
- Removes dark class in light mode
- Persists dark-mode preference to localStorage
- Handles fetch failure gracefully
- Skips secondary/tertiary when null
- Throws when useTheme is used outside ThemeProvider

### `ToastContext.test.tsx` - 5 tests

Toast notification state management with auto-dismiss.

- Adds a toast
- Removes a toast manually
- Auto-dismisses after 4 seconds (fake timers)
- Supports multiple toasts
- Throws when useToast is used outside ToastProvider

### `ToastContainer.test.tsx` - 7 tests

Toast notification UI rendering and dismiss interaction.

- Renders nothing when there are no toasts
- Renders a single toast
- Renders multiple toasts
- Applies success variant styling (bg-green-600)
- Applies error variant styling (bg-red-600)
- Applies info variant styling (bg-blue-600)
- Calls removeToast when dismiss button is clicked

### `UIComponents.test.tsx` - 19 tests

Core UI primitives: Button, Card, Modal.

- **Button (12):** renders children, fires onClick, disabled state, fullWidth class, size classes (sm/lg), primary/danger variant inline styles, outline/ghost variant classes, custom className, does not fire when disabled
- **Card (3):** renders children, hover styles, custom className
- **Modal (4):** renders when open, hidden when closed, Escape closes, backdrop click closes, content click does not close

### `UIComponentsExtra.test.tsx` - 45 tests

Extended UI components: Input, Select, Badge, Spinner, Switch, Divider, IconButton.

- **Input (9):** label rendering, no label, error message + styling, helper text, helper hidden on error, provided/generated id, disabled state, custom className
- **Select (8):** label + options rendering, no label, error message + styling, provided/generated id, numeric option values, disabled state
- **Badge (7):** renders children, neutral variant bg, non-neutral inline styles, custom className, danger/primary/default variants
- **Spinner (5):** animate-spin class, sm/md/lg size classes, custom className
- **Switch (7):** role=switch, aria-checked reflects state, onChange toggle, labels rendering, disabled state, no onChange when disabled
- **Divider (2):** renders hr element, custom className
- **IconButton (7):** renders children, ghost/primary/secondary variants, size classes (sm/md/lg), disabled state, onClick

### `DataTable.test.tsx` - 11 tests

Generic data table with headers, rows, loading, empty states, and double-click.

- Renders column headers
- Renders data rows
- Shows empty message when data is empty
- Shows default empty message
- Shows empty sub-message
- Shows spinner when loading
- Fires onRowDoubleClick for double-click-enabled columns
- Does not fire onRowDoubleClick for non-enabled columns
- Shows "Double-click to edit" title on enabled cells
- Uses custom render function
- Uses string keyExtractor

### `gcalColors.test.ts` - 12 tests

Google Calendar colour palette and utilities.

- GCAL_COLOR_META has 11 entries
- Each entry has label, order, background, foreground
- Tomato is id "11" with #D50000
- Banana is id "5" with black foreground
- GCAL_PALETTE has 11 colours sorted by display order
- Tomato first, Graphite last
- Each palette entry has id, background, foreground
- sortedGcalColors sorts by display order
- Does not mutate the original array
- Puts unknown IDs at the end
- gcalColorLabel returns label for known ID
- gcalColorLabel returns fallback for unknown ID

### `calendarTaskUtils.test.ts` - 20 tests

Time conversion and TaskInstance-to-CalendarTask mapping.

- **minutesToTime (6):** 0â†’00:00, 60â†’01:00, 90â†’01:30, 720â†’12:00, 1439â†’23:59, pads single digits
- **timeToMinutes (5):** 00:00â†’0, 01:30â†’90, 12:00â†’720, 23:59â†’1439, handles single-digit format
- **Roundtrip (1):** minutesToTime â†” timeToMinutes for 9 values
- **toCalendarTask (6):** basic field mapping, uses final over optimised, template name fallback, multiple persons, undefined times, unknown task type
- **instancesToCalendarTasks (2):** filters by eventId + optimised/final, empty array

### `optimizationApi.test.ts` - 8 tests

Optimization job API client (start, poll, list).

- startOptimization sends POST with JSON body
- Throws on HTTP error with detail message
- Handles 422 validation errors with detail array
- Handles error when JSON parsing fails
- getJobStatus fetches with correct URL
- getJobStatus throws on HTTP error
- getJobsForEvent fetches jobs list
- getJobsForEvent throws on HTTP error

---

## Desktop Backend Tests (59 tests)

FastAPI desktop backend behaviour, data management, optimisation normalisation, Unicode handling, and MP-Backend publishing.

- `test_crud.py` - 21 tests for authentication, events, locations, people, tasks, status updates, and cascade deletion
- `test_data_management.py` - 14 tests for export, import, preview validation, safe mutation, and optional-table deletion
- `test_mp_backend_publish.py` - 3 tests for selected-day MP-Backend publish scoping, all-event fallback, and invalid date rejection
- `test_normalizer.py` - 8 tests for time conversion, normalisation, capabilities, unavailability, and fatigue scores
- `test_optimization.py` - 4 tests for optimisation and job endpoints
- `test_publish_state.py` - 6 tests for persistent publish state, per-day failures, clearing, event deletion, and missing-event rejection
- `test_unicode_and_identifier_validation.py` - 3 tests for Unicode names and strict machine-name validation
