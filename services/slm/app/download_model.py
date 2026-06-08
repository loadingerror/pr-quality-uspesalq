from transformers import AutoModelForCausalLM, AutoTokenizer

from .config import settings


def main() -> None:
    print(f"Downloading model into image cache: {settings.model_id}", flush=True)
    AutoTokenizer.from_pretrained(settings.model_id, trust_remote_code=True)
    AutoModelForCausalLM.from_pretrained(settings.model_id, trust_remote_code=True)
    print("Model download completed", flush=True)


if __name__ == "__main__":
    main()
