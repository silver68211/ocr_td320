# Modular TD320 Form OCR

A modular OCR pipeline for extracting structured English and Chinese information from TD320 application forms using Qwen3-VL vision-language models.

The pipeline combines document preprocessing, form alignment, region-based extraction, multi-view OCR, validation, and quantitative evaluation.

## Features

- Reads form images from the `figs/` directory.
- Preserves original images and saves processed images separately.
- Supports deskewing and template-based alignment.
- Extracts predefined form regions for more focused recognition.
- Generates original, CLAHE-enhanced, Otsu-binary, and adaptive-binary views.
- Supports multiple Qwen3-VL model sizes and 4-bit quantization.
- Uses field-specific prompts and structured JSON output.
- Compares OCR results obtained from different image views.
- Flags conflicting or invalid results for manual review.
- Produces separate English and Chinese output files.
- Provides field-level and character-level evaluation metrics.

## Repository Structure

```text
ocr_td320/
├── figs/                  # Original form images and optional blank template
├── preprocessed/          # Processed images, aligned forms, and region crops
├── output/                # OCR results, raw responses, and audit reports
├── ground_truth/          # Manually verified reference data
├── config.py              # Paths, model profiles, prompts, and settings
├── preprocessing.py       # Image enhancement, alignment, and cropping
├── model.py               # Model loading and OCR inference
├── utils.py               # Parsing, validation, and output utilities
├── metrics.py             # OCR evaluation metrics
├── main.py                # Command-line entry point
├── test_core.py           # Core unit tests
├── run_pipeline.ipynb     # Optional notebook interface
├── requirements.txt       # Python dependencies
└── README.md
```

## Requirements

- Python 3.10 or later
- Conda or another Python environment manager
- CUDA-compatible GPU recommended
- Hugging Face account for authenticated model downloads

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/silver68211/ocr_td320.git
cd ocr_td320
```

### 2. Create a Conda environment

```bash
conda create -n ocr python=3.12
conda activate ocr
```

### 3. Install the dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Authenticate with Hugging Face

```bash
hf auth login
```

### 5. Verify CUDA availability

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU count:', torch.cuda.device_count())"
```

If CUDA is available, display the GPU name:

```bash
python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU available')"
```

## Input Data

Place the form images in the `figs/` directory:

```text
figs/
├── Chan.png
├── sample_02.jpg
└── sample_03.png
```

Supported image formats are:

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`
- `.tif`
- `.tiff`
- `.bmp`

An optional border-only blank form can be used for template alignment:

```text
figs/td320_form_borders_only.png
```

The template image is excluded automatically from the OCR input batch.

## Usage

### Display command-line options

```bash
python main.py --help
```

### Preprocess one image

```bash
python main.py \
  --profile balanced \
  --image Chan \
  --preprocess-only
```

### Process one image

```bash
python main.py \
  --profile balanced \
  --image Chan
```

The image name can be supplied with or without its file extension.

For example, both commands are valid:

```bash
python main.py --profile balanced --image Chan
python main.py --profile balanced --image Chan.png
```

### Process all images

```bash
python main.py --profile balanced
```

### Use a custom model

```bash
python main.py \
  --profile balanced \
  --model-id Qwen/Qwen3-VL-4B-Instruct
```

## Model Profiles

| Profile | Model | Quantization | Image views | Intended use |
|---|---|---:|---|---|
| `simple` | Qwen3-VL-2B | None | Original | Fast baseline |
| `balanced` | Qwen3-VL-2B | 4-bit | Original, CLAHE, Otsu | Recommended default |
| `accurate` | Qwen3-VL-4B | 4-bit | Four views | Higher accuracy |
| `maximum` | Qwen3-VL-8B | 4-bit | Four views | High-memory GPU |

Select a profile using the `--profile` option:

```bash
python main.py --profile accurate
```

The profiles are starting configurations. Their accuracy and resource usage should be evaluated on representative forms before deployment.

## Preprocessing Methods

The pipeline supports the following preprocessing methods.

### Deskewing

Corrects small rotations in scanned or photographed forms.

### Template alignment

Aligns an input form with the blank border template so that predefined crop coordinates remain consistent.

### CLAHE enhancement

Improves local contrast while limiting excessive amplification of image noise.

### Otsu thresholding

Automatically selects a global threshold and creates a black-and-white image.

### Adaptive thresholding

Uses local thresholds to handle uneven illumination and shadows.

### Region cropping

Divides the form into predefined sections so that the model can process relevant fields independently.

## Output Structure

Each input image receives a separate output directory:

```text
output/Chan/
├── Chan_English.txt
├── Chan_English.json
├── Chan_Chinese.txt
├── Chan_Chinese.json
├── Chan_audit.json
└── Chan_raw.json
```

The generated files contain:

| File | Description |
|---|---|
| `*_English.json` | Structured English extraction |
| `*_Chinese.json` | Structured Chinese extraction |
| `*_English.txt` | Human-readable English output |
| `*_Chinese.txt` | Human-readable Chinese output |
| `*_audit.json` | Validation results and manual-review items |
| `*_raw.json` | Unmodified model responses |

Processed images and regional crops are saved under:

```text
preprocessed/<image_name>/
```

A summary of a complete batch run is saved as:

```text
output/batch_summary.json
```

## Evaluation

Place manually verified reference files in the `ground_truth/` directory:

```text
ground_truth/
└── Chan.json
```

The reference JSON must use the same field names and structure as the predicted English JSON.

Run the evaluation with:

```bash
python main.py \
  --prediction output/Chan/Chan_English.json \
  --reference ground_truth/Chan.json
```

The evaluation reports the following metrics:

| Metric | Description |
|---|---|
| Field exact-match accuracy | Fraction of fields matching the reference exactly |
| Character error rate | Character-level edit distance normalized by reference length |
| Mean field similarity | Average edit similarity across evaluated fields |
| Nonblank precision | Accuracy of predicted nonempty fields |
| Nonblank recall | Coverage of nonempty reference fields |
| Nonblank F1 score | Harmonic mean of nonblank precision and recall |

Exact-match accuracy is especially important for:

- Identity-document numbers
- Telephone numbers
- Dates
- Room and floor identifiers
- Other structured numeric fields

## Configuration

The primary settings are defined in `config.py`.

Configurable options include:

- Input, preprocessing, output, and ground-truth directories
- Model identifier
- Model profile
- Quantization settings
- Generation parameters
- Maximum image dimensions
- Enabled preprocessing views
- Template image path
- Form-region coordinates
- Field-specific prompts
- Expected JSON schemas
- Validation rules
- Review thresholds

This design allows the pipeline to run as either a lightweight baseline or a more accurate multi-view OCR system.

## Running Tests

Run the core test suite with:

```bash
python -m unittest -v test_core.py
```

The tests cover:

- Configuration loading
- Image discovery
- Preprocessing functions
- Response parsing
- Field normalization
- Validation rules
- Evaluation metrics

## Troubleshooting

### No supported images found in `figs`

Confirm that the directory exists and contains supported image files:

```bash
find figs -maxdepth 1 -type f
```

Also confirm that the program is being executed from the repository root:

```bash
pwd
ls
```

### CUDA is unavailable

Check whether the operating system detects the GPU:

```bash
nvidia-smi
```

Then check whether PyTorch can access it:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

### GPU out-of-memory error

Use a smaller profile:

```bash
python main.py --profile simple
```

Alternatively, reduce image dimensions or the number of preprocessing views in `config.py`.

### Hugging Face authentication warning

Authenticate with:

```bash
hf auth login
```

Verify the active account:

```bash
hf auth whoami
```

### Disk quota exceeded

Check available storage and cache usage:

```bash
df -h
du -sh ~/.cache/huggingface ~/.cache/pip ~/.conda/pkgs
```

Remove unused package caches when appropriate:

```bash
conda clean --all
python -m pip cache purge
```

## Important Notes

- Original images are never overwritten.
- Processed images are stored separately under `preprocessed/`.
- Binary PNG files use visible pixel values of `0` and `255`.
- Raw model responses are retained for inspection.
- Conflicting multi-view results are flagged instead of silently accepted.
- Blank fields are not automatically copied from unrelated fields.
- Passing automated validation does not guarantee that every extracted character is correct.
- Human verification is recommended for critical identity and contact information.
