"""Document preprocessing, template registration and multi-view crop creation.

The module implements three of the accuracy improvements used by the pipeline:

1. optional geometric registration to a blank template;
2. high-resolution, fixed-position field crops; and
3. multiple independent image views instead of destructively replacing the
   original with a single thresholded version.

OpenCV images use BGR channel order. Files written by this module can be read
normally by PIL, browsers and the model processor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from config import Box, PipelineConfig


@dataclass
class PreprocessResult:
    """Paths and diagnostics produced for one source image."""

    original_path: Path
    aligned_path: Path
    crops: dict[str, dict[str, Path]]
    metadata: dict[str, object]


def read_image(path: Path | str, grayscale: bool = False) -> np.ndarray:
    """Read an image and raise a useful error instead of returning ``None``.

    Parameters
    ----------
    path:
        Image path.
    grayscale:
        If true, return a two-dimensional uint8 array. Otherwise return BGR.
    """

    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    image = cv2.imread(str(path), flag)
    if image is None:
        raise FileNotFoundError(f"OpenCV could not read image: {Path(path).resolve()}")
    return image


def write_image(path: Path | str, image: np.ndarray) -> Path:
    """Write an image, creating its parent directory, and return its path."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV could not write image: {path.resolve()}")
    return path


def estimate_skew_angle(image: np.ndarray, max_degrees: float = 5.0) -> float:
    """Estimate small page rotation from long horizontal lines.

    The TD320 form contains many long horizontal rules. A probabilistic Hough
    transform detects those rules, and the median near-horizontal angle gives a
    robust estimate. Angles outside ``max_degrees`` are ignored to avoid
    rotating the page from vertical borders or handwriting strokes.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    minimum_length = max(80, image.shape[1] // 5)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 1800,
        threshold=100,
        minLineLength=minimum_length,
        maxLineGap=20,
    )
    if lines is None:
        return 0.0

    angles = []
    # OpenCV versions expose HoughLinesP as either (N, 1, 4) or (N, 4).
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if abs(angle) <= max_degrees:
            angles.append(angle)
    return float(np.median(angles)) if angles else 0.0


def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate around the page centre while preserving the original dimensions."""

    if abs(angle) < 0.05:
        return image.copy()
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def align_to_template(
    image: np.ndarray,
    template: np.ndarray,
    maximum_features: int = 5000,
    minimum_matches: int = 25,
) -> tuple[np.ndarray, dict[str, object]]:
    """Register a filled form to a blank template using ORB and a homography.

    Returns the aligned image and diagnostics. If reliable registration cannot
    be established, the unmodified image is returned with ``aligned=False``;
    the pipeline therefore remains usable rather than failing the whole batch.
    """

    source_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    detector = cv2.ORB_create(nfeatures=maximum_features)
    source_keypoints, source_descriptors = detector.detectAndCompute(source_gray, None)
    target_keypoints, target_descriptors = detector.detectAndCompute(target_gray, None)

    if source_descriptors is None or target_descriptors is None:
        return image.copy(), {"aligned": False, "reason": "No ORB descriptors"}

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(source_descriptors, target_descriptors, k=2)
    good = []
    for pair in pairs:
        # A descriptor can occasionally have fewer than two neighbours.
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
            good.append(pair[0])
    if len(good) < minimum_matches:
        return image.copy(), {
            "aligned": False,
            "reason": "Too few reliable template matches",
            "matches": len(good),
        }

    source_points = np.float32(
        [source_keypoints[match.queryIdx].pt for match in good]
    ).reshape(-1, 1, 2)
    target_points = np.float32(
        [target_keypoints[match.trainIdx].pt for match in good]
    ).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(
        source_points, target_points, cv2.RANSAC, 4.0
    )
    if homography is None:
        return image.copy(), {"aligned": False, "reason": "Homography failed"}

    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    if inliers < max(12, minimum_matches // 2):
        return image.copy(), {
            "aligned": False,
            "reason": "Too few homography inliers",
            "matches": len(good),
            "inliers": inliers,
        }

    height, width = template.shape[:2]
    aligned = cv2.warpPerspective(
        image,
        homography,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return aligned, {
        "aligned": True,
        "matches": len(good),
        "inliers": inliers,
    }


def create_views(image: np.ndarray, config) -> dict[str, np.ndarray]:
    """Create independent OCR views from one aligned BGR image.

    Supported names are ``original``, ``gray``, ``clahe``, ``otsu`` and
    ``adaptive``. Binary images are saved with values 0 and 255 because literal
    0/1 PNGs appear black to image decoders and are not appropriate OCR input.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(
        clipLimit=config.clahe_clip_limit,
        tileGridSize=(config.clahe_grid_size, config.clahe_grid_size),
    ).apply(gray)
    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    block_size = config.adaptive_block_size
    if block_size < 3 or block_size % 2 == 0:
        raise ValueError("adaptive_block_size must be an odd integer >= 3")
    adaptive = cv2.adaptiveThreshold(
        clahe,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        config.adaptive_constant,
    )
    available = {
        "original": image,
        "gray": gray,
        "clahe": clahe,
        "otsu": otsu,
        "adaptive": adaptive,
    }
    unknown = set(config.views) - set(available)
    if unknown:
        raise ValueError(f"Unknown preprocessing view(s): {sorted(unknown)}")
    return {name: available[name] for name in config.views}


def crop_normalized(
    image: np.ndarray,
    box: Box,
    margin: float = 0.0,
    upscale: float = 1.0,
    interpolation: int = cv2.INTER_CUBIC,
) -> np.ndarray:
    """Crop a normalized region, add a fractional margin and optionally upscale."""

    left, top, right, bottom = box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"Invalid normalized crop box: {box}")

    height, width = image.shape[:2]
    left = max(0.0, left - margin)
    top = max(0.0, top - margin)
    right = min(1.0, right + margin)
    bottom = min(1.0, bottom + margin)
    x1, y1 = round(left * width), round(top * height)
    x2, y2 = round(right * width), round(bottom * height)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError(f"Crop {box} produced an empty image")
    if upscale > 1.0:
        crop = cv2.resize(
            crop,
            None,
            fx=upscale,
            fy=upscale,
            interpolation=interpolation,
        )
    return crop


def preprocess_image(
    image_path: Path | str, config: PipelineConfig
) -> PreprocessResult:
    """Align, deskew, enhance, crop and save every configured view.

    Outputs are placed under ``preprocessed/<image>/<region>/<view>.png``.
    Keeping each view in a separate file prevents the overwrite bug in the
    original notebook and provides auditable evidence for every prediction.
    """

    image_path = Path(image_path)
    image = read_image(image_path)
    work = image.copy()
    metadata: dict[str, object] = {
        "original_size": [image.shape[1], image.shape[0]],
        "profile": config.profile,
        "views": list(config.preprocessing.views),
    }

    template_path = config.paths.template
    if config.preprocessing.align_to_template and template_path.is_file():
        template = read_image(template_path)
        work, alignment = align_to_template(
            work,
            template,
            maximum_features=config.preprocessing.orb_features,
            minimum_matches=config.preprocessing.minimum_template_matches,
        )
        metadata["template_alignment"] = alignment
    elif config.preprocessing.align_to_template:
        metadata["template_alignment"] = {
            "aligned": False,
            "reason": f"Template not found: {template_path}",
        }

    if config.preprocessing.deskew:
        angle = estimate_skew_angle(work, config.preprocessing.max_skew_degrees)
        # estimate_skew_angle reports the page-line angle; rotate by its negative.
        work = rotate_image(work, -angle)
        metadata["deskew_angle_degrees"] = round(angle, 4)

    image_folder = config.paths.preprocessed / image_path.stem
    aligned_path = write_image(image_folder / "aligned.png", work)
    views = create_views(work, config.preprocessing)
    crop_paths: dict[str, dict[str, Path]] = {}

    for region_name, region in config.preprocessing.regions.items():
        crop_paths[region_name] = {}
        for view_name, view_image in views.items():
            crop = crop_normalized(
                view_image,
                region.box,
                margin=config.preprocessing.crop_margin,
                upscale=config.preprocessing.crop_upscale,
                interpolation=(
                    cv2.INTER_NEAREST
                    if view_name in {"otsu", "adaptive"}
                    else cv2.INTER_CUBIC
                ),
            )
            output_path = image_folder / region_name / f"{view_name}.png"
            crop_paths[region_name][view_name] = write_image(output_path, crop)

    metadata["regions"] = {
        name: asdict(region) for name, region in config.preprocessing.regions.items()
    }
    return PreprocessResult(image_path, aligned_path, crop_paths, metadata)
