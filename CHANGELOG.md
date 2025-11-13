# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.5.8-bmcd04] - 2025-11-13

### Added
- **Subtitle Embedding Feature** - Added ability to embed downloaded subtitles directly into MP4 video files
  - New `add_subtitles` configuration option in Downloads settings
  - Implemented FFmpegEmbedSubtitle postprocessor in yt-dlp handler
  - Added toggle control in Settings → Application page
  - Subtitle embedding is disabled by default for backwards compatibility
  - Commits: cf3b3891

### Fixed
- **Query Variable Bug** - Fixed incorrect variable reference (`query` → `queries`) in channel video query logic that could cause AttributeError
  - File: `backend/channel/src/remote_query.py`
  - Commits: 47b4332e

- **Download Progress Safety** - Added defensive programming to prevent KeyError when processing yt-dlp responses
  - Now uses `.get()` method with fallback to "Processing" instead of direct dictionary access
  - Prevents crashes when `info_dict` or `title` is unavailable during download progress updates
  - File: `backend/download/src/yt_dlp_handler.py`
  - Commits: c7905309

### Changed
- **Frontend Tooling** - Added missing `@eslint/js` v9.33.0 dependency for ESLint support
  - Improved code formatting consistency
  - Commits: c800c278

### Technical Details

#### Files Modified
**Backend:**
- `backend/appsettings/serializers.py` - Added `add_subtitles` field
- `backend/appsettings/src/config.py` - Added subtitle embedding configuration
- `backend/download/src/yt_dlp_handler.py` - Implemented subtitle embedding logic and safety improvements
- `backend/channel/src/remote_query.py` - Fixed variable reference bug

**Frontend:**
- `frontend/package.json` - Added @eslint/js dependency
- `frontend/package-lock.json` - Updated lockfile
- `frontend/src/api/loader/loadAppsettingsConfig.ts` - Added TypeScript type for add_subtitles
- `frontend/src/stores/AppSettingsStore.ts` - Added state management for subtitle embedding
- `frontend/src/pages/SettingsApplication.tsx` - Added UI toggle and formatting improvements

#### Migration Notes
- No database migrations required
- New `add_subtitles` setting defaults to `false` (disabled)
- Existing configurations will continue to work without changes

## [v0.5.8-bmcd03] - 2025-09-XX

### Added
- Thread-safe startup timestamp handling
- Full metadata embedding functionality
- Deno support added to build process
- Frontend caching reload improvements

### Changed
- Bumped Django version for security updates
- Updated frontend dependencies
- Pinned yt-dlp to master branch

### Fixed
- Fixed unittest failures in startup timestamp handling
- Fixed embed error handling
- Fixed upload_date format handling (#1052)

---

## Previous Versions

For changes in versions prior to v0.5.8-bmcd03, please refer to the git commit history or original upstream repository.

---

**Note:** This changelog tracks changes specific to the bmcdonough fork. For upstream Tube Archivist changes, see the [official repository](https://github.com/tubearchivist/tubearchivist).
