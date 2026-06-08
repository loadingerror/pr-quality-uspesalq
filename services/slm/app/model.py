from __future__ import annotations

from dataclasses import dataclass

from .config import settings


@dataclass
class GenerationRequest:
    prompt: str
    max_new_tokens: int | None = None


class BaseGenerator:
    def generate(self, req: GenerationRequest) -> str:
        raise NotImplementedError


class MockGenerator(BaseGenerator):
    def generate(self, req: GenerationRequest) -> str:
        return """## Reviewer summary
Mock SLM mode: the model is disabled. The deterministic analyzer has already collected facts; review the report below.

## Main risks
Check the deterministic findings for secrets, risky Python patterns, dependency changes, and missing tests.

## What to check manually
Review business-logic correctness, test coverage, security impact, and backward compatibility.

## Questions for the PR author
Why was this implementation approach chosen? Which scenarios were tested? Is there any production risk?

## Suggested review attention level
Use the deterministic risk score as the primary attention signal."""


class TransformersGenerator(BaseGenerator):
    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(settings.model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            settings.model_id,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map="cpu",
        )
        self.model.eval()

    def generate(self, req: GenerationRequest) -> str:
        messages = [{"role": "user", "content": req.prompt}]
        if hasattr(self.tokenizer, "apply_chat_template"):
            text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = req.prompt
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=8192)
        max_new_tokens = req.max_new_tokens or settings.max_new_tokens
        with self.torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()


def build_generator() -> BaseGenerator:
    backend = settings.slm_backend.lower().strip()
    if backend == "mock":
        return MockGenerator()
    if backend == "transformers":
        return TransformersGenerator()
    raise ValueError(f"Unsupported SLM_BACKEND={settings.slm_backend}")
