import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from core import conversation_store, graph_pipeline
from services import ltm_module, rag_module, tools_external


class ConversationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "conversations.sqlite3"
        self.default_database_path = conversation_store.DATABASE_PATH
        self.database_patch = patch.object(
            conversation_store,
            "DATABASE_PATH",
            self.database_path,
        )
        self.database_patch.start()

    def tearDown(self) -> None:
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_data_paths_remain_under_backend_data(self) -> None:
        backend_dir = Path(__file__).resolve().parents[1]

        self.assertEqual(
            self.default_database_path,
            backend_dir / "data" / "ltm" / "conversations.sqlite3",
        )
        self.assertEqual(ltm_module.LTM_DIR, backend_dir / "data" / "ltm")
        self.assertEqual(
            rag_module.KB_DIR,
            backend_dir / "data" / "knowledge_base",
        )
        self.assertEqual(
            tools_external.MOCK_DIR,
            backend_dir / "data" / "mock_external",
        )
        self.assertTrue((rag_module.KB_DIR / "sample_kb.txt").is_file())
        self.assertTrue((tools_external.MOCK_DIR / "logs_student.json").is_file())

    def test_persists_conversations_and_turns_by_session_id(self) -> None:
        conversation_store.create_conversation("session-a", "user-a")
        conversation_store.create_conversation("session-b", "user-b")
        conversation_store.record_conversation_turn(
            "session-a",
            "first question",
            "first answer",
            "success",
        )
        conversation_store.record_conversation_turn(
            "session-a",
            "second question",
            "second answer",
            "handoff_triggered",
        )

        conversations = conversation_store.list_conversations("user-a")
        details = conversation_store.get_conversation_details(
            "session-a",
            "user-a",
        )

        self.assertEqual([item["session_id"] for item in conversations], ["session-a"])
        self.assertEqual(conversations[0]["turn_count"], 2)
        self.assertEqual(conversations[0]["last_user_message"], "second question")
        self.assertEqual(conversations[0]["last_status"], "handoff_triggered")
        self.assertIsNotNone(details)
        self.assertEqual(
            [turn["user_message"] for turn in details["turns"]],
            ["first question", "second question"],
        )
        self.assertIsNone(
            conversation_store.get_conversation_details("session-a", "user-b")
        )

    def test_session_can_be_processed_by_another_worker(self) -> None:
        conversation_store.create_conversation("session-c", "user-c")
        with patch.dict(graph_pipeline.SESSION_STORE, {}, clear=True):
            with (
                patch(
                    "core.graph_pipeline.trace_conversation",
                    side_effect=lambda *args, **kwargs: nullcontext(None),
                ),
                patch(
                    "core.graph_pipeline.trace_step",
                    side_effect=lambda *args, **kwargs: nullcontext(None),
                ),
                patch("core.graph_pipeline.update_observation"),
                patch("core.graph_pipeline.fetch_user_config", return_value={}),
                patch("core.graph_pipeline.fetch_recent_logs", return_value=[]),
                patch("core.graph_pipeline.query_kb", return_value=[]),
                patch("core.graph_pipeline.query_ltm", return_value=[]),
                patch(
                    "core.graph_pipeline.triage_node",
                    return_value={"decision": "respond", "rationale": "ok"},
                ),
                patch(
                    "core.graph_pipeline.run_diagnostics_chain",
                    return_value={
                        "overall_status": "OK",
                        "recommendation": "stable",
                        "steps": [],
                    },
                ),
                patch(
                    "core.graph_pipeline.generate_troubleshooting_plan",
                    return_value={"troubleshooting_plan": "check the cable"},
                ),
                patch(
                    "core.graph_pipeline.generate_text",
                    return_value={"respuesta": "Revisa el cable."},
                ),
            ):
                result = graph_pipeline.run_multimodal_session(
                    "session-c",
                    "No enciende",
                    None,
                )

        details = conversation_store.get_conversation_details(
            "session-c",
            "user-c",
        )
        self.assertEqual(result["session_id"], "session-c")
        self.assertEqual(details["turn_count"], 1)
        self.assertEqual(details["turns"][0]["user_message"], "No enciende")
        self.assertEqual(
            details["turns"][0]["assistant_message"],
            "Revisa el cable.",
        )


if __name__ == "__main__":
    unittest.main()
