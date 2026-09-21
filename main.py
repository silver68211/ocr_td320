"""Command-line entry point for adaptive, multi-layout form OCR."""

from __future__ import annotations

import argparse
import json
import time
import traceback
from collections.abc import Sequence
from pathlib import Path

from config import PipelineConfig, build_config
from metrics import evaluate_files
from model import VisionOCRModel
from preprocessing import PreprocessResult, preprocess_image
from utils import (
    PROMPTS,
    consensus_for_task,
    list_images,
    parse_json_object,
    validate_and_combine,
    write_json,
    write_outputs,
)


class FormOCRPipeline:
    """Connect preprocessing, model inference, consensus and validation."""

    def __init__(self, config: PipelineConfig, model: VisionOCRModel | None = None):
        self.config = config
        self.config.make_directories()
        self.model = model

    def load_model(self) -> VisionOCRModel:
        """Load the configured model lazily and reuse it across the batch."""

        if self.model is None:
            self.model = VisionOCRModel(self.config).load()
        return self.model

    def preprocess(self, image_path: Path | str) -> PreprocessResult:
        """Create aligned, enhanced, high-resolution crops for one form."""

        return preprocess_image(image_path, self.config)

    def process_image(self, image_path: Path | str) -> dict[str, object]:
        """Process one form and write all output/audit files.

        Every view is an independent OCR vote. Invalid JSON from one view is
        recorded and does not erase successful evidence from other views.
        """

        image_path = Path(image_path)
        started = time.perf_counter()
        preprocessed = self.preprocess(image_path)
        model = self.load_model()
        raw: dict[str, object] = {}
        consensus_results: dict[str, object] = {}
        consensus_audit = []

        for region_name, region_config in preprocessed.layout.regions.items():
            task = region_config.task
            prompt = PROMPTS[task]
            raw[task] = {}
            parsed_responses = []

            for view_name, crop_path in preprocessed.crops[region_name].items():
                try:
                    response = model.generate([crop_path], prompt)
                    parsed = parse_json_object(response)
                    raw[task][view_name] = {
                        "crop": str(crop_path),
                        "response": response,
                        "parsed": parsed,
                    }
                    parsed_responses.append(parsed)
                # A malformed response from one view must not discard other votes.
                except Exception as error:  # noqa: BLE001
                    raw[task][view_name] = {
                        "crop": str(crop_path),
                        "error": str(error),
                    }

            if not parsed_responses:
                raise RuntimeError(f"All OCR views failed for task: {task}")
            fields, task_audit = consensus_for_task(
                task,
                parsed_responses,
                self.config.inference.minimum_agreement,
            )
            consensus_results[task] = fields
            consensus_audit.extend(task_audit)

        data, audit = validate_and_combine(
            consensus_results,
            consensus_audit,
            form_id=preprocessed.layout.form_id,
        )
        audit.update(
            {
                "original_image": str(image_path),
                "model": self.config.model.model_id,
                "profile": self.config.profile,
                "form_type": preprocessed.layout.form_id,
                "form_name": preprocessed.layout.display_name,
                "preprocessing": preprocessed.metadata,
                "elapsed_seconds": round(time.perf_counter() - started, 2),
            }
        )
        folder = write_outputs(
            self.config.paths.output,
            image_path,
            data,
            audit,
            raw,
        )
        return {
            "image": image_path.name,
            "status": audit["status"],
            "output": str(folder),
            "elapsed_seconds": audit["elapsed_seconds"],
        }

    def run_batch(self, image_paths: Sequence[Path]) -> list[dict[str, object]]:
        """Process a batch while preserving failures in the summary."""

        summary = []
        for index, image_path in enumerate(image_paths, start=1):
            print(f"[{index}/{len(image_paths)}] {image_path.name}")
            try:
                result = self.process_image(image_path)
            # Batch processing must preserve later forms after one isolated failure.
            except Exception as error:  # noqa: BLE001
                result = {
                    "image": image_path.name,
                    "status": "error",
                    "error": str(error),
                }
                error_folder = self.config.paths.output / image_path.stem
                write_json(
                    error_folder / f"{image_path.stem}_error.json",
                    {**result, "traceback": traceback.format_exc()},
                )
            summary.append(result)
            print(" ", result["status"])
        write_json(self.config.paths.output / "batch_summary.json", summary)
        return summary


def select_images(config: PipelineConfig, requested: str | None = None) -> list[Path]:
    """Return all forms or a single case-insensitive stem/name match."""

    images = list_images(
        config.paths.figures,
        config.image_extensions,
        config.template_paths(),
    )
    if requested is None:
        return images
    selected = [
        path
        for path in images
        if path.name.casefold() == requested.casefold()
        or path.stem.casefold() == Path(requested).stem.casefold()
    ]
    if not selected:
        raise FileNotFoundError(
            f"No image matching {requested!r} in {config.paths.figures}"
        )
    return selected


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("simple", "balanced", "accurate", "maximum"),
        default="balanced",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--image", help="Process one filename or stem")
    parser.add_argument("--model-id", help="Override the profile model")
    parser.add_argument(
        "--layout",
        default="auto",
        help="Detect layout automatically (default) or force a form id such as td320",
    )
    parser.add_argument(
        "--preprocess-only",
        action="store_true",
        help="Create crops without loading model weights",
    )
    parser.add_argument("--prediction", type=Path, help="Prediction JSON to evaluate")
    parser.add_argument("--reference", type=Path, help="Ground-truth JSON to evaluate")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if bool(args.prediction) != bool(args.reference):
        raise SystemExit("--prediction and --reference must be supplied together")
    if args.prediction:
        print(json.dumps(evaluate_files(args.prediction, args.reference), indent=2))
        return

    config = build_config(args.profile, args.root)
    if args.model_id:
        config.model.model_id = args.model_id
    config.preprocessing.layout = args.layout.casefold()
    if config.preprocessing.layout != "auto":
        config.resolve_layout(config.preprocessing.layout)
    config.make_directories()
    images = select_images(config, args.image)
    if not images:
        raise SystemExit(f"No supported images found in {config.paths.figures}")

    pipeline = FormOCRPipeline(config)
    if args.preprocess_only:
        for image_path in images:
            result = pipeline.preprocess(image_path)
            print(
                image_path.name,
                "->",
                result.layout.form_id,
                "->",
                result.aligned_path.parent,
            )
        return
    pipeline.run_batch(images)


if __name__ == "__main__":
    main()
