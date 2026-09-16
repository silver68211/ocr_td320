# Modular TD320 form OCR

It retains the original directory convention:

```text
ocr_td320/
├── figs/                 # input scans and optional blank template
├── preprocessed/         # aligned crops and independent image views
├── output/               # final JSON/TXT, raw responses and audits
├── config.py
├── preprocessing.py
├── model.py
├── utils.py
├── metrics.py
├── main.py
└── run_pipeline.ipynb
```

## Accuracy methods

1. **Template alignment and deskewing** stabilize field locations.
2. **Fixed regional crops with upscaling** give small handwriting more visual
   tokens than a full-page request.
3. **Independent original/CLAHE/binary views** preserve faint strokes while
   still benefiting from enhanced contrast.
4. **Field-specific prompts and schemas** reduce leakage between residential
   and correspondence sections.
5. **Agreement, validation and review routing** accept consistent evidence and
   flag disagreements instead of guessing.

## Profiles

| Profile | Model | Views | Intended use |
|---|---|---|---|
| `simple` | Qwen3-VL-2B | original | quick baseline |
| `balanced` | Qwen3-VL-2B 4-bit | original, CLAHE, Otsu | recommended default |
| `accurate` | Qwen3-VL-4B 4-bit | four views | larger GPU |
| `maximum` | Qwen3-VL-8B 4-bit | four views | high-VRAM node |

Profiles are starting points, not benchmark conclusions. Use `metrics.py` and
your labelled forms to select the best profile empirically.

## Setup

```bash
conda activate ocr
python -m pip install -r requirements.txt
hf auth login
```

Copy forms into `figs/`. If available, save the border-only blank form as:

```text
figs/td320_form_borders_only.png
```

## Run

Preprocess `Chan` without loading the model:

```bash
python main.py --profile balanced --image Chan --preprocess-only
```

Run `Chan` end to end:

```bash
python main.py --profile balanced --image Chan
```

Run every image:

```bash
python main.py --profile balanced
```

Use a custom model:

```bash
python main.py --profile balanced --model-id Qwen/Qwen3-VL-4B-Instruct
```

## Evaluation

Create manually checked ground truth with the same keys as an English output
JSON, then run:

```bash
python main.py \
  --prediction output/Chan/Chan_English.json \
  --reference ground_truth/Chan.json
```

Reported metrics are field exact-match accuracy, character error rate, mean
field edit similarity, and nonblank precision/recall/F1. Exact match should be
the primary metric for identity numbers, telephone numbers and dates.

## Important behavior

- The original image is never overwritten.
- Binary PNGs use visible values 0/255; no unnecessary `.npy` files are saved.
- The pipeline does not copy one name field into another.
- Raw responses and every crop are retained for audit.
- `passed_automated_checks` means structural checks passed, not that a human
  verified every character.

