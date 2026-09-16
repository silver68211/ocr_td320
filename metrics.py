"""Field-level metrics for OCR and structured extraction experiments."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path


def flatten_fields(value: Mapping[str, object], prefix: str = "") -> dict[str, str]:
    """Flatten nested dictionaries into dot-separated string fields."""

    flat: dict[str, str] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flat.update(flatten_fields(item, name))
        else:
            flat[name] = "" if item is None else str(item)
    return flat


def normalize(value: object) -> str:
    """Normalize Unicode and whitespace for evaluation, not for saved output."""

    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return re.sub(r"\s+", " ", text)


def levenshtein(reference: str, prediction: str) -> int:
    """Compute edit distance using O(min(n,m)) memory."""

    if len(reference) < len(prediction):
        reference, prediction = prediction, reference
    previous = list(range(len(prediction) + 1))
    for row, reference_character in enumerate(reference, start=1):
        current = [row]
        for column, prediction_character in enumerate(prediction, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1]
                    + (reference_character != prediction_character),
                )
            )
        previous = current
    return previous[-1]


def evaluate_prediction(
    prediction: Mapping[str, object],
    reference: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate exact match, CER, edit similarity and nonblank detection.

    Character error rate (CER) is total edit distance divided by the total
    number of reference characters. Nonblank precision/recall/F1 measures
    whether the pipeline correctly distinguishes filled from blank fields.
    """

    predicted = flatten_fields(prediction)
    expected = flatten_fields(reference)
    field_names = sorted(set(predicted) | set(expected))
    per_field: dict[str, object] = {}
    exact = 0
    total_edits = 0
    total_reference_characters = 0
    true_positive = false_positive = false_negative = 0

    for field in field_names:
        predicted_value = normalize(predicted.get(field, ""))
        expected_value = normalize(expected.get(field, ""))
        distance = levenshtein(expected_value, predicted_value)
        denominator = max(1, len(expected_value))
        is_exact = predicted_value == expected_value
        exact += int(is_exact)
        total_edits += distance
        total_reference_characters += len(expected_value)

        predicted_nonblank = bool(predicted_value)
        expected_nonblank = bool(expected_value)
        true_positive += int(predicted_nonblank and expected_nonblank)
        false_positive += int(predicted_nonblank and not expected_nonblank)
        false_negative += int(not predicted_nonblank and expected_nonblank)

        per_field[field] = {
            "exact": is_exact,
            "edit_distance": distance,
            "similarity": max(0.0, 1.0 - distance / denominator),
            "prediction": predicted.get(field, ""),
            "reference": expected.get(field, ""),
        }

    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "field_count": len(field_names),
        "field_exact_match_accuracy": exact / max(1, len(field_names)),
        "character_error_rate": total_edits / max(1, total_reference_characters),
        "mean_field_similarity": sum(item["similarity"] for item in per_field.values())
        / max(1, len(per_field)),
        "nonblank_precision": precision,
        "nonblank_recall": recall,
        "nonblank_f1": f1,
        "per_field": per_field,
    }


def evaluate_files(
    prediction_path: Path | str, reference_path: Path | str
) -> dict[str, object]:
    """Load two JSON files and return :func:`evaluate_prediction` results."""

    prediction = json.loads(Path(prediction_path).read_text(encoding="utf-8"))
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    if not isinstance(prediction, dict) or not isinstance(reference, dict):
        raise TypeError("Prediction and reference JSON must contain objects")
    return evaluate_prediction(prediction, reference)
