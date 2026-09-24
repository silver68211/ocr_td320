from pathlib import Path

import pandas as pd
from tabulate import tabulate

from config import build_config
from metrics import evaluate_files


config = build_config(profile="accurate", root=Path("."))

output_root = config.paths.output
ground_truth_root = Path("ground_truth")

# Metrics shown in the final table.
# "field_count" has been removed.
metric_columns = {
    "field_exact_match_accuracy": "Field exact accuracy",
    "character_error_rate": "Character error rate",
    "mean_field_similarity": "Mean field similarity",
    "nonblank_precision": "Nonblank precision",
    "nonblank_recall": "Nonblank recall",
    "nonblank_f1": "Nonblank F1",
}

rows = []
missing_references = []
missing_predictions = []
evaluation_errors = []


# Search all folders inside output/.
for output_folder in sorted(
    output_root.iterdir(),
    key=lambda path: path.name.casefold(),
):
    if not output_folder.is_dir():
        continue

    filename = output_folder.name
    prediction_path = output_folder / f"{filename}_English.json"

    # Support both possible ground-truth naming conventions:
    # ground_truth/Lee_reference.json
    # ground_truth/Lee.json
    reference_candidates = [
        ground_truth_root / f"{filename}_reference.json",
        ground_truth_root / f"{filename}.json",
    ]

    reference_path = next(
        (path for path in reference_candidates if path.exists()),
        None,
    )

    if not prediction_path.exists():
        missing_predictions.append(filename)
        continue

    if reference_path is None:
        missing_references.append(filename)
        continue

    try:
        report = evaluate_files(
            prediction_path=prediction_path,
            reference_path=reference_path,
        )
    except Exception as error:
        evaluation_errors.append((filename, str(error)))
        continue

    row = {"File": filename}

    for metric_key, column_name in metric_columns.items():
        row[column_name] = report[metric_key]

    rows.append(row)


if not rows:
    print("No prediction and ground-truth pairs were found.")

else:
    results = pd.DataFrame(rows).set_index("File")

    # Macro-average: every file receives the same weight.
    results.loc["AVERAGE"] = results.mean(numeric_only=True)

    formatted_results = results.copy()

    # Display every metric as a percentage.
    for column in formatted_results.columns:
        formatted_results[column] = formatted_results[column].map(
            lambda value: f"{100 * value:.2f}%"
        )

    # Restore File as a normal column for tabulate.
    formatted_results = formatted_results.reset_index()

    print("\nOCR evaluation summary:\n")

    print(
        tabulate(
            formatted_results,
            headers="keys",
            tablefmt="grid",
            showindex=False,
            stralign="left",
            numalign="right",
        )
    )


if missing_references:
    print("\nSkipped because no ground truth was found:")

    for filename in missing_references:
        print(f"  - {filename}")


if missing_predictions:
    print("\nSkipped because no English prediction was found:")

    for filename in missing_predictions:
        print(f"  - {filename}")


if evaluation_errors:
    print("\nFiles that could not be evaluated:")

    for filename, error in evaluation_errors:
        print(f"  - {filename}: {error}")