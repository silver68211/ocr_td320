"""Small dependency-light tests for consensus, validation and metrics."""

import unittest

from config import build_config
from metrics import evaluate_prediction
from utils import consensus_for_task


def leaf(value, state="filled"):
    return {"value": value, "state": state}


class CoreTests(unittest.TestCase):
    def test_profiles(self):
        self.assertEqual(build_config("simple").inference.minimum_agreement, 1)
        self.assertEqual(
            build_config("balanced").model.model_id, "Qwen/Qwen3-VL-2B-Instruct"
        )
        self.assertIn("adaptive", build_config("accurate").preprocessing.views)

    def test_consensus_preserves_original_spelling(self):
        first = {
            "name_english": leaf("CHAN TAI MAN"),
            "name_chinese": leaf("", "blank"),
            "identity_document_number": leaf("TEST001"),
        }
        second = {
            "name_english": leaf("CHAN  TAI MAN"),
            "name_chinese": leaf("", "blank"),
            "identity_document_number": leaf("TEST001"),
        }
        result, _audit = consensus_for_task("identity", [first, second], 2)
        self.assertEqual(result["name_english"]["value"], "CHAN TAI MAN")
        self.assertEqual(result["identity_document_number"]["state"], "filled")

    def test_disagreement_becomes_uncertain(self):
        responses = [
            {
                "name_english": leaf("CHAN"),
                "name_chinese": leaf("", "blank"),
                "identity_document_number": leaf("ABC1"),
            },
            {
                "name_english": leaf("CHEN"),
                "name_chinese": leaf("", "blank"),
                "identity_document_number": leaf("ABC1"),
            },
        ]
        result, audit = consensus_for_task("identity", responses, 2)
        self.assertEqual(result["name_english"]["state"], "uncertain")
        self.assertTrue(audit)

    def test_metrics(self):
        reference = {"name": "CHAN", "address": {"district": "SHA TIN"}}
        exact = evaluate_prediction(reference, reference)
        self.assertEqual(exact["field_exact_match_accuracy"], 1.0)
        self.assertEqual(exact["character_error_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
