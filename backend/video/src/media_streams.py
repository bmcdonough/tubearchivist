"""extract metadata from video streams"""

import inspect
import json
import logging
import os
import subprocess
from os import stat

logging = logging.getLogger(__name__)


# Debug helper function
def debug_helper(func):
    """Decorator to add debug logging for stream extraction functions"""

    def wrapper(*args, **kwargs):
        # Get caller information
        stack = inspect.stack()
        caller_frame = stack[
            2
        ]  # Frame 0 is wrapper, Frame 1 is decorated func, Frame 2 is caller
        filename = os.path.basename(caller_frame.filename)
        line_number = caller_frame.lineno

        logging.debug(
            f"Calling {func.__name__} from [{filename}:{line_number}]"
        )
        try:
            result = func(*args, **kwargs)
            logging.debug(
                f"[{filename}:{line_number}] {func.__name__} succeeded with "
                f"result type: {type(result)}"
            )
            return result
        except Exception as e:
            logging.error(
                f"[{filename}:{line_number}] {func.__name__} failed with "
                f"error: {str(e)}"
            )
            raise

    return wrapper


class MediaStreamExtractor:
    """extract stream metadata"""

    def __init__(self, media_path):
        self.media_path = media_path
        self.metadata = []

    @debug_helper
    def extract_metadata(self):
        """entry point to extract metadata"""

        # First check if the file exists
        if not os.path.exists(self.media_path):
            logging.error(f"File does not exist: {self.media_path}")
            return self.metadata

        logging.debug(f"Extracting metadata from: {self.media_path}")
        file_size = (
            os.path.getsize(self.media_path)
            if os.path.exists(self.media_path)
            else "File not found"
        )
        logging.debug(f"File size: {file_size}")

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            self.media_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            return self.metadata

        streams = json.loads(result.stdout).get("streams")
        logging.debug(f"streams :: {json.dumps(streams, indent=4)}")
        for stream in streams:
            self.process_stream(stream)

        return self.metadata

    def process_stream(self, stream):
        """parse stream to metadata"""
        codec_name = stream.get("codec_name")
        codec_tag_string = stream.get("codec_tag_string")
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            self._extract_video_metadata(stream)
            if codec_name == "png":
                self._extract_thumbnail_metadata(stream)
        elif codec_type == "audio":
            self._extract_audio_metadata(stream)
        elif codec_type == "data":
            if codec_tag_string == "text":
                self._extract_subtitle_metadata(stream)
        else:
            return

    def _extract_video_metadata(self, stream):
        """parse video metadata"""
        if "bit_rate" not in stream:
            # is probably thumbnail
            return

        self.metadata.append(
            {
                "type": "video",
                "index": stream["index"],
                "codec": stream["codec_name"],
                "width": stream["width"],
                "height": stream["height"],
                "bitrate": int(stream["bit_rate"]),
                "language": stream.get("tags", {}).get("language", "unknown"),
            }
        )

    def _extract_audio_metadata(self, stream):
        """extract audio metadata"""
        self.metadata.append(
            {
                "type": "audio",
                "index": stream["index"],
                "codec": stream.get("codec_name", "undefined"),
                "bitrate": int(stream.get("bit_rate", 0)),
                "language": stream.get("tags", {}).get("language", "unknown"),
            }
        )

    @debug_helper
    def _extract_subtitle_metadata(self, stream):
        """extract subtitle metadata"""
        logging.debug(
            f"subtitle metadata: {stream['index']} {stream.get('codec_name')} "
            f"{int(stream.get('bit_rate', 0))} "
            f"{stream.get('tags', {}).get('language', 'unknown')}"
        )
        self.metadata.append(
            {
                "type": "subtitle",
                "index": stream["index"],
                "codec": stream.get("codec_name", "text"),
                "bitrate": int(stream.get("bit_rate", 0)),
                "language": stream.get("tags", {}).get("language", "unknown"),
            }
        )

    @debug_helper
    def _extract_thumbnail_metadata(self, stream):
        """extract thumbnail metadata"""
        logging.debug(
            f"thumbnail metadata: {stream['index']} {stream.get('codec_name')}"
            f"{int(stream.get('bit_rate', 0))} "
            f"{stream.get('tags', {}).get('language', 'unknown')}"
        )
        self.metadata.append(
            {
                "type": "thumbnail",
                "index": stream["index"],
                "codec": stream.get("codec_name", "image"),
                "bitrate": int(stream.get("bit_rate", 0)),
                "language": stream.get("tags", {}).get("language", "unknown"),
            }
        )

    def get_file_size(self):
        """get filesize in bytes"""
        return stat(self.media_path).st_size
