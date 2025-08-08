"""
functionality:
- download subtitles
- parse subtitles into it's cues
- index dubtitles
"""

import json
import os
import re
from datetime import datetime
from operator import itemgetter

import requests
from common.src.env_settings import EnvironmentSettings
from common.src.es_connect import ElasticWrap
from common.src.helper import rand_sleep, requests_headers
from yt_dlp.utils import orderedSet_from_options


class YoutubeSubtitle:
    """handle video subtitle functionality"""

    def __init__(self, video):
        self.video = video
        self.languages = False
        print(f"{video.youtube_id}: initializing subtitle handler")

    def _sub_conf_parse(self):
        """add additional conf values to self"""
        languages_raw = self.video.config["downloads"]["subtitle"]
        print(f"{self.video.youtube_id}: parsing subtitle config: {languages_raw}")
        if languages_raw:
            self.languages = [i.strip() for i in languages_raw.split(",")]
            print(
                f"{self.video.youtube_id}: subtitle languages requested: {self.languages}"
            )

    def get_subtitles(self):
        """check what to do"""
        print(f"{self.video.youtube_id}: checking subtitle requirements")
        self._sub_conf_parse()
        if not self.languages:
            # no subtitles
            print(f"{self.video.youtube_id}: no subtitles requested, skipping")
            return False

        available_subtitles = self._get_all_subtitles("user")
        if self.video.config["downloads"]["subtitle_source"] == "auto":
            for lang, auto_cap in self._get_all_subtitles("auto").items():
                if lang not in available_subtitles:
                    available_subtitles[lang] = auto_cap

        all_sub_langs = tuple(available_subtitles.keys())
        relevant_subtitles = False
        try:
            relevant_subtitles = [
                available_subtitles[lang]
                for lang in orderedSet_from_options(
                    self.languages, {"all": all_sub_langs}, use_regex=True
                )
            ]
        except re.error as e:
            raise ValueError(f"wrong regex in subtitle config: {e.pattern}")

        return relevant_subtitles

    def _get_all_subtitles(self, source):
        """get video subtitles or automatic captions"""
        print(f"{self.video.youtube_id}: get {source} subtitles")
        youtube_meta_keys = {"user": "subtitles", "auto": "automatic_captions"}
        if not (youtube_meta_key := youtube_meta_keys.get(source, None)):
            print(f"{self.video.youtube_id}: unknown subtitles source: {source}")
            raise ValueError(f"unknown subtitles source: {source}")
        all_subtitles = self.video.youtube_meta.get(youtube_meta_key)
        if not all_subtitles:
            print(f"{self.video.youtube_id}: no {source} subtitles found in metadata")
            return {}

        print(
            f"{self.video.youtube_id}: found {len(all_subtitles)} language options for {source} subtitles"
        )
        candidate_subtitles = {}
        for lang, all_formats in all_subtitles.items():
            if lang == "live_chat":
                print(f"{self.video.youtube_id}: skipping live_chat, not supported yet")
                # not supported yet
                continue

            print(f"{self.video.youtube_id}: processing {lang} subtitle option")
            video_media_url = self.video.json_data["media_url"]
            media_url = video_media_url.replace(".mp4", f".{lang}.vtt")
            if not all_formats:
                print(f"{self.video.youtube_id}-{lang}: no subtitle formats found")
                # no subtitles found
                continue

            print(
                f"{self.video.youtube_id}-{lang}: found {len(all_formats)} format options"
            )
            subtitle_json3 = [i for i in all_formats if i["ext"] == "json3"]
            if not subtitle_json3:
                print(
                    f"{self.video.youtube_id}-{lang}: json3 format not found, skipping"
                )
                continue

            print(
                f"{self.video.youtube_id}-{lang}: json3 format found, adding as candidate"
            )
            subtitle = subtitle_json3[0]
            subtitle.update({"lang": lang, "source": source, "media_url": media_url})
            candidate_subtitles[lang] = subtitle

        print(
            f"{self.video.youtube_id}: found {len(candidate_subtitles)} candidate {source} subtitles"
        )
        return candidate_subtitles

    def download_subtitles(self, relevant_subtitles):
        """download subtitle files to archive"""
        subtitle_list = ", ".join(map(itemgetter("lang"), relevant_subtitles))
        print(f"{self.video.youtube_id}: downloading subtitles: {subtitle_list}")
        videos_base = EnvironmentSettings.MEDIA_DIR
        indexed = []
        for subtitle in relevant_subtitles:
            dest_path = os.path.join(videos_base, subtitle["media_url"])
            source = subtitle["source"]
            lang = subtitle.get("lang")
            response = requests.get(
                subtitle["url"], headers=requests_headers(), timeout=30
            )
            if not response.ok:
                subtitle_key = f"{self.video.youtube_id}-{lang}"
                print(f"{subtitle_key}: failed to download subtitle")
                print(response.text)
                rand_sleep(self.video.config)
                continue

            if not response.text:
                print(f"{subtitle_key}: skip empty subtitle")
                rand_sleep(self.video.config)
                continue

            print(f"{self.video.youtube_id}-{lang}: parsing subtitle content")
            parser = SubtitleParser(response.text, lang, source)
            parser.process()
            if not parser.all_cues:
                print(f"{self.video.youtube_id}-{lang}: no cues found, skipping")
                rand_sleep(self.video.config)
                continue
            print(f"{self.video.youtube_id}-{lang}: found {len(parser.all_cues)} cues")

            subtitle_str = parser.get_subtitle_str()
            self._write_subtitle_file(dest_path, subtitle_str)
            if self.video.config["downloads"]["subtitle_index"]:
                query_str = parser.create_bulk_import(self.video, source)
                self._index_subtitle(query_str)

            indexed.append(subtitle)
            rand_sleep(self.video.config)

        return indexed

    def _write_subtitle_file(self, dest_path, subtitle_str):
        """write subtitle file to disk"""
        print(f"{self.video.youtube_id}: writing subtitle file to {dest_path}")
        # create folder here for first video of channel
        os.makedirs(os.path.split(dest_path)[0], exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as subfile:
            subfile.write(subtitle_str)
        print(f"{self.video.youtube_id}: subtitle file written successfully")

        host_uid = EnvironmentSettings.HOST_UID
        host_gid = EnvironmentSettings.HOST_GID
        if host_uid and host_gid:
            os.chown(dest_path, host_uid, host_gid)

    @staticmethod
    def _index_subtitle(query_str):
        """send subtitle to es for indexing"""
        print("indexing subtitle to Elasticsearch")
        _, _ = ElasticWrap("_bulk").post(data=query_str, ndjson=True)
        print("subtitle indexing complete")

    def delete(self, subtitles=False):
        """delete subtitles from index and filesystem"""
        youtube_id = self.video.youtube_id
        print(f"{youtube_id}: deleting subtitle files and index entries")
        videos_base = EnvironmentSettings.MEDIA_DIR
        # delete files
        if subtitles:
            files = [i["media_url"] for i in subtitles]
            print(
                f"{youtube_id}: deleting specified subtitle files: {len(files)} files"
            )
        else:
            if not self.video.json_data.get("subtitles"):
                print(f"{youtube_id}: no subtitles to delete")
                return

            files = [i["media_url"] for i in self.video.json_data["subtitles"]]
            print(f"{youtube_id}: deleting all subtitle files: {len(files)} files")

        for file_name in files:
            file_path = os.path.join(videos_base, file_name)
            try:
                os.remove(file_path)
                print(f"{youtube_id}: removed {file_path}")
            except FileNotFoundError:
                print(f"{youtube_id}: {file_path} failed to delete")
        # delete from index
        path = "ta_subtitle/_delete_by_query?refresh=true"
        data = {"query": {"term": {"youtube_id": {"value": youtube_id}}}}
        _, _ = ElasticWrap(path).post(data=data)
        print(f"{youtube_id}: removed subtitle entries from index")


class SubtitleParser:
    """parse subtitle str from youtube"""

    def __init__(self, subtitle_str, lang, source):
        print(f"initializing subtitle parser for language: {lang}, source: {source}")
        self.subtitle_raw = json.loads(subtitle_str)
        self.lang = lang
        self.source = source
        self.all_cues = False

    def process(self):
        """extract relevant que data"""
        print(f"{self.lang}: processing subtitle events")
        self.all_cues = []
        all_events = self.subtitle_raw.get("events")

        if not all_events:
            print(f"{self.lang}: no events found in subtitle data")
            return

        print(f"{self.lang}: found {len(all_events)} events")
        if self.source == "auto":
            print(f"{self.lang}: flattening automatic caption segments")
            all_events = self._flat_auto_caption(all_events)

        for idx, event in enumerate(all_events):
            if "dDurationMs" not in event or "segs" not in event:
                # some events won't have a duration or segs
                print(f"skipping subtitle event without content: {event}")
                continue

            cue = {
                "start": self._ms_conv(event["tStartMs"]),
                "end": self._ms_conv(event["tStartMs"] + event["dDurationMs"]),
                "text": "".join([i.get("utf8") for i in event["segs"]]),
                "idx": idx + 1,
            }
            self.all_cues.append(cue)

        print(f"{self.lang}: processed {len(self.all_cues)} cues")

    @staticmethod
    def _flat_auto_caption(all_events):
        """flatten autocaption segments"""
        print(f"flattening {len(all_events)} auto caption events")
        flatten = []
        for event in all_events:
            if "segs" not in event.keys():
                print(f"skipping event without segs: {event}")
                continue
            text = "".join([i.get("utf8") for i in event.get("segs")])
            if not text.strip():
                continue

            if flatten:
                # fix overlapping retiming issue
                last = flatten[-1]
                if "dDurationMs" not in last or "segs" not in last:
                    # some events won't have a duration or segs
                    print(f"skipping subtitle event without content: {event}")
                    continue

                last_end = last["tStartMs"] + last["dDurationMs"]
                if event["tStartMs"] < last_end:
                    joined = last["segs"][0]["utf8"] + "\n" + text
                    last["segs"][0]["utf8"] = joined
                    continue

            event.update({"segs": [{"utf8": text}]})
            flatten.append(event)

        return flatten

    @staticmethod
    def _ms_conv(ms):
        """convert ms to timestamp"""
        # Not adding logging here as this is a utility method called very frequently
        # Adding logging would create too much noise in the logs
        hours = str((ms // (1000 * 60 * 60)) % 24).zfill(2)
        minutes = str((ms // (1000 * 60)) % 60).zfill(2)
        secs = str((ms // 1000) % 60).zfill(2)
        millis = str(ms % 1000).zfill(3)

        return f"{hours}:{minutes}:{secs}.{millis}"

    def get_subtitle_str(self):
        """create vtt text str from cues"""
        print(f"{self.lang}: creating VTT subtitle string")
        subtitle_str = f"WEBVTT\nKind: captions\nLanguage: {self.lang}"

        for cue in self.all_cues:
            stamp = f"{cue.get('start')} --> {cue.get('end')}"
            cue_text = f"\n\n{cue.get('idx')}\n{stamp}\n{cue.get('text')}"
            subtitle_str = subtitle_str + cue_text

        print(
            f"{self.lang}: VTT subtitle string created with {len(self.all_cues)} cues"
        )
        return subtitle_str

    def create_bulk_import(self, video, source):
        """subtitle lines for es import"""
        print(f"{video.youtube_id}-{self.lang}: creating bulk import for Elasticsearch")
        documents = self._create_documents(video, source)
        print(
            f"{video.youtube_id}-{self.lang}: created {len(documents)} documents for indexing"
        )
        bulk_list = []

        for document in documents:
            document_id = document.get("subtitle_fragment_id")
            action = {"index": {"_index": "ta_subtitle", "_id": document_id}}
            bulk_list.append(json.dumps(action))
            bulk_list.append(json.dumps(document))

        bulk_list.append("\n")
        query_str = "\n".join(bulk_list)
        print(f"{video.youtube_id}-{self.lang}: bulk import query string created")

        return query_str

    def _create_documents(self, video, source):
        """process documents"""
        print(f"{video.youtube_id}-{self.lang}: creating subtitle documents")
        documents = self._chunk_list(video.youtube_id)
        print(
            f"{video.youtube_id}-{self.lang}: chunked into {len(documents)} documents"
        )

        channel = video.json_data.get("channel")
        meta_dict = {
            "youtube_id": video.youtube_id,
            "title": video.json_data.get("title"),
            "subtitle_channel": channel.get("channel_name"),
            "subtitle_channel_id": channel.get("channel_id"),
            "subtitle_last_refresh": int(datetime.now().timestamp()),
            "subtitle_lang": self.lang,
            "subtitle_source": source,
        }

        print(f"{video.youtube_id}-{self.lang}: adding metadata to documents")
        _ = [i.update(meta_dict) for i in documents]

        return documents

    def _chunk_list(self, youtube_id):
        """join cues for bulk import"""
        print(f"{youtube_id}-{self.lang}: chunking subtitle cues for Elasticsearch")
        chunk_list = []

        chunk = {}
        for cue in self.all_cues:
            if chunk:
                text = f"{chunk.get('subtitle_line')} {cue.get('text')}\n"
                chunk["subtitle_line"] = text
            else:
                idx = len(chunk_list) + 1
                chunk = {
                    "subtitle_index": idx,
                    "subtitle_line": cue.get("text"),
                    "subtitle_start": cue.get("start"),
                }

            chunk["subtitle_fragment_id"] = f"{youtube_id}-{self.lang}-{idx}"

            if cue["idx"] % 5 == 0:
                chunk["subtitle_end"] = cue.get("end")
                chunk_list.append(chunk)
                chunk = {}

        print(f"{youtube_id}-{self.lang}: created {len(chunk_list)} subtitle chunks")
        return chunk_list
