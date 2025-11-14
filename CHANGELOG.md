# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.5.8-bmcd03] - 2025-11-14

### Added
- **Custom yt-dlp Extractor Arguments Support** - Added ability to pass extractor-specific parameters to yt-dlp at runtime
  - New `extractor_args` configuration field in Downloads settings
  - Implemented `ExtractorArgsParser` class following yt-dlp's official parsing logic
  - Supports multiple extractors, multiple arguments, and complex value formats
  - Format: `EXTRACTOR1:ARG1=VAL1,VAL2;ARG2=VAL3 EXTRACTOR2:ARG3=VAL4`
  - Automatic parsing and merging into yt-dlp's extractor_args option
  - Comprehensive logging of applied arguments for debugging
  - Commits: 3f529bdb, daf38fc0, 52122123, 35a81a6b, 840c001e, 255b5535, 7e64e451, f812375a, 0ac0efaf, 2979399f

### Technical Details

#### Parser Implementation
Based on yt-dlp's official parsing logic from [options.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/options.py):
```python
_extractor_arg_parser = lambda key, vals='': (key.strip().lower().replace('-', '_'), [
    val.replace(r'\,', ',').strip() for val in re.split(r'(?<!\\),', vals)])
```

**Features:**
- Whitespace separates multiple extractors
- Colon (`:`) separates extractor name from arguments
- Semicolon (`;`) separates multiple key-value pairs
- Equals (`=`) separates key from values
- Comma (`,`) separates multiple values
- Escaped commas (`\,`) preserved in values
- Keys normalized: lowercase, hyphens to underscores
- Helpful warnings for malformed input

#### Files Modified
**Backend:**
- `backend/appsettings/serializers.py` - Added extractor_args field
- `backend/appsettings/src/config.py` - Added to downloads configuration
- `backend/download/src/yt_dlp_base.py` - ExtractorArgsParser class and YtWrap integration
- `backend/user/migrations/0001_initial.py` - Migration updates

**Frontend:**
- `frontend/package.json` - Dependency updates
- `frontend/package-lock.json` - Updated lockfile
- `frontend/src/api/loader/loadAppsettingsConfig.ts` - Type definition
- `frontend/src/pages/SettingsApplication.tsx` - UI input field with help text
- `frontend/src/stores/AppSettingsStore.ts` - State management

#### Use Cases
- **PO Token providers** - Integration with bgutil-ytdlp-pot-provider for YouTube rate limiting
- **Site-specific authentication** - Pass credentials or tokens to extractors
- **Rate limiting control** - Configure extractor-specific rate limits
- **Language preferences** - Specify metadata extraction languages
- **Player client selection** - Choose specific player clients (e.g., `youtube:player_client=android`)
- **Advanced options** - Enable experimental features or specific extraction modes

#### Example Configurations
```
youtubepot-bgutilhttp:base_url=http://172.17.0.1:4416
youtube:lang=en,es;skip=hls
youtube:player_client=android generic:key=value
```

#### Logging Output
```
[extractor_args] Applied custom args: {'youtubepot-bgutilhttp': {'base_url': ['http://172.17.0.1:4416']}}
```

---

## [v0.5.8-bmcd02] - 2025-11-13

### Added
- **Enhanced Media Stream Metadata Display** - Significantly improved media stream information on video pages
  - Added subtitle stream detection and display
  - Added thumbnail stream detection (attached_pic)
  - Added language metadata for video, audio, and subtitle streams
  - Improved conditional rendering in frontend for different stream types
  - Better handling of streams without bitrate data
  - Commits: 7d66f8bc

### Changed
- **Frontend Tooling** - Added missing `@eslint/js` v9.33.0 dependency for ESLint support
  - Commits: c18aff4c

### Technical Details

#### Files Modified
**Backend:**
- `backend/video/serializers.py` - Updated StreamItemSerializer to support subtitle type and language field
- `backend/video/src/media_streams.py` - Added subtitle/thumbnail extraction, language metadata

**Frontend:**
- `frontend/package.json` - Added @eslint/js dependency
- `frontend/src/pages/Home.tsx` - Updated StreamType TypeScript definitions
- `frontend/src/pages/Video.tsx` - Enhanced stream display with conditional rendering

#### Benefits
- Users can now see all embedded streams (video, audio, subtitles, thumbnails)
- Language information helps identify multi-language content
- More robust handling of various media container formats
- Complements the subtitle embedding feature by showing which subtitles are present

---

## [v0.5.8-bmcd01] - 2025-11-13

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

## [v0.5.8] - 2025-11-07

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
