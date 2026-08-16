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
RUN_LIVE_SKILL_TESTS = os.environ.get("RUN_LIVE_SKILL_TESTS") == "1"


def load_script(skill: str, filename: str):
    path = ROOT / "skills" / skill / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"{skill}_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillPackagingTests(unittest.TestCase):
    def test_default_prompts_reference_the_complete_skill_name(self):
        for skill_directory in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
            metadata = (skill_directory / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${skill_directory.name}", metadata, skill_directory.name)


class PaperEvidenceRadarTests(unittest.TestCase):
    def test_natural_multiword_query_is_not_forced_into_one_exact_phrase(self):
        module = load_script("paper-evidence-radar", "arxiv_search.py")
        query = module.build_search_query("video generation character consistency")
        self.assertEqual(
            query,
            'all:"video" AND all:"generation" AND all:"character" AND all:"consistency"',
        )
        self.assertEqual(module.build_search_query("video generation", "phrase"), 'all:"video generation"')

    def test_parses_arxiv_atom_into_stable_evidence(self):
        module = load_script("paper-evidence-radar", "arxiv_search.py")
        items = module.parse_atom((SKILLS / "paper-evidence-radar" / "evals" / "files" / "arxiv.xml").read_bytes())
        self.assertEqual(items[0]["arxivId"], "2608.12345")
        self.assertEqual(items[0]["version"], 2)
        self.assertEqual(items[0]["authors"], ["Ada Researcher", "Bo Scientist"])
        self.assertEqual(items[0]["primaryCategory"], "cs.CV")
        self.assertEqual(module.filter_recent(items, date(2026, 8, 1)), items)


class GithubRepositoryResearchTests(unittest.TestCase):
    def test_remote_url_credentials_query_and_fragment_are_redacted(self):
        module = load_script("github-repository-research", "repo_snapshot.py")
        self.assertEqual(
            module._safe_remote("https://user:secret@github.com/org/repo.git?token=secret#fragment"),
            "https://github.com/org/repo.git",
        )
        self.assertEqual(module._safe_remote("git@github.com:org/repo.git"), "github.com:org/repo.git")

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
        self.assertTrue(result["comments"][0]["author"].startswith("commenter-"))
        self.assertTrue(result["boundaries"]["commentAuthorsRedacted"])
        self.assertEqual(result["coverage"]["commentLimit"], 1)

    def test_comment_pseudonyms_are_scoped_to_one_video(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        row = {"rpid": 1, "member": {"mid": "123"}, "content": {"message": "hello"}}
        first = module._normalize_comment(row, "BV1xx411c7mD")
        second = module._normalize_comment(row, "BV1yy411c7mD")
        self.assertNotEqual(first["author"], second["author"])

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


@unittest.skipUnless(RUN_LIVE_SKILL_TESTS, "set RUN_LIVE_SKILL_TESTS=1 for public network smoke tests")
class PublicLiveSkillTests(unittest.TestCase):
    def test_arxiv_natural_query_returns_current_primary_links(self):
        module = load_script("paper-evidence-radar", "arxiv_search.py")
        papers, api_query = module.fetch_arxiv("video generation character consistency", 3)
        self.assertGreater(len(papers), 0)
        self.assertIn(" AND ", api_query)
        self.assertTrue(all(str(paper["url"]).startswith("https://arxiv.org/abs/") for paper in papers))

    def test_bilibili_public_metadata_and_comments_are_available_without_identity(self):
        module = load_script("bilibili-content-research", "bilibili_public.py")
        result = module.collect_public("BV1xx411c7mD", 2)
        self.assertIn(result["status"], {"complete", "partial"})
        self.assertTrue(result["video"]["title"])
        self.assertGreater(len(result["comments"]), 0)
        self.assertTrue(all(comment["author"].startswith("commenter-") for comment in result["comments"]))
        self.assertFalse(result["boundaries"]["authenticated"])

    def test_public_github_shallow_clone_can_be_snapshotted(self):
        module = load_script("github-repository-research", "repo_snapshot.py")
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "agentskills"
            subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/agentskills/agentskills.git", str(repository)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = module.build_snapshot(repository)
        self.assertEqual(result["git"]["branch"], "main")
        self.assertEqual(result["git"]["status"], [])
        self.assertIn("LICENSE", result["licenseFiles"])


class WeChatChatExportTests(unittest.TestCase):
    def test_setup_check_offers_manual_risk_path_when_no_key_is_ready(self):
        module = load_script("wechat-chat-export", "wechat_setup.py")
        not_ready = {
            "status": "not_ready",
            "platform": {"wechatVersion": "4.1.11"},
            "keyBundle": {"found": False},
            "database": {"contactDecryptable": False, "messageDecryptable": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "WeChat.app"
            data = root / "xwechat_files"
            (data / "account" / "db_storage").mkdir(parents=True)
            app.mkdir()
            with mock.patch.object(module.wechat_export, "doctor", return_value=not_ready), mock.patch.object(
                module, "OFFICIAL_APP", app
            ), mock.patch.object(module, "DATA_ROOT", data), mock.patch.object(
                module, "DEBUG_APP", root / "debug" / "WeChat-debug.app"
            ), mock.patch.object(module, "_tool_status", return_value={
                "ditto": True, "codesign": True, "lldb": True, "open": True, "ps": True,
            }), mock.patch.object(module.platform, "machine", return_value="arm64"), mock.patch.object(
                module.sys, "platform", "darwin"
            ):
                result = module.setup_check()
        self.assertEqual(result["status"], "manual_risk_setup_available")
        self.assertTrue(result["risk"]["acknowledgementRequired"])
        self.assertFalse(result["risk"]["automaticCapture"])
        self.assertTrue(result["environment"]["reviewedWechatVersion"])

    def test_setup_check_does_not_offer_capture_for_an_unreviewed_wechat_version(self):
        module = load_script("wechat-chat-export", "wechat_setup.py")
        not_ready = {
            "status": "not_ready",
            "platform": {"wechatVersion": "4.2.0"},
            "keyBundle": {"found": False},
            "database": {"contactDecryptable": False, "messageDecryptable": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "WeChat.app"
            data = root / "xwechat_files"
            (data / "account" / "db_storage").mkdir(parents=True)
            app.mkdir()
            with mock.patch.object(module.wechat_export, "doctor", return_value=not_ready), mock.patch.object(
                module, "OFFICIAL_APP", app
            ), mock.patch.object(module, "DATA_ROOT", data), mock.patch.object(
                module, "_tool_status", return_value={
                    "ditto": True, "codesign": True, "lldb": True, "open": True, "ps": True,
                }
            ), mock.patch.object(module.platform, "machine", return_value="arm64"), mock.patch.object(
                module.sys, "platform", "darwin"
            ):
                result = module.setup_check()
        self.assertEqual(result["status"], "unsupported_or_incomplete_environment")
        self.assertFalse(result["environment"]["reviewedWechatVersion"])
        self.assertFalse(result["risk"]["acknowledgementRequired"])

    def test_default_key_discovery_skips_invalid_bundle_and_uses_next_valid_one(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = root / "invalid.json"
            valid = root / "valid.json"
            invalid.write_text("not json", encoding="utf-8")
            valid.write_text(json.dumps({"keys": {str(root / "contact.db"): "a" * 64}}), encoding="utf-8")
            with mock.patch.object(module, "DEFAULT_KEY_FILES", (invalid, valid)):
                selected, keys = module._load_keys(None)
        self.assertEqual(selected, valid.resolve())
        self.assertEqual(len(keys), 1)

    def test_zero_to_one_setup_is_dry_run_by_default_and_requires_exact_ack(self):
        module = load_script("wechat-chat-export", "wechat_setup.py")
        with tempfile.TemporaryDirectory() as temporary:
            debug_root = Path(temporary) / ".wechat-chat-export"
            debug_app = debug_root / "WeChat-debug.app"
            with mock.patch.object(module, "DEBUG_ROOT", debug_root):
                result = module.prepare_debug_copy(debug_app, execute=False, acknowledgement=None)
                self.assertEqual(result["status"], "dry_run")
                self.assertFalse(result["willModifyOriginalApp"])
                self.assertFalse(debug_app.exists())
                with mock.patch.object(module.subprocess, "run") as run:
                    with self.assertRaises(module.SetupError) as raised:
                        module.prepare_debug_copy(debug_app, execute=True, acknowledgement=None)
                    run.assert_not_called()
            self.assertEqual(raised.exception.code, "risk_not_acknowledged")

    def test_setup_refuses_debug_copy_outside_private_root(self):
        module = load_script("wechat-chat-export", "wechat_setup.py")
        with self.assertRaises(module.SetupError) as raised:
            module.prepare_debug_copy(Path("/Applications/Other-WeChat.app"), execute=False, acknowledgement=None)
        self.assertEqual(raised.exception.code, "unsafe_debug_path")

    def test_capture_command_is_pid_bound_and_never_run_by_setup_script(self):
        module = load_script("wechat-chat-export", "wechat_setup.py")
        with mock.patch.object(module, "_debug_processes", return_value=[4321]):
            result = module.capture_command(module.DEBUG_APP, 4321, 180)
        self.assertEqual(result["status"], "manual_command_ready")
        self.assertFalse(result["runsAutomatically"])
        self.assertIn("sudo lldb --batch -p 4321", result["shellCommand"])
        self.assertIn("wechat_key_hook.py", result["shellCommand"])
        self.assertIn("sign out and sign back in", result["manualTrigger"])

    def test_key_hook_derives_verifies_and_writes_private_bundle_without_preview(self):
        module = load_script("wechat-chat-export", "wechat_key_hook.py")
        passphrase = bytes(range(32))
        page = bytearray((index % 251) + 1 for index in range(module.PAGE_SIZE))
        salt = bytes(range(16, 32))
        page[:module.SALT_SIZE] = salt
        encryption_key = module.derive_sqlcipher4_key(passphrase, bytes(page))
        mac_salt = bytes(value ^ 0x3A for value in salt)
        mac_key = module.hashlib.pbkdf2_hmac("sha512", encryption_key, mac_salt, 2, dklen=module.KEY_SIZE)
        mac = module.hmac.new(
            mac_key,
            bytes(page[module.SALT_SIZE:module.PAGE_SIZE - module.RESERVE_SIZE + module.SALT_SIZE]),
            module.hashlib.sha512,
        )
        mac.update(module.struct.pack("<I", 1))
        page[module.PAGE_SIZE - module.HMAC_SIZE:module.PAGE_SIZE] = mac.digest()
        self.assertTrue(module.verify_sqlcipher4_key(encryption_key, bytes(page)))
        self.assertFalse(module.verify_sqlcipher4_key(b"x" * 32, bytes(page)))
        self.assertEqual(module._breakpoint_specs("arm64")[0][0], "CCKeyDerivationPBKDF")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "private" / "keys.json"
            written = module.write_key_bundle({"/synthetic/contact.db": encryption_key.hex()}, str(destination))
            payload = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(written.stat().st_mode & 0o777, 0o600)
            self.assertEqual(written.parent.stat().st_mode & 0o777, 0o700)
            self.assertNotIn("preview", json.dumps(payload).lower())
            self.assertEqual(payload["keys"]["/synthetic/contact.db"], encryption_key.hex())

    def test_key_hook_requires_contact_and_message_from_the_same_account(self):
        module = load_script("wechat-chat-export", "wechat_key_hook.py")
        root = "/private/xwechat_files"
        mixed = {
            f"{root}/account-a/db_storage/contact/contact.db": "a" * 64,
            f"{root}/account-b/db_storage/message/message_0.db": "b" * 64,
        }
        self.assertIsNone(module.ready_account(mixed, root))
        mixed[f"{root}/account-a/db_storage/message/message_0.db"] = "c" * 64
        self.assertEqual(module.ready_account(mixed, root), "account-a")

    def test_doctor_reports_missing_key_without_attempting_acquisition(self):
        module = load_script("wechat-chat-export", "wechat_export.py")
        result = module.doctor("/path/that/does/not/exist.json")
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["error"]["code"], "missing_key_bundle")
        self.assertFalse(result["capabilities"]["acquireKeys"])
        self.assertTrue(result["capabilities"]["guidedFirstTimeSetup"])
        self.assertIn("wechat_setup.py check", result["nextAction"])

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
            self.assertTrue(result["visualSignal"]["visiblePixelRangeDetected"])
            self.assertTrue(result["audioSignal"]["signalAboveMinus60Db"])
            self.assertGreaterEqual(result["coverage"]["framesExtracted"], 1)
            self.assertLessEqual(result["coverage"]["framesExtracted"], 4)
            self.assertTrue((output / "evidence.json").is_file())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_distinguishes_black_silent_media_from_missing_streams(self):
        module = load_script("reference-video-deconstruction", "extract_video_evidence.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "black-silent.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=black:size=320x240:rate=24",
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
                    "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(video),
                ],
                check=True,
            )
            result = module.extract(video, root / "evidence", max_frames=4)
        self.assertTrue(result["probe"]["hasAudio"])
        self.assertEqual(result["visualSignal"]["blackFrameRatio"], 1.0)
        self.assertFalse(result["visualSignal"]["visiblePixelRangeDetected"])
        self.assertFalse(result["audioSignal"]["signalAboveMinus60Db"])

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
    def test_non_object_payload_and_non_array_evidence_are_rejected(self):
        module = load_script("creator-opportunity-radar", "rank_opportunities.py")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            module.rank_opportunities([])
        with self.assertRaisesRegex(ValueError, "evidence must be an array"):
            module.rank_opportunities({"asOfDate": "2026-08-17", "evidence": {}})

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
            "whyNowDate": "2026-08-16",
            "promise": "A result", "differentiation": "Direct proof", "formatHypothesis": "Short demo",
            "validationAction": "Interview users", "stopCondition": "No repeated need",
            "scores": {"relevance": 3, "timeliness": 3, "evidence": 3, "differentiation": 3, "feasibility": 3},
        }
        result = module.rank_opportunities({"asOfDate": "2026-08-17", "opportunities": [None, valid, dict(valid)]})
        self.assertEqual(len(result["ranked"]), 1)
        self.assertEqual(len(result["rejected"]), 2)
        self.assertIn("duplicate opportunity id", result["rejected"][1]["reason"])

    def test_unknown_evidence_cannot_create_high_confidence(self):
        module = load_script("creator-opportunity-radar", "rank_opportunities.py")
        payload = {
            "asOfDate": "2026-08-17",
            "evidence": [{"id": "known", "sourceType": "github", "capturedAt": "2026-08-16"}],
            "opportunities": [{
                "id": "fabricated", "title": "Fabricated confidence", "audienceTension": "A specific pain",
                "whyNow": "A current change", "whyNowDate": "2026-08-16", "promise": "A result",
                "differentiation": "Direct proof", "formatHypothesis": "Demo", "validationAction": "Test",
                "stopCondition": "No repeated need", "evidenceIds": ["known", "invented-1", "invented-2"],
                "sourceTypes": ["github", "paper", "community"],
                "scores": {"relevance": 5, "timeliness": 5, "evidence": 5, "differentiation": 5, "feasibility": 5},
            }],
        }
        result = module.rank_opportunities(payload)
        self.assertEqual(result["ranked"], [])
        self.assertIn("unknown evidence ids", result["rejected"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
