"""extract metadata from video streams"""

import json
import logging
import os
import subprocess
from os import stat

# Setup logger
logging = logging.getLogger(__name__)


# Debug helper function
def debug_streams(func):
    """Decorator to add debug logging for stream extraction functions"""

    def wrapper(*args, **kwargs):
        logging.info(f"[DEBUG] Calling {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logging.info(
                f"[DEBUG] {func.__name__} succeeded with result type: "
                f"{type(result)}"
            )
            return result
        except Exception as e:
            logging.error(
                f"[DEBUG] {func.__name__} failed with error: {str(e)}"
            )
            raise

    return wrapper


class MediaStreamExtractor:
    """extract stream metadata"""

    def __init__(self, media_path):
        self.media_path = media_path
        self.metadata = []
        self.format_info = {}

    @debug_streams
    def extract_metadata(self):
        """entry point to extract metadata"""
        # First check if the file exists
        if not os.path.exists(self.media_path):
            logging.error(f"[DEBUG] File does not exist: {self.media_path}")
            return self.metadata

        logging.info(f"[DEBUG] Extracting metadata from: {self.media_path}")
        file_size = (
            os.path.getsize(self.media_path)
            if os.path.exists(self.media_path)
            else "File not found"
        )
        logging.info(f"[DEBUG] File size: {file_size}")

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

        try:
            logging.info(f"[DEBUG] Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                logging.error(
                    f"[DEBUG] ffprobe failed with return code "
                    f"{result.returncode}"
                )
                logging.error(f"[DEBUG] stderr: {result.stderr}")
                return self.metadata

            try:
                json_output = json.loads(result.stdout)
                streams = json_output.get("streams", [])
                format_info = json_output.get("format", {})

                logging.info(f"[DEBUG] Found {len(streams)} streams")
                logging.info(f"[DEBUG] Format info: {format_info}")

                # Store format info for use in stream processing
                self.format_info = format_info

                if not streams:
                    logging.warning("[DEBUG] No streams found in the file")

                for stream in streams:
                    self.process_stream(stream)

                logging.info(f"[DEBUG] Final metadata: {self.metadata}")
                return self.metadata
            except json.JSONDecodeError as e:
                logging.error(
                    f"[DEBUG] Failed to parse ffprobe JSON output: {e}"
                )
                logging.error(f"[DEBUG] Raw output: {result.stdout[:500]}...")
                return self.metadata
        except Exception as e:
            logging.error(f"[DEBUG] Exception running ffprobe: {str(e)}")
            return self.metadata

    @debug_streams
    def process_stream(self, stream):
        """parse stream to metadata"""
        codec_type = stream.get("codec_type")
        logging.info(
            f"[DEBUG] Processing stream with codec_type: {codec_type}"
        )
        logging.info(f"[DEBUG] Stream details: {stream}")

        if codec_type == "video":
            self._extract_video_metadata(stream)
        elif codec_type == "audio":
            self._extract_audio_metadata(stream)
        else:
            logging.info(
                f"[DEBUG] Ignoring stream with codec_type: {codec_type}"
            )
            return

    @debug_streams
    def _extract_video_metadata(self, stream):
        """parse video metadata"""
        logging.info(
            f"[DEBUG] Extracting video metadata from stream: {stream['index']}"
        )

        bit_rate = self._get_video_bitrate(stream)
        self._create_video_metadata_entry(stream, bit_rate)

    def _get_video_bitrate(self, stream):
        """Extract bitrate from video stream with fallbacks"""
        logging.info(
            f"[DEBUG] Stream {stream['index']} keys: {list(stream.keys())}"
        )
        logging.info(
            f"[DEBUG] Format info available: {bool(self.format_info)}"
        )

        # Log format info if available
        self._log_format_info()

        # Try direct stream bit_rate first
        bit_rate = self._get_direct_bitrate(stream)
        if bit_rate > 0:
            return bit_rate

        # Try alternative sources
        logging.warning(
            f"[DEBUG] No bit_rate in video stream {stream['index']} - "
            f"attempting alternative sources"
        )

        # Try tags
        bit_rate = self._get_bitrate_from_tags(stream)
        if bit_rate > 0:
            return bit_rate

        # Try format bit_rate as last resort
        return self._get_format_bitrate()

    def _log_format_info(self):
        """Log format information for debugging"""
        if self.format_info:
            logging.info(
                f"[DEBUG] Format info keys: {list(self.format_info.keys())}"
            )
            if "bit_rate" in self.format_info:
                logging.info(
                    f"[DEBUG] Format bit_rate: {self.format_info['bit_rate']}"
                )

    def _get_direct_bitrate(self, stream):
        """Get bitrate directly from stream"""
        if "bit_rate" in stream:
            try:
                bit_rate = int(stream["bit_rate"])
                logging.info(
                    f"[DEBUG] Found direct bit_rate in stream: {bit_rate}"
                )
                return bit_rate
            except (ValueError, TypeError) as e:
                logging.error(
                    f"[DEBUG] Error converting bit_rate: {e}, value: "
                    f"{stream.get('bit_rate')}"
                )
        return 0

    def _get_bitrate_from_tags(self, stream):
        """Get bitrate from stream tags"""
        if "tags" in stream:
            logging.info(
                f"[DEBUG] Tags available: {list(stream['tags'].keys())}"
            )
            if "BPS" in stream["tags"]:
                try:
                    bit_rate = int(stream["tags"]["BPS"])
                    logging.info(f"[DEBUG] Found bit_rate in tags: {bit_rate}")
                    return bit_rate
                except (ValueError, TypeError) as e:
                    logging.warning(f"[DEBUG] Invalid BPS value in tags: {e}")
        return 0

    def _get_format_bitrate(self):
        """Get bitrate from format info as fallback"""
        if self.format_info and "bit_rate" in self.format_info:
            try:
                bit_rate = int(self.format_info["bit_rate"])
                logging.info(f"[DEBUG] Using format bit_rate: {bit_rate}")
                return bit_rate
            except (ValueError, TypeError) as e:
                logging.error(f"[DEBUG] Error converting format bit_rate: {e}")
        return 0

    def _create_video_metadata_entry(self, stream, bit_rate):
        """Create and append video metadata entry"""
        # Create metadata entry regardless of bit_rate - we'll use 0 if
        # not available
        # This ensures we don't lose video stream information
        try:
            metadata_entry = {
                "type": "video",
                "index": stream["index"],
                "codec": stream.get("codec_name", "unknown"),
                "width": stream.get("width", 0),
                "height": stream.get("height", 0),
                "bitrate": bit_rate,
            }
            logging.info(f"[DEBUG] Created video metadata: {metadata_entry}")
            self.metadata.append(metadata_entry)
            logging.info(
                f"[DEBUG] Successfully added video stream "
                f"{stream['index']} to metadata"
            )
        except KeyError as e:
            logging.error(f"[DEBUG] Missing required key in stream: {e}")
            logging.error(f"[DEBUG] Stream data: {stream}")

    @debug_streams
    def _extract_audio_metadata(self, stream):
        """extract audio metadata"""
        logging.info(
            f"[DEBUG] Extracting audio metadata from stream: {stream['index']}"
        )

        try:
            bit_rate = int(stream.get("bit_rate", 0))
        except (ValueError, TypeError) as e:
            logging.error(
                f"[DEBUG] Error converting audio bit_rate: {e}, value: "
                f"{stream.get('bit_rate')}"
            )
            # Try to get bit_rate from tags if available
            if "tags" in stream and "BPS" in stream["tags"]:
                try:
                    bit_rate = int(stream["tags"]["BPS"])
                    logging.info(
                        f"[DEBUG] Found audio bit_rate in tags: {bit_rate}"
                    )
                except (ValueError, TypeError):
                    bit_rate = 0
                    logging.warning("[DEBUG] Invalid audio BPS value in tags")
            else:
                bit_rate = 0

        try:
            metadata_entry = {
                "type": "audio",
                "index": stream["index"],
                "codec": stream.get("codec_name", "undefined"),
                "bitrate": bit_rate,
            }
            logging.info(f"[DEBUG] Created audio metadata: {metadata_entry}")
            self.metadata.append(metadata_entry)
        except KeyError as e:
            logging.error(f"[DEBUG] Missing required key in audio stream: {e}")
            logging.error(f"[DEBUG] Stream data: {stream}")

    @debug_streams
    def get_file_size(self):
        """get filesize in bytes"""
        try:
            size = stat(self.media_path).st_size
            logging.info(f"[DEBUG] File size: {size} bytes")
            return size
        except FileNotFoundError:
            logging.error(f"[DEBUG] File not found: {self.media_path}")
            return 0
        except Exception as e:
            logging.error(f"[DEBUG] Error getting file size: {str(e)}")
            return 0
