"""Configuration for adaptive, multi-layout form OCR.

Each supported form owns a template, crop map and optional preprocessing
overrides. The pipeline identifies the layout before it aligns and crops the
page, so coordinates are never shared accidentally between different forms.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class RegionConfig:
    """A normalized crop and the extraction task applied to that crop."""

    task: str
    box: Box


@dataclass(frozen=True)
class LayoutConfig:
    """Template and preprocessing parameters for one known form layout."""

    form_id: str
    display_name: str
    template: Path
    regions: dict[str, RegionConfig]
    crop_margin: float | None = None
    crop_upscale: float | None = None
    max_skew_degrees: float | None = None


def td320_regions() -> dict[str, RegionConfig]:
    """Regions for TD320 (Rev. 01/2022), page 1."""

    return {
        "identity": RegionConfig("identity", (0.025, 0.175, 0.975, 0.300)),
        "residential": RegionConfig("residential", (0.025, 0.275, 0.985, 0.545)),
        "correspondence": RegionConfig(
            "correspondence", (0.025, 0.495, 0.985, 0.725)
        ),
        "declaration": RegionConfig("declaration", (0.025, 0.685, 0.985, 0.985)),
    }


def td555_regions() -> dict[str, RegionConfig]:
    """Regions for TD555 (Rev. 11/2024), page 1."""

    return {
        "identity": RegionConfig(
            "identity_with_birth", (0.020, 0.205, 0.980, 0.360)
        ),
        "e_contact": RegionConfig("e_contact", (0.020, 0.350, 0.985, 0.435)),
        "residential": RegionConfig("residential", (0.020, 0.420, 0.985, 0.635)),
        "correspondence": RegionConfig(
            "correspondence", (0.020, 0.625, 0.985, 0.875)
        ),
    }


def default_layouts(root: Path) -> dict[str, LayoutConfig]:
    """Return all layouts known by the detector."""

    figures = root / "figs"
    return {
        "td320": LayoutConfig(
            form_id="td320",
            display_name="TD320 driving licence particulars",
            template=figures / "td320_blank.png",
            regions=td320_regions(),
            crop_margin=0.008,
            crop_upscale=1.5,
        ),
        "td555": LayoutConfig(
            form_id="td555",
            display_name="TD555 learner's driving licence",
            template=figures / "td555_blank.png",
            regions=td555_regions(),
            crop_margin=0.006,
            crop_upscale=1.6,
        ),
    }


@dataclass
class PathConfig:
    """Input, intermediate and output locations."""

    figures: Path = Path("figs")
    preprocessed: Path = Path("preprocessed")
    output: Path = Path("output")
    model_cache: Path | None = None


@dataclass
class PreprocessConfig:
    """Controls layout detection, registration, enhancement and saved views."""

    layout: str = "auto"
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
    minimum_layout_inliers: int = 16
    minimum_layout_inlier_ratio: float = 0.20
    minimum_layout_margin: float = 1.08


@dataclass
class ModelConfig:
    """Model-loading options."""

    model_id: str = "Qwen/Qwen3-VL-2B-Instruct"
    load_in_4bit: bool = True
    device_map: str = "auto"
    allow_cpu_offload: bool = False
    gpu_memory: str | None = None
    cpu_memory: str | None = None
    torch_dtype: str = "auto"
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
    layouts: dict[str, LayoutConfig]
    example_name: str = "Chan"
    image_extensions: tuple[str, ...] = (
        ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"
    )

    def make_directories(self) -> None:
        for directory in (
            self.paths.figures,
            self.paths.preprocessed,
            self.paths.output,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def template_paths(self) -> tuple[Path, ...]:
        return tuple(layout.template for layout in self.layouts.values())

    def resolve_layout(self, form_id: str) -> LayoutConfig:
        try:
            return self.layouts[form_id]
        except KeyError as error:
            choices = ", ".join(sorted(self.layouts))
            raise ValueError(
                f"Unknown form layout {form_id!r}; choose {choices}"
            ) from error


def build_config(profile: str = "balanced", root: Path | str = ".") -> PipelineConfig:
    """Build one of four model/accuracy profiles."""

    root = Path(root)
    paths = PathConfig(
        figures=root / "figs",
        preprocessed=root / "preprocessed",
        output=root / "output",
    )
    preprocessing = PreprocessConfig()
    model = ModelConfig()
    inference = InferenceConfig()

    if profile == "simple":
        preprocessing.deskew = False
        preprocessing.views = ("original",)
        preprocessing.crop_upscale = 1.0
        inference.minimum_agreement = 1
    elif profile == "balanced":
        preprocessing.views = ("original", "clahe", "otsu")
    elif profile == "accurate":
        preprocessing.views = ("original", "clahe", "otsu", "adaptive")
        preprocessing.crop_upscale = 2.0
        model.model_id = "Qwen/Qwen3-VL-4B-Instruct"
        inference.max_image_edge = 2800
    elif profile == "maximum":
        preprocessing.views = ("original", "clahe", "otsu", "adaptive")
        preprocessing.crop_upscale = 2.0
        model.model_id = "Qwen/Qwen3-VL-8B-Instruct"
        inference.max_image_edge = 3200
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
        layouts=default_layouts(root),
    )
