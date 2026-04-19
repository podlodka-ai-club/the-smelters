Project: DemoApp

# Share & Download Functionality

## Summary

- Priority: High
- Estimated Duration: 2-3 days
- Complexity: Medium
- User Impact: High

## Context

Enable users to share GIFs via social media and download them locally. This feature enables:
- **Viral Sharing**: Easy distribution across messaging apps and social platforms
- **Local Storage**: Download GIFs for offline access and media library
- **Social Integration**: Share directly to WhatsApp, Telegram, Instagram, etc.
- **Content Export**: Save in high quality for personal use or editing
- **Engagement Multiplier**: Users share with friends, bringing new users to app

### User Stories

1. **As a user**, I want to **share a GIF** via WhatsApp/Telegram/Email, so I can **send it to friends quickly**
2. **As a user**, I want to **download a GIF** to my device, so I can **use it offline or in other apps**
3. **As a user**, I want to **see download progress**, so I can **know when the GIF is ready**
4. **As a user**, I want **download quality options** (preview vs original), so I can **choose between speed and quality**
5. **As a user**, I want **downloaded GIFs in my photo gallery**, so I can **find them easily**
6. **As a user**, I want to **copy a shareable link**, so I can **share with those who don't have the app**

---

## Technical Notes

### Dependencies

**Android Framework APIs** (no additional dependencies):
- `android.content.Intent` (sharing)
- `android.app.DownloadManager` (system download service)
- `androidx.core.content.FileProvider` (secure file sharing)
- `android.content.ClipboardManager` (copy to clipboard)

**Permissions** (manifest):
- `INTERNET` (already exists)
- `WRITE_EXTERNAL_STORAGE` (for Android 10-12)
- `POST_NOTIFICATIONS` (for download notifications - Android 13+)
- `READ_MEDIA_IMAGES` (for Android 13+ scoped storage)

### Architecture

Following the modular Clean Architecture pattern:

```
domain/sharing/
├── model/           ← Download progress models
├── repository/      ← Repository interfaces
├── usecase/         ← Business logic
└── di/              ← DI registration

data/sharing/
├── download/        ← DownloadManager wrapper
├── share/           ← Share manager & utilities
├── mapper/          ← Data transformation
├── repository/      ← Repository implementations
└── di/              ← DI registration

feature/details/
├── DetailScreen.kt  ← Enhanced with share/download buttons
└── DetailViewModel  ← Enhanced with download state
```

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **File Storage** | Android Intent + FileProvider | Secure file sharing |
| **Downloads** | Android DownloadManager | Background downloads |
| **Sharing** | Android Intent API | Share via apps/email |
| **Storage Access** | MediaStore API | Save to device storage |
| **Notifications** | NotificationCompat | Download progress notifications |
| **Permissions** | Runtime Permissions | Android 6+ handling |

---

## Implementation Plan

### Phase 1: File Storage & Permissions (Day 1)

Set up file storage utilities and permission handling:

- **Create file storage utility layer** (`data/sharing/`)
  - Get GiphySearch directory in app's cache and Pictures folders
  - Generate unique filenames with timestamps
  - Get file URIs via FileProvider for secure sharing
  - Handle cleanup of old downloads

- **Setup FileProvider** in AndroidManifest
  - Configure paths for cache and external storage
  - Ensure proper file access permissions

- **Implement runtime permissions** handling
  - Check permission status before operations
  - Request permissions with rationale if needed
  - Handle permission denials gracefully
  - Support different Android versions (6-13+)

### Phase 2: Download Functionality (Day 1-2)

Implement background download management:

- **Create download manager wrapper** (`data/sharing/download/`)
  - Wrapper around Android's DownloadManager
  - Track download progress and status
  - Return Flow of download progress updates
  - Support cancellation of ongoing downloads
  - Handle download completion and errors

- **Create download repository** (`domain/sharing/` + `data/sharing/`)
  - Interface: Download contract definition
  - Implementation: Delegate to download manager
  - Methods: start download, cancel, get status, get history

- **Create use cases** (`domain/sharing/usecase/`)
  - `DownloadGifUseCase`: Start GIF download with quality selection
  - Track downloads and expose progress

### Phase 3: Sharing Functionality (Day 2)

Implement sharing across apps:

- **Create share manager** (`data/sharing/share/`)
  - Generate share intents for URLs
  - Share downloaded files via FileProvider
  - Copy shareable links to clipboard
  - Create Giphy.com shareable URL format

- **Create share repository** (`domain/sharing/` + `data/sharing/`)
  - Interface: Sharing contract definition
  - Implementation: Delegate to share manager
  - Methods: share URL, share file, copy link

- **Create use cases** (`domain/sharing/usecase/`)
  - `ShareGifUseCase`: Share GIF URL directly
  - `CopyShareLinkUseCase`: Copy Giphy URL to clipboard

### Phase 4: UI Integration (Day 2-3)

Enhance existing DetailScreen with sharing features:

- **Update DetailScreen composable**
  - Add action buttons row below GIF image
  - Include: Share button, Download button, More options menu
  - Display download progress indicator during downloads
  - Show success/error toast messages

- **Update DetailViewModel**
  - Add download progress state to UI state
  - Add methods for handling share/download actions
  - Manage download cancellation
  - Handle permission requests and results

- **Add quality selection dialog**
  - Offer choice between preview quality (smaller, faster) and original quality
  - Remember user preference
  - Show estimated file size for each quality

### Phase 5: Dependency Injection & Integration (Day 3)

Set up module registration:

- **Create domain module** with use case registrations
- **Create data module** with repository implementations
- **Update DetailViewModel DI** to inject new use cases
- **Update `AppModule`** to include sharing modules
- **Register managers** as singletons for proper lifecycle management

---

## UI/UX Details

### DetailScreen Action Buttons

Add button row below GIF image:
- **Share Button**: Icon + label, opens share chooser
- **Download Button**: Icon + label with progress indicator
- **More Options**: Menu with copy link option
- **Cancel Download**: Button shown during active downloads

### Download Dialog

When user taps download:
- Show dialog with quality options
- Display file size estimates
- Offer Preview (faster) vs Original (full quality)
- Cancel/Confirm buttons

### Download Progress

While downloading:
- Show circular or linear progress indicator
- Display percentage and size downloaded
- Show estimated time remaining
- Allow cancellation

### Download Completion

When download finishes:
- Show success toast/snackbar
- Message: "Downloaded to Pictures/GiphySearch/"
- Optional: Tap to open folder in Files app

### Error Handling

Display appropriate messages for:
- No internet connection
- Storage full
- Permission denied
- Download interrupted

---

## Download Management

### Download Paths

**Primary**: `Pictures/GiphySearch/` (MediaStore API, visible in Photos app)
**Fallback**: App's cache directory (auto-cleaned)

### File Organization

Naming convention: `giphysearch_[gif-id]_[timestamp].[format]`
Example: `giphysearch_abc123_20240419123456.gif`

### Storage Considerations

- Handle Android 10+ scoped storage requirements
- Use MediaStore for Pictures folder access
- Implement cleanup for old downloads (configurable, default 30 days)
- Provide manual cache clearing option in settings

---

## Sharing Features

### Share Types

1. **Share URL**: Instant share of Giphy link (no download)
2. **Share File**: Share downloaded local file via FileProvider
3. **Copy Link**: Copy Giphy URL to clipboard

### Share Targets

System will show all available apps:
- Messaging: WhatsApp, Telegram, Signal, Messenger
- Email: Gmail, Outlook, Mail
- Social: Twitter, Instagram (as DM)
- System: Nearby Share, Bluetooth

---

## Permissions Strategy

### Required Permissions

By Android Version:
- **Android 6-9**: WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
- **Android 10-12**: Use MediaStore API or WRITE_EXTERNAL_STORAGE
- **Android 13+**: READ_MEDIA_IMAGES, POST_NOTIFICATIONS

### Graceful Degradation

- Share always works (no permission needed for URL)
- Download to cache if storage permission denied
- Show user-friendly message explaining permission needs
- Provide link to settings for permission grant

---

## Error Handling

### Common Scenarios

| Scenario | User Message | Recovery |
|----------|--------------|----------|
| No Internet | "Check internet connection" | Retry when online |
| Storage Full | "Not enough storage space" | Free space or use preview quality |
| Permission Denied | "Storage permission required" | Show settings link |
| App Not Installed | "App not available" | Show other share options |
| Corrupted Download | "File corrupted, try again?" | Delete & retry |

---

## Data Models

### DownloadProgress

- `downloadId`: Long identifier
- `status`: PENDING, RUNNING, PAUSED, SUCCESSFUL, FAILED, CANCELLED
- `bytesDownloaded`, `totalBytes`: Progress tracking
- `progress`: 0-100 percentage
- `filePath`: Path to downloaded file
- `error`: Error message if failed

### DownloadQuality

- `PREVIEW`: Smaller file, faster download
- `ORIGINAL`: Full quality, larger file

---

## Coding Conventions Alignment

✅ **Clean Architecture**: Separate domain/data layers
✅ **MVVM Pattern**: DetailViewModel enhanced with download/share state
✅ **Coroutines**: Flow for download progress
✅ **DI Pattern**: Koin modules with proper registration
✅ **Async Operations**: No blocking calls on UI thread
✅ **Permissions**: Runtime permission handling
✅ **Error Handling**: Result wrapper for operations

---

## Testing Strategy

- Unit tests for share manager
- Unit tests for download manager
- Unit tests for use cases
- Integration tests for repository
- Permission handling tests
- UI tests for button interactions

---

## Success Criteria

✅ Users can download GIFs in multiple qualities
✅ Downloads appear in Pictures/GiphySearch folder
✅ Download progress shows accurate percentage
✅ Users can cancel downloads
✅ Users can share GIFs via any app
✅ Share works with URL or file
✅ Copy link to clipboard works
✅ Proper error messages for failures
✅ Permissions handled gracefully
✅ Download notifications show progress

---

## Future Enhancements

- 📤 **Cloud Upload**: Save downloads to Google Drive/Dropbox
- 🎬 **Video Conversion**: Convert GIF to MP4/WebM
- 👥 **Social Sharing**: Direct APIs for social platforms
- 📧 **Email Integration**: Email GIF directly from app
- 📊 **Share Analytics**: Track most-shared GIFs
- 📦 **Batch Download**: Download multiple GIFs at once
- 🎨 **Gallery Enhancement**: Custom folder in photo gallery
