"""Model loading and deterministic multimodal generation.

Only this module depends on Transformers model classes. The rest of the
pipeline can therefore be tested without downloading model weights.
"""

from __future__ import annotations

import gc
from collections.abc import Sequence
from pathlib import Path

from config import PipelineConfig
from PIL import Image, ImageOps


class VisionOCRModel:
    """Thin wrapper around a Hugging Face image-to-text chat model."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.processor = None
        self.model = None

    def load(self) -> VisionOCRModel:
        """Load the configured model once and return ``self``.

        Four-bit NF4 quantization is optional. CPU offload is disabled by
        default because it can consume substantial RAM and disk; enable it only
        explicitly through the configuration.
        """

        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable to PyTorch on this Jupyter node.")

        model_config = self.config.model
        if model_config.torch_dtype == "bfloat16":
            dtype = torch.bfloat16
        elif model_config.torch_dtype == "float16":
            dtype = torch.float16
        else:
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

        options = {
            "device_map": model_config.device_map,
            "low_cpu_mem_usage": model_config.low_cpu_mem_usage,
            "dtype": dtype,
            "trust_remote_code": model_config.trust_remote_code,
        }
        if self.config.paths.model_cache is not None:
            options["cache_dir"] = str(self.config.paths.model_cache)

        maximum_memory = {}
        if model_config.gpu_memory:
            maximum_memory[0] = model_config.gpu_memory
        if model_config.cpu_memory:
            maximum_memory["cpu"] = model_config.cpu_memory
        if maximum_memory:
            options["max_memory"] = maximum_memory

        if model_config.load_in_4bit:
            from transformers import BitsAndBytesConfig

            options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_use_double_quant=True,
                llm_int8_enable_fp32_cpu_offload=model_config.allow_cpu_offload,
            )

        self.processor = AutoProcessor.from_pretrained(
            model_config.model_id,
            cache_dir=(
                str(self.config.paths.model_cache)
                if self.config.paths.model_cache is not None
                else None
            ),
            trust_remote_code=model_config.trust_remote_code,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_config.model_id,
            **options,
        ).eval()
        return self

    def _input_device(self):
        """Return the device that should receive token and pixel tensors."""

        import torch

        if self.model is None:
            raise RuntimeError("Model has not been loaded")
        for parameter in self.model.parameters():
            if parameter.device.type != "meta":
                return parameter.device
        return torch.device("cuda:0")

    def _prepare_image(self, path: Path | str) -> Image.Image:
        """Open one crop, correct EXIF orientation and limit its longest edge."""

        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        maximum = self.config.inference.max_image_edge
        if max(image.size) > maximum:
            scale = maximum / max(image.size)
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        return image

    def generate(self, image_paths: Sequence[Path | str], prompt: str) -> str:
        """Generate a deterministic response for one or more image crops.

        Parameters
        ----------
        image_paths:
            Paths supplied in order. The normal pipeline uses one crop per call
            so that separate preprocessing views remain independent votes.
        prompt:
            Field-specific extraction instructions and exact JSON schema.
        """

        import torch

        if self.model is None or self.processor is None:
            raise RuntimeError("Call VisionOCRModel.load() before generate().")

        content = [
            {"type": "image", "image": self._prepare_image(path)}
            for path in image_paths
        ]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self._input_device())

        generation = {
            "max_new_tokens": self.config.inference.max_new_tokens,
            "do_sample": self.config.inference.do_sample,
            "repetition_penalty": self.config.inference.repetition_penalty,
        }
        if self.config.inference.do_sample and self.config.inference.temperature:
            generation["temperature"] = self.config.inference.temperature

        with torch.inference_mode():
            output = self.model.generate(**inputs, **generation)
        new_tokens = output[0, inputs["input_ids"].shape[1] :]
        if len(new_tokens) >= self.config.inference.max_new_tokens:
            raise RuntimeError(
                "Model response reached max_new_tokens and may be incomplete."
            )
        return self.processor.decode(new_tokens, skip_special_tokens=True).strip()


def release_gpu_memory(model_wrapper: VisionOCRModel | None = None) -> None:
    """Delete model references and release unused PyTorch CUDA cache."""

    if model_wrapper is not None:
        model_wrapper.model = None
        model_wrapper.processor = None
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass
