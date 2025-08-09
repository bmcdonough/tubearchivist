# TubeArchivist Video and Audio File Merging

## Overview

TubeArchivist is a self-hosted YouTube media server that downloads and manages YouTube videos. This document outlines how TubeArchivist handles the downloading and merging of video and audio streams.

## Technical Implementation

TubeArchivist relies on the [yt-dlp](https://github.com/yt-dlp/yt-dlp) library, which is a fork of youtube-dl with additional features and fixes, to handle the downloading and processing of YouTube videos. The merging of separate video and audio streams is performed automatically by yt-dlp based on the configuration provided by TubeArchivist.

## Download and Merge Workflow

### 1. Configuration Setup

The download configuration is built in several steps:

1. **Base Configuration**: Defined in `VideoDownloader._build_obs_basic` method
   - Sets `merge_output_format` to "mp4"
   - Sets output template and other basic parameters
   - Located in: `/backend/download/src/yt_dlp_handler.py`

```python
def _build_obs_basic(self):
    """initial obs"""
    self.obs = {
        "merge_output_format": "mp4",
        "outtmpl": (self.CACHE_DIR + "/download/%(id)s.mp4"),
        "progress_hooks": [self._progress_hook],
        "noprogress": True,
        "continuedl": True,
        "writethumbnail": False,
        "noplaylist": True,
        "color": "no_color",
    }
```

2. **User Customization**: Applied in `VideoDownloader._build_obs_user` method
   - Adds user-defined format preferences
   - Allows custom format selection and sorting
   - Located in: `/backend/download/src/yt_dlp_handler.py`

```python
def _build_obs_user(self):
    """build user customized options"""
    if self.config["downloads"]["format"]:
        self.obs["format"] = self.config["downloads"]["format"]
    if self.config["downloads"]["format_sort"]:
        format_sort = self.config["downloads"]["format_sort"]
        format_sort_list = [i.strip() for i in format_sort.split(",")]
        self.obs["format_sort"] = format_sort_list
    # ...additional rate limiting configuration...
```

3. **Post-Processing Configuration**: Set in `VideoDownloader._build_obs_postprocessors` method
   - Adds metadata and thumbnail embedding options
   - Located in: `/backend/download/src/yt_dlp_handler.py`

```python
def _build_obs_postprocessors(self):
    """add postprocessor to obs"""
    postprocessors = []

    if self.config["downloads"]["add_metadata"]:
        postprocessors.append(
            {
                "key": "FFmpegMetadata",
                "add_chapters": True,
                "add_metadata": True,
            }
        )
        # ...additional metadata configuration...

    if self.config["downloads"]["add_thumbnail"]:
        postprocessors.append(
            {
                "key": "EmbedThumbnail",
                "already_have_thumbnail": True,
            }
        )
        self.obs["writethumbnail"] = True

    self.obs["postprocessors"] = postprocessors
```

### 2. Download Process

The actual download happens in the `_dl_single_vid` method which:
- Creates a copy of the options
- Applies any channel-specific overwrites
- Calls `YtWrap(obs, self.config).download(youtube_id)` to perform the download

```python
def _dl_single_vid(self, youtube_id: str, channel_id: str) -> bool:
    """download single video"""
    obs = self.obs.copy()
    self._set_overwrites(obs, channel_id)
    dl_cache = os.path.join(self.CACHE_DIR, "download")

    success, message = YtWrap(obs, self.config).download(youtube_id)
    if not success:
        self._handle_error(youtube_id, message)

    # ...cleanup of temporary files...

    return success
```

### 3. YtWrap Implementation

The `YtWrap` class in `/backend/download/src/yt_dlp_base.py` handles the actual interaction with yt-dlp:

```python
def download(self, url):
    """make download request"""
    self.obs.update({"check_formats": "selected"})
    with yt_dlp.YoutubeDL(self.obs) as ydl:
        try:
            ydl.download([url])
        except yt_dlp.utils.DownloadError as err:
            print(f"{url}: failed to download with message {err}")
            if "Temporary failure in name resolution" in str(err):
                raise ConnectionError("lost the internet, abort!") from err

            return False, str(err)

    self._validate_cookie()

    return True, True
```

### 4. Video and Audio Merging

The merging process is handled automatically by yt-dlp based on the configuration provided:

1. **Format Selection**: 
   - If a user specifies a `format` option, yt-dlp uses that to select video and audio streams.
   - Otherwise, yt-dlp selects the best available formats based on quality.

2. **Merging Process**:
   - yt-dlp typically downloads the best video stream and the best audio stream separately.
   - The `merge_output_format` option set to "mp4" instructs yt-dlp to merge these separate streams.
   - The merging is done using FFmpeg, which is a dependency of yt-dlp.

3. **Output**:
   - The merged file is saved to the configured output path: `CACHE_DIR + "/download/%(id)s.mp4"`.

### 5. Moving to Archive

After download and merging are complete, the file is moved from the cache to the permanent media storage:

```python
def move_to_archive(self, vid_dict):
    """move downloaded video from cache to archive"""
    # ...directory preparation...
    
    # move media file
    media_file = vid_dict["youtube_id"] + ".mp4"
    old_path = os.path.join(self.CACHE_DIR, "download", media_file)
    new_path = os.path.join(self.MEDIA_DIR, vid_dict["media_url"])
    # move media file and fix permission
    shutil.move(old_path, new_path, copy_function=shutil.copyfile)
    # ...permission fixing...
```

## Summary

TubeArchivist relies on yt-dlp to handle both the downloading and merging of YouTube video and audio streams. This process is configured through several methods that set up the download parameters, format preferences, and post-processing options. The key configuration is the `merge_output_format` parameter set to "mp4", which instructs yt-dlp to automatically merge separate video and audio streams into a single MP4 file using FFmpeg.

The workflow can be summarized as:
1. Configure download parameters including format preferences
2. Download video and audio streams using yt-dlp
3. Automatically merge streams via yt-dlp using FFmpeg (configured by `merge_output_format`)
4. Move the resulting MP4 file from the cache to permanent storage
5. Update metadata in the database

This approach leverages yt-dlp's built-in capabilities to handle the complexities of selecting appropriate formats and merging them efficiently.

## The 'obs' Dictionary

In TubeArchivist, the configuration for yt-dlp is stored in a Python dictionary called `obs` (options). This dictionary is built from multiple sources and contains all the parameters that control how yt-dlp downloads and processes videos.

### Structure of the 'obs' Dictionary

The `obs` dictionary is constructed in several layers:

1. **Base Layer (YtWrap.OBS_BASE)**
   ```python
   OBS_BASE = {
       "default_search": "ytsearch",
       "quiet": True,
       "socket_timeout": 10,
       "extractor_retries": 3,
       "retries": 10,
   }
   ```

2. **Basic Download Options (_build_obs_basic)**
   ```python
   self.obs = {
       "merge_output_format": "mp4",
       "outtmpl": (self.CACHE_DIR + "/download/%(id)s.mp4"),
       "progress_hooks": [self._progress_hook],
       "noprogress": True,
       "continuedl": True,
       "writethumbnail": False,
       "noplaylist": True,
       "color": "no_color",
   }
   ```

3. **User Customization (_build_obs_user)**
   - Format selection: `self.obs["format"] = self.config["downloads"]["format"]`
   - Format sorting: `self.obs["format_sort"] = format_sort_list`
   - Rate limits: `self.obs["ratelimit"] = self.config["downloads"]["limit_speed"] * 1024`

4. **Post-processors (_build_obs_postprocessors)**
   ```python
   self.obs["postprocessors"] = [
       {
           "key": "FFmpegMetadata",
           "add_chapters": True,
           "add_metadata": True,
       },
       # Other post-processors
   ]
   ```

5. **Additional parameters (YtWrap.download)**
   ```python
   self.obs.update({"check_formats": "selected"})
   ```

6. **Channel-specific overwrites (_set_overwrites)**
   ```python
   if overwrites and overwrites.get("download_format"):
       obs["format"] = overwrites.get("download_format")
   ```

### Key Parameters for Video/Audio Processing

- **merge_output_format**: Specifies the container format for the merged video and audio streams ("mp4")
- **format**: Format selection string for yt-dlp (if specified by the user)
- **format_sort**: List of format sorting criteria (if specified by the user)
- **postprocessors**: List of post-processing operations to perform on the downloaded video

## FFmpeg Usage

FFmpeg is not directly invoked by TubeArchivist but is used by yt-dlp as a dependency to perform several critical operations:

1. **Format Merging**: 
   - When `merge_output_format` is set to "mp4", yt-dlp uses FFmpeg to combine the separate video and audio streams
   - This happens automatically as part of yt-dlp's download process

2. **Metadata Embedding**:
   - The "FFmpegMetadata" post-processor uses FFmpeg to embed metadata into the video file
   - This includes information like title, uploader, chapters, etc.

3. **Thumbnail Embedding**:
   - When the "EmbedThumbnail" post-processor is enabled, FFmpeg is used to embed the thumbnail image into the video file

## Implementing "--remux-video" Option

The "--remux-video" option in yt-dlp allows remuxing the video into a different container format without re-encoding. This can be useful for faster processing when only a container change is needed.

### How to Implement

To add the "--remux-video" option to TubeArchivist, you would need to modify the `_build_obs_basic` or `_build_obs_user` method in `yt_dlp_handler.py`. Here's a suggested implementation:

```python
def _build_obs_basic(self):
    """initial obs"""
    self.obs = {
        "merge_output_format": "mp4",
        "outtmpl": (self.CACHE_DIR + "/download/%(id)s.mp4"),
        "progress_hooks": [self._progress_hook],
        "noprogress": True,
        "continuedl": True,
        "writethumbnail": False,
        "noplaylist": True,
        "color": "no_color",
        "remux_video": "mp4",  # Add this line to enable remuxing to MP4
    }
```

Alternatively, you could add this as a user-configurable option by modifying the `_build_obs_user` method:

```python
def _build_obs_user(self):
    """build user customized options"""
    # Existing code...
    
    if self.config["downloads"].get("remux_video"):
        self.obs["remux_video"] = self.config["downloads"]["remux_video"]
```

And then add the option to the user settings in the appropriate configuration file.

### Considerations

1. **Performance Impact**: Using "--remux-video" can significantly speed up processing when only a container change is needed, as it avoids re-encoding.

2. **Format Compatibility**: This option works best when the source formats are compatible with the target container. For MP4, this typically means H.264 video and AAC audio.

3. **Integration with merge_output_format**: When both options are specified, you may need to ensure they don't conflict. In most cases, they should work together seamlessly when specifying the same output format.

4. **User Control**: Consider making this an optional setting that users can enable/disable based on their specific needs and hardware capabilities.

# example
```shell
yt-dlp -f bestvideo+bestaudio[acodec*=mp4a] \
  --merge-output-format mkv \
  --write-subs --embed-subs --sub-lang en-US \
  -o "%(title)s.%(ext)s" \
  "https://youtube.com/watch?v=1VRgZEwf85Y"
```
