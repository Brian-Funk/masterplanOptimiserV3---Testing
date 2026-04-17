# Test Coverage Summary

> **Total: 289 tests across 25 test files — all passing**  
> Server Frontend: 134 tests (12 files) | Desktop Frontend: 155 tests (13 files)

---

## Server Frontend Tests (134 tests)

### `apiFetch.test.ts` — 13 tests

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

### `AuthContext.test.tsx` — 12 tests

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

### `ThemeContext.test.tsx` — 8 tests

Dark/light theme toggle with localStorage persistence.

- Defaults to light theme
- Reads stored theme from localStorage
- Toggles theme and saves to localStorage
- Toggles back to light after two toggles
- Adds dark class to documentElement when toggled to dark
- Removes dark class when toggled back to light
- Respects system dark mode preference
- Throws when useTheme is used outside ThemeProvider

### `LoginPage.test.tsx` — 9 tests

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

### `BootstrapPage.test.tsx` — 12 tests

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

### `reauth.test.ts` — 9 tests

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

### `UIComponents.test.tsx` — 31 tests

Core UI primitives: Button, Card, Input.

- **Button (13):** renders children, variant classes (primary/secondary/outline/ghost/danger with inline styles), click events, disabled state, fullWidth, size classes (sm/lg), custom className, does not fire click when disabled
- **Card (5):** renders children, hover class, custom className, no hover class when false, border/background classes
- **Input (10):** renders with/without label, error message + styling, helper text, hides helper when error present, HTML attributes passthrough, disabled state, error/normal border classes, generated/provided id

### `Logo.test.tsx` — 9 tests

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

### `ThemeToggle.test.tsx` — 4 tests

Theme toggle button with Moon/Sun icons.

- Renders a button with toggle theme label
- Shows Moon icon in light mode
- Shows Sun icon in dark mode
- Calls toggleTheme on click

### `Footer.test.tsx` — 7 tests

Page footer with copyright, links, and version.

- Renders copyright notice with current year
- Renders About link
- Renders Privacy link
- Renders Terms link
- Renders Disclaimer link
- Renders footer element
- Renders version placeholder

### `AnnouncementBanner.test.tsx` — 8 tests

Announcement banner with fetch, dismiss, and sessionStorage persistence.

- Renders announcements from API
- Renders announcement body when present
- Renders nothing when no announcements
- Renders nothing when API fails
- Dismisses an announcement on click
- Saves dismissed IDs to sessionStorage
- Loads previously dismissed IDs from sessionStorage
- Does not fetch when eventId is 0

### `DeleteMyDataLink.test.tsx` — 12 tests

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

---

## Desktop Frontend Tests (155 tests)

### `dateFormat.test.ts` — 7 tests

Date formatting utilities (European DD.MM.YY format).

- formatDateShort formats as DD.MM.YY
- formatDateWithWeekday prepends weekday abbreviation
- formatDateLong uses full weekday name
- formatDateTime appends HH:MM time
- Handles various date strings correctly
- Pads single-digit days and months
- Handles edge-case dates

### `environment.test.ts` — 3 tests

Desktop app detection and API URL resolution.

- isDesktopApp returns true when window.electron exists
- isDesktopApp returns false in browser
- getApiUrl returns localhost for desktop

### `AuthContext.test.tsx` — 3 tests

Static local user context (no login needed in desktop).

- Provides a static local user (id=0, username="local")
- isLoading is always false
- Works without a provider (uses default context value)

### `EventContext.test.tsx` — 7 tests

Event selection with API fetching and sessionStorage persistence.

- Fetches events on mount
- Starts with no selection
- Selects an event and persists to sessionStorage
- Clears selection and removes from sessionStorage
- Handles fetch failure gracefully
- Clears stale selection when event no longer exists
- Throws when useEvent is used outside EventProvider

### `ThemeContext.test.tsx` — 8 tests

Theme fetching from API, CSS custom property application, dark mode.

- Fetches and applies theme on mount
- Applies CSS custom properties to document root (7 variables)
- Applies dark class when dark_mode is "dark"
- Removes dark class in light mode
- Persists dark-mode preference to localStorage
- Handles fetch failure gracefully
- Skips secondary/tertiary when null
- Throws when useTheme is used outside ThemeProvider

### `ToastContext.test.tsx` — 5 tests

Toast notification state management with auto-dismiss.

- Adds a toast
- Removes a toast manually
- Auto-dismisses after 4 seconds (fake timers)
- Supports multiple toasts
- Throws when useToast is used outside ToastProvider

### `ToastContainer.test.tsx` — 7 tests

Toast notification UI rendering and dismiss interaction.

- Renders nothing when there are no toasts
- Renders a single toast
- Renders multiple toasts
- Applies success variant styling (bg-green-600)
- Applies error variant styling (bg-red-600)
- Applies info variant styling (bg-blue-600)
- Calls removeToast when dismiss button is clicked

### `UIComponents.test.tsx` — 19 tests

Core UI primitives: Button, Card, Modal.

- **Button (12):** renders children, fires onClick, disabled state, fullWidth class, size classes (sm/lg), primary/danger variant inline styles, outline/ghost variant classes, custom className, does not fire when disabled
- **Card (3):** renders children, hover styles, custom className
- **Modal (4):** renders when open, hidden when closed, Escape closes, backdrop click closes, content click does not close

### `UIComponentsExtra.test.tsx` — 45 tests

Extended UI components: Input, Select, Badge, Spinner, Switch, Divider, IconButton.

- **Input (9):** label rendering, no label, error message + styling, helper text, helper hidden on error, provided/generated id, disabled state, custom className
- **Select (8):** label + options rendering, no label, error message + styling, provided/generated id, numeric option values, disabled state
- **Badge (7):** renders children, neutral variant bg, non-neutral inline styles, custom className, danger/primary/default variants
- **Spinner (5):** animate-spin class, sm/md/lg size classes, custom className
- **Switch (7):** role=switch, aria-checked reflects state, onChange toggle, labels rendering, disabled state, no onChange when disabled
- **Divider (2):** renders hr element, custom className
- **IconButton (7):** renders children, ghost/primary/secondary variants, size classes (sm/md/lg), disabled state, onClick

### `DataTable.test.tsx` — 11 tests

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

### `gcalColors.test.ts` — 12 tests

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

### `calendarTaskUtils.test.ts` — 20 tests

Time conversion and TaskInstance-to-CalendarTask mapping.

- **minutesToTime (6):** 0→00:00, 60→01:00, 90→01:30, 720→12:00, 1439→23:59, pads single digits
- **timeToMinutes (5):** 00:00→0, 01:30→90, 12:00→720, 23:59→1439, handles single-digit format
- **Roundtrip (1):** minutesToTime ↔ timeToMinutes for 9 values
- **toCalendarTask (6):** basic field mapping, uses final over optimised, template name fallback, multiple persons, undefined times, unknown task type
- **instancesToCalendarTasks (2):** filters by eventId + optimised/final, empty array

### `optimizationApi.test.ts` — 8 tests

Optimization job API client (start, poll, list).

- startOptimization sends POST with JSON body
- Throws on HTTP error with detail message
- Handles 422 validation errors with detail array
- Handles error when JSON parsing fails
- getJobStatus fetches with correct URL
- getJobStatus throws on HTTP error
- getJobsForEvent fetches jobs list
- getJobsForEvent throws on HTTP error
