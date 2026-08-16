from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def load_script(skill: str, filename: str):
    path = ROOT / "skills" / skill / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"{skill}_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PaperEvidenceRadarTests(unittest.TestCase):
    def test_parses_arxiv_atom_into_stable_evidence(self):
        module = load_script("paper-evidence-radar", "arxiv_search.py")
        items = module.parse_atom((SKILLS / "paper-evidence-radar" / "evals" / "files" / "arxiv.xml").read_bytes())
        self.assertEqual(items[0]["arxivId"], "2608.12345")
        self.assertEqual(items[0]["version"], 2)
        self.assertEqual(items[0]["authors"], ["Ada Researcher", "Bo Scientist"])
        self.assertEqual(items[0]["primaryCategory"], "cs.CV")
        self.assertEqual(module.filter_recent(items, date(2026, 8, 1)), items)


class GithubRepositoryResearchTests(unittest.TestCase):
    def test_snapshot_identifies_entrypoints_tests_and_license(self):
        module = load_script("github-repository-research", "repo_snapshot.py")
        snapshot = module.build_snapshot(SKILLS / "github-repository-research" / "evals" / "files" / "local-repo")
        self.assertEqual(snapshot["manifests"], ["package.json"])
        self.assertIn("src", snapshot["sourceDirectories"])
        self.assertIn("tests", snapshot["testDirectories"])
        self.assertEqual(snapshot["licenseFiles"], ["LICENSE"])


class BilibiliContentResearchTests(unittest.TestCase):
    def test_fixture_normalization_keeps_subtitle_and_comment_evidence(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        payload = json.loads((SKILLS / "bilibili-content-research" / "evals" / "files" / "bilibili.json").read_text())
        result = module.normalize_fixture(payload, max_comments=1)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["video"]["bvid"], "BV1xx411c7mD")
        self.assertEqual(result["subtitles"][0]["segments"][0]["text"], "第一句字幕")
        self.assertEqual(len(result["comments"]), 1)
        self.assertEqual(result["coverage"]["commentLimit"], 1)

    def test_fatal_collection_error_is_structured_and_read_only(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        result = module.failure_result("BV1xx411c7mD", 3, OSError("network unavailable"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["coverage"]["commentLimit"], 3)
        self.assertEqual(result["errors"], ["metadata:OSError:network unavailable"])
        self.assertFalse(result["boundaries"]["authenticated"])

    def test_wbi_signature_is_deterministic_with_fixed_timestamp(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        query = module.build_wbi_query(
            {"oid": 123, "type": 1},
            "7cd084941338484aae1ad9425b84077c",
            "4932caff0ff746eab6f01bf08b70ac45",
            1700000000,
        )
        self.assertIn("wts=1700000000", query)
        self.assertRegex(query, r"w_rid=[0-9a-f]{32}$")

    def test_anonymous_nav_can_supply_public_wbi_material(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        data = module._nav_data({"code": -101, "message": "not logged in", "data": {"isLogin": False, "wbi_img": {"img_url": "i", "sub_url": "s"}}})
        self.assertFalse(data["isLogin"])
        self.assertIn("wbi_img", data)

    def test_subtitle_fetch_is_limited_to_bilibili_hosts(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        self.assertEqual(module._subtitle_url("//aisubtitle.hdslb.com/example.json"), "https://aisubtitle.hdslb.com/example.json")
        self.assertIsNone(module._subtitle_url("https://example.com/private.json"))

    def test_player_failure_keeps_metadata_as_partial_result(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        fixture = json.loads((SKILLS / "bilibili-content-research" / "evals" / "files" / "bilibili.json").read_text())

        def fake_get(url, _referer=None):
            if "/view?" in url:
                return fixture["view"]
            return {"code": -404, "message": "player unavailable"}

        with mock.patch.object(module, "_get_json", side_effect=fake_get):
            result = module.collect_public("BV1xx411c7mD", max_comments=0)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["video"]["title"], "A useful demo")
        self.assertEqual(result["coverage"]["commentsReturned"], 0)
        self.assertTrue(result["errors"][0].startswith("player:"))

    def test_comment_api_error_keeps_metadata_as_partial_result(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        fixture = json.loads((SKILLS / "bilibili-content-research" / "evals" / "files" / "bilibili.json").read_text())

        def fake_get(url, _referer=None):
            if "/view?" in url:
                return fixture["view"]
            if "/player/" in url:
                return {"code": 0, "data": {}}
            if "/nav" in url:
                return {
                    "code": -101,
                    "data": {"isLogin": False, "wbi_img": {
                        "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
                        "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png",
                    }},
                }
            return {"code": -412, "message": "request blocked"}

        with mock.patch.object(module, "_get_json", side_effect=fake_get):
            result = module.collect_public("BV1xx411c7mD", max_comments=1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["video"]["title"], "A useful demo")
        self.assertEqual(result["comments"], [])
        self.assertTrue(result["errors"][0].startswith("comments:"))


class WeChatChatExportTests(unittest.TestCase):
    def test_doctor_reports_missing_key_without_attempting_acquisition(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        result = module.doctor("/path/that/does/not/exist.json")
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["error"]["code"], "missing_key_bundle")
        self.assertFalse(result["capabilities"]["acquireKeys"])

    def test_doctor_warns_about_stale_optional_paths_but_verifies_core_databases(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contact = root / "contact.db"
            message_dir = root / "message"
            message_dir.mkdir()
            message = message_dir / "message_0.db"
            contact.touch()
            message.touch()
            key_file = root / "keys.json"
            key_file.write_text(
                json.dumps({"keys": {
                    str(contact): "0" * 64,
                    str(message): "1" * 64,
                    str(root / "optional-missing.db"): "2" * 64,
                }}),
                encoding="utf-8",
            )
            key_file.chmod(0o600)

            def fake_decrypt(_source, _key, destination):
                module.sqlite3.connect(destination).close()

            with mock.patch.object(module, "decrypt_database", side_effect=fake_decrypt), mock.patch.object(
                module.sys, "platform", "darwin"
            ):
                result = module.doctor(str(key_file))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["keyBundle"]["missingDatabaseCount"], 1)
        self.assertIn("keyBundleReferencesMissingDatabases", result["warnings"])

    def test_image_classification_keeps_locator_but_drops_media_key(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        kind, text, media = module.classify_message(
            '<msg><img md5="safe-locator" aeskey="must-not-export" /></msg>'
        )
        self.assertEqual(kind, "image")
        self.assertEqual(text, "[image]")
        self.assertEqual(media, {"mediaId": "safe-locator"})
        self.assertNotIn("aes", json.dumps(media).lower())

    def test_ambiguous_group_requires_opaque_conversation_id(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        chats = [
            {"name": "Customer group A", "conversationId": "conversation-a", "_chatroom": "one@chatroom"},
            {"name": "Customer group B", "conversationId": "conversation-b", "_chatroom": "two@chatroom"},
        ]
        with self.assertRaises(module.ExportError) as raised:
            module.choose_chat(chats, "Customer group", None)
        self.assertEqual(raised.exception.code, "ambiguous_chat")
        selected = module.choose_chat(chats, None, "conversation-b")
        self.assertEqual(selected["name"], "Customer group B")

    def test_private_writer_sets_0600_and_refuses_git_worktrees(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "export.json"
            module.write_private_json(output, {"messages": []}, force=False)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            (root / ".git").mkdir()
            with self.assertRaises(module.ExportError) as raised:
                module.write_private_json(root / "blocked.json", {"messages": []}, force=False)
            self.assertEqual(raised.exception.code, "unsafe_output")

    def test_truncation_compares_available_records_with_requested_limit(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        self.assertFalse(module._is_truncated(50, 1000))
        self.assertFalse(module._is_truncated(1000, 1000))
        self.assertTrue(module._is_truncated(1001, 1000))
        self.assertFalse(module._is_truncated(1001, None))

    @unittest.skipUnless(
        os.environ.get("WECHAT_TEST_KEYS_PATH") and os.environ.get("WECHAT_TEST_GROUP"),
        "set WECHAT_TEST_KEYS_PATH and WECHAT_TEST_GROUP for the private local integration test",
    )
    def test_real_local_database_export_is_redacted_and_bounded(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        key_path = os.environ["WECHAT_TEST_KEYS_PATH"]
        group = os.environ["WECHAT_TEST_GROUP"]
        readiness = module.doctor(key_path)
        self.assertEqual(readiness["status"], "ready")
        with tempfile.TemporaryDirectory() as temporary:
            _, keys = module._load_keys(key_path)
            chats = module.discover_chats(keys, Path(temporary))
            chat = module.choose_chat(chats, group, None)
            result = module.export_messages(keys, chat, Path(temporary), None, None, 20, False)
        self.assertGreater(result["coverage"]["exportedCount"], 0)
        self.assertLessEqual(result["coverage"]["exportedCount"], 20)
        self.assertEqual(result["coverage"]["exportedCount"], len(result["messages"]))
        self.assertTrue(all(item["author"].startswith("participant-") for item in result["messages"]))
        serialized = json.dumps(result).lower()
        self.assertNotIn("aeskey", serialized)
        self.assertNotIn("db_storage", serialized)


class ReferenceVideoDeconstructionTests(unittest.TestCase):
    def test_probe_and_sample_plan_are_bounded(self):
        module = load_script("reference-video-deconstruction", "extract_video_evidence.py")
        probe = module.parse_probe({
            "format": {"duration": "20.0", "format_name": "mov,mp4"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
        })
        self.assertTrue(probe["hasAudio"])
        self.assertTrue(probe["hasVideo"])
        self.assertEqual(probe["orientation"], "portrait")
        times = module.sample_times(20.0, max_frames=5)
        self.assertEqual(len(times), 5)
        self.assertGreaterEqual(times[0], 0)
        self.assertLess(times[-1], 20.0)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_extracts_real_video_and_audio_evidence(self):
        module = load_script("reference-video-deconstruction", "extract_video_evidence.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "reference.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000",
                    "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(video),
                ],
                check=True,
            )
            output = root / "evidence"
            result = module.extract(video, output, max_frames=4)
            self.assertTrue(result["probe"]["hasAudio"])
            self.assertEqual(result["probe"]["width"], 320)
            self.assertGreaterEqual(result["coverage"]["framesExtracted"], 1)
            self.assertLessEqual(result["coverage"]["framesExtracted"], 4)
            self.assertTrue((output / "evidence.json").is_file())

    def test_force_refuses_symlinked_frames_directory(self):
        module = load_script("reference-video-deconstruction", "extract_video_evidence.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            target = root / "external"
            output.mkdir()
            target.mkdir()
            (output / "frames").symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                module._clear_generated_evidence(output)


class CreatorOpportunityRadarTests(unittest.TestCase):
    def test_ranking_rewards_independent_evidence(self):
        module = load_script("creator-opportunity-radar", "rank_opportunities.py")
        payload = json.loads((SKILLS / "creator-opportunity-radar" / "evals" / "files" / "opportunities.json").read_text())
        result = module.rank_opportunities(payload)
        self.assertEqual(result["ranked"][0]["id"], "opp-evidence-rich")
        self.assertEqual(result["ranked"][0]["confidence"], "high")
        self.assertEqual(result["ranked"][1]["confidence"], "low")

    def test_invalid_items_and_duplicate_ids_are_rejected(self):
        module = load_script("creator-opportunity-radar", "rank_opportunities.py")
        valid = {
            "id": "one", "title": "One", "audienceTension": "A concrete problem", "whyNow": "A dated change",
            "promise": "A result", "differentiation": "Direct proof", "formatHypothesis": "Short demo",
            "validationAction": "Interview users", "stopCondition": "No repeated need",
            "scores": {"relevance": 3, "timeliness": 3, "evidence": 3, "differentiation": 3, "feasibility": 3},
        }
        result = module.rank_opportunities({"opportunities": [None, valid, dict(valid)]})
        self.assertEqual(len(result["ranked"]), 1)
        self.assertEqual(len(result["rejected"]), 2)
        self.assertIn("duplicate opportunity id", result["rejected"][1]["reason"])


if __name__ == "__main__":
    unittest.main()
