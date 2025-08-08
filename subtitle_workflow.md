# TubeArchivist Subtitle Workflow Documentation

This document provides a detailed explanation of how TubeArchivist identifies, processes, and adds subtitles to archived videos.

## Table of Contents

1. [Overview](#overview)
2. [Subtitle Identification](#subtitle-identification)
3. [Subtitle Processing](#subtitle-processing)
4. [Subtitle Storage](#subtitle-storage)
5. [Subtitle Indexing](#subtitle-indexing)
6. [Subtitle Workflow Diagram](#subtitle-workflow-diagram)

## Overview

TubeArchivist provides functionality to download, process, and index subtitles for archived YouTube videos. The subtitle system supports both user-created subtitles and automatically generated captions from YouTube. Subtitles are stored as VTT files alongside video files and optionally indexed in Elasticsearch for searchability.

The subtitle functionality is primarily implemented in two classes:
- `YoutubeSubtitle`: Handles the overall subtitle workflow including identification, download, and storage
- `SubtitleParser`: Parses subtitle data from YouTube's JSON format into WebVTT format

## Subtitle Identification

### Entry Point

The subtitle functionality is triggered from the `YoutubeVideo.check_subtitles()` method in `video/src/index.py`. This method is called during the video archiving process and supports two paths:

1. **Online subtitles**: Subtitles downloaded directly from YouTube
2. **Offline subtitles**: Pre-existing subtitle files provided during import

### Subtitle Configuration

The system reads subtitle configuration from the application settings to determine:
- Which languages to download (comma-separated list in `config["downloads"]["subtitle"]`)
- Whether to use automatic captions when manual subtitles aren't available (`config["downloads"]["subtitle_source"]` set to `"auto"`)
- Whether to index subtitles in Elasticsearch (`config["downloads"]["subtitle_index"]` boolean)

### Subtitle Source Identification

Subtitles are identified in the `YoutubeSubtitle.get_subtitles()` method through the following process:

1. Parse subtitle configuration with `_sub_conf_parse()`
2. If no languages are configured, skip subtitle processing
3. Get available user-created subtitles with `_get_all_subtitles("user")`
4. If automatic captions are enabled and a language doesn't have user subtitles, get automatic captions with `_get_all_subtitles("auto")`
5. Filter subtitles based on configured languages using regex matching
6. Return a list of relevant subtitles

### Available Subtitle Detection

The `YoutubeSubtitle._get_all_subtitles()` method identifies available subtitles by:

1. Looking for subtitles in the video metadata (either `youtube_meta["subtitles"]` or `youtube_meta["automatic_captions"]`)
2. For each language, finding the JSON3 format subtitle (preferred format)
3. Constructing the expected media URL for the subtitle file (`{video_path}.{language}.vtt`)
4. Returning a dictionary of available subtitle metadata keyed by language

## Subtitle Processing

### Download Process

Once relevant subtitles are identified, they are downloaded and processed through the `YoutubeSubtitle.download_subtitles()` method:

1. For each subtitle in the list of relevant subtitles:
   - Download the JSON3 subtitle data from YouTube
   - Parse the subtitle data using the `SubtitleParser` class
   - Convert to WebVTT format
   - Write the VTT file to disk
   - Optionally index the subtitle in Elasticsearch

### Parsing Process

The `SubtitleParser` class handles the conversion from YouTube's JSON3 format to WebVTT:

1. Initialize with the raw JSON subtitle data, language code, and source type
2. In the `process()` method:
   - Extract events from the subtitle data
   - For automatic captions, flatten the caption segments with `_flat_auto_caption()`
   - For each event, extract the start time, end time, and text content
   - Convert timestamps from milliseconds to WebVTT format using `_ms_conv()`
   - Store processed cues in `self.all_cues`

### Format Conversion

The `SubtitleParser.get_subtitle_str()` method converts the processed cues to a WebVTT formatted string:

1. Create the WebVTT header with language information
2. For each cue, format with:
   - Cue number
   - Timestamp range (`start --> end`)
   - Caption text
3. Return the complete WebVTT formatted string

## Subtitle Storage

### File Storage

Subtitle files are stored on disk through the `YoutubeSubtitle._write_subtitle_file()` method:

1. Create directory structure if it doesn't exist
2. Write the WebVTT formatted subtitle string to a file
3. Set proper ownership using `HOST_UID` and `HOST_GID` from environment settings
4. Files are stored with the naming pattern `{video_base_name}.{language}.vtt` in the same directory as the video file

### Directory Structure

The subtitle files are stored alongside the video files in the media directory defined by `EnvironmentSettings.MEDIA_DIR`. This keeps subtitles and videos together for easy access during playback.

## Subtitle Indexing

### Indexing Process

If subtitle indexing is enabled, the subtitles are indexed in Elasticsearch for searchability:

1. The `SubtitleParser.create_bulk_import()` method:
   - Creates documents using `_create_documents()`
   - Formats for Elasticsearch bulk import
   - Returns a formatted query string for Elasticsearch

2. The `YoutubeSubtitle._index_subtitle()` method:
   - Sends the bulk import query to Elasticsearch using `ElasticWrap("_bulk").post()`

### Document Creation

The `SubtitleParser._create_documents()` method prepares subtitle data for indexing:

1. Chunk subtitle cues into groups using `_chunk_list()`
2. Add metadata including:
   - Video ID and title
   - Channel name and ID
   - Subtitle language and source
   - Last refresh timestamp

### Chunking Process

The `SubtitleParser._chunk_list()` method chunks subtitle cues for better searchability:

1. Group subtitle cues into chunks (approximately 5 cues per chunk)
2. Create a unique ID for each chunk (`{youtube_id}-{language}-{chunk_index}`)
3. Include start and end timestamps for each chunk

## Subtitle Workflow Diagram

```
┌─────────────────────┐
│  Video Archiving    │
│  Process Starts     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│YoutubeVideo.check_  │
│subtitles() called   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     No     ┌─────────────────┐
│  Subtitles enabled  ├────────────►  Skip Subtitles │
│  in configuration?  │            └─────────────────┘
└──────────┬──────────┘
           │ Yes
           ▼
┌─────────────────────┐
│ Get available       │
│ subtitle languages  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     No     ┌─────────────────┐
│ User subtitles      ├────────────►  Check auto     │
│ available?          │            │  captions       │
└──────────┬──────────┘            └────────┬────────┘
           │ Yes                            │
           │                                ▼
           │                     ┌─────────────────────┐
           │                     │ Auto captions       │
           │                     │ available?          │
           │                     └──────────┬──────────┘
           │                                │ Yes
           │                                ▼
           │                     ┌─────────────────────┐
           │                     │ Add auto captions   │
           │                     │ to available list   │
           │                     └──────────┬──────────┘
           │                                │
           ▼◄───────────────────────────────┘
┌─────────────────────┐
│ Filter by configured│
│ languages           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     No     ┌─────────────────┐
│ Subtitles found     ├────────────►  Done           │
│ after filtering?    │            └─────────────────┘
└──────────┬──────────┘
           │ Yes
           ▼
┌─────────────────────┐
│ Download subtitles  │
│ in JSON3 format     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Parse JSON3 into    │
│ subtitle cues       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Convert to WebVTT   │
│ format              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Write VTT file      │
│ to disk             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     No     ┌─────────────────┐
│ Subtitle indexing   ├────────────►  Done           │
│ enabled?            │            └─────────────────┘
└──────────┬──────────┘
           │ Yes
           ▼
┌─────────────────────┐
│ Create Elasticsearch│
│ documents           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Bulk index into     │
│ Elasticsearch       │
└─────────────────────┘
```
