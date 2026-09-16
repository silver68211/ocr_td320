"""Configuration objects and ready-to-use accuracy profiles.

Normal users should edit only :func:`build_config` arguments or the returned
dataclass values.  Paths, preprocessing, model loading and inference settings
are intentionally separated so that experiments are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class RegionConfig:
    """A normalized crop and the extraction task applied to that crop.

    ``box`` is ``(left, top, right, bottom)`` expressed as fractions of image
    width and height.  This makes the regions independent of scan resolution.
    """

    task: str
    box: Box


def default_regions() -> dict[str, RegionConfig]:
    """Return conservative TD320 regions with margins around entered values."""

    return {
        "identity": RegionConfig("identity", (0.025, 0.170, 0.975, 0.305)),
        "residential": RegionConfig("residential", (0.025, 0.275, 0.985, 0.545)),
        "correspondence": RegionConfig("correspondence", (0.025, 0.495, 0.985, 0.725)),
        "declaration": RegionConfig("declaration", (0.025, 0.685, 0.985, 0.985)),
    }


@dataclass
class PathConfig:
    """Input, intermediate and output locations."""

    figures: Path = Path("figs")
    preprocessed: Path = Path("preprocessed")
    output: Path = Path("output")
    template: Path = Path("figs/td320_blank.png")
    model_cache: Path | None = None


@dataclass
class PreprocessConfig:
    """Controls registration, enhancement, crops and saved image views."""

    align_to_template: bool = True
    deskew: bool = True
    max_skew_degrees: float = 5.0
    views: tuple[str, ...] = ("original", "clahe", "otsu")
    clahe_clip_limit: float = 2.0
    clahe_grid_size: int = 8
    adaptive_block_size: int = 31
    adaptive_constant: int = 12
    crop_upscale: float = 1.5
    crop_margin: float = 0.01
    orb_features: int = 5000
    minimum_template_matches: int = 25
    regions: dict[str, RegionConfig] = field(default_factory=default_regions)


@dataclass
class ModelConfig:
    """Model-loading options, from a small local model to a larger VLM."""

    model_id: str = "Qwen/Qwen3-VL-2B-Instruct"
    load_in_4bit: bool = True
    device_map: str = "auto"
    allow_cpu_offload: bool = False
    gpu_memory: str | None = None
    cpu_memory: str | None = None
    torch_dtype: str = "auto"  # auto, bfloat16 or float16
    trust_remote_code: bool = False
    low_cpu_mem_usage: bool = True


@dataclass
class InferenceConfig:
    """Generation and agreement settings."""

    max_image_edge: int = 2400
    max_new_tokens: int = 700
    do_sample: bool = False
    temperature: float | None = None
    repetition_penalty: float = 1.02
    minimum_agreement: int = 2
    save_all_views: bool = True


@dataclass
class PipelineConfig:
    """Complete configuration passed to the OCR pipeline."""

    profile: str
    paths: PathConfig
    preprocessing: PreprocessConfig
    model: ModelConfig
    inference: InferenceConfig
    example_name: str = "Chan"
    image_extensions: tuple[str, ...] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
    )

    def make_directories(self) -> None:
        """Create writable pipeline directories if they do not exist."""

        for directory in (
            self.paths.figures,
            self.paths.preprocessed,
            self.paths.output,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def build_config(profile: str = "balanced", root: Path | str = ".") -> PipelineConfig:
    """Build one of four practical complexity profiles.

    Parameters
    ----------
    profile:
        ``simple`` uses one original crop and the 2B model; ``balanced`` adds
        three image views and consensus; ``accurate`` uses a 4B model and four
        views; ``maximum`` selects the 8B model and is intended for large GPUs.
    root:
        Project directory containing ``figs``. Relative output paths are
        resolved below this directory.

    Returns
    -------
    PipelineConfig
        Independent configuration object safe to modify for one experiment.
    """

    root = Path(root)
    paths = PathConfig(
        figures=root / "figs",
        preprocessed=root / "preprocessed",
        output=root / "output",
        template=root / "figs" / "td320_blank.png",
    )
    preprocessing = PreprocessConfig()
    model = ModelConfig()
    inference = InferenceConfig()

    if profile == "simple":
        preprocessing.align_to_template = False
        preprocessing.deskew = False
        preprocessing.views = ("original",)
        preprocessing.crop_upscale = 1.0
        model.model_id = "Qwen/Qwen3-VL-2B-Instruct"
        inference.minimum_agreement = 1
    elif profile == "balanced":
        preprocessing.views = ("original", "clahe", "otsu")
        model.model_id = "Qwen/Qwen3-VL-2B-Instruct"
        inference.minimum_agreement = 2
    elif profile == "accurate":
        preprocessing.views = ("original", "clahe", "otsu", "adaptive")
        preprocessing.crop_upscale = 2.0
        model.model_id = "Qwen/Qwen3-VL-4B-Instruct"
        inference.max_image_edge = 2800
        inference.minimum_agreement = 2
    elif profile == "maximum":
        preprocessing.views = ("original", "clahe", "otsu", "adaptive")
        preprocessing.crop_upscale = 2.0
        model.model_id = "Qwen/Qwen3-VL-8B-Instruct"
        inference.max_image_edge = 3200
        inference.minimum_agreement = 2
    else:
        raise ValueError(
            f"Unknown profile {profile!r}. Choose simple, balanced, accurate, or maximum."
        )

    return PipelineConfig(
        profile=profile,
        paths=paths,
        preprocessing=preprocessing,
        model=model,
        inference=inference,
    )
