import csv
import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

# Resolve config relative to this script, independent of the working directory.
CONFIG_PATH = Path(__file__).resolve().with_name("models_config.json")
with CONFIG_PATH.open(encoding="utf-8") as config_file:
    CONFIG = json.load(config_file)
PRICING_TIER = CONFIG["pricing_tier"]
MODELS = [m.strip() for m in os.getenv("MODELS", ",".join(CONFIG["models"])).split(",") if m.strip()]
PROMPT = (
    os.getenv("PROMPT", "Write three tips for organizing a bookshop.")
)

OUTPUT_CSV = os.getenv("OUTPUT_CSV", "model_comparison_results.csv")
MAX_PREVIEW_CHARS = 240

# Rate limit pause between calls (seconds)
DELAY_BETWEEN_CALLS = float(os.getenv("DELAY_BETWEEN_CALLS", "0.5"))

# USD per million tokens; verification metadata lives in the config.
PRICES = CONFIG["prices"]

@dataclass
class RunResult:
    model: str
    supports_browsing: bool
    ok: bool
    error: Optional[str]
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    price_usd: float
    output: str

def compute_price(model: str, tier: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> float:
    if model not in PRICES:
        return float("nan")
    tier = tier if tier in PRICES[model] else "Standard"
    rates = PRICES[model][tier]

    billable_input = max(input_tokens - max(cached_input_tokens, 0), 0)
    cached_input = max(min(cached_input_tokens, input_tokens), 0)
    output = max(output_tokens, 0)

    cost = (
                   billable_input * rates["input"]
                   + cached_input * rates["cached_input"]
                   + output * rates["output"]
           ) / 1_000_000.0
    return cost




def main():
    api_key = OPENAI_API_KEY
    if not api_key:
        print("Please set OPENAI_API_KEY in your environment or .env file", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=0)

    prompt = PROMPT
    results: List[RunResult] = []

    for model in MODELS:
        time.sleep(DELAY_BETWEEN_CALLS)

        supports_browsing = False
        ok = False
        err = None
        input_tokens = cached_input_tokens = output_tokens = total_tokens = 0
        output = ""
        price_usd = float("nan")

        # First, try with web_search tool enabled
        try:
            resp = client.responses.create(
                model=model,
                tools=[{"type": "web_search"}],
                input=prompt,
            )
            text = getattr(resp, "output_text", None) or ""
            usage = getattr(resp, "usage", None)

            supports_browsing = True  # if it didn't throw, we treat as supported
            ok = True
        except Exception as e:
            err = str(e)

        # If browsing attempt failed, try again without tools (to still compare quality/pricing)
        if not ok:
            try:
                resp = client.responses.create(
                    model=model,
                    input=prompt,
                )
                text = getattr(resp, "output_text", None) or ""
                usage = getattr(resp, "usage", None)
                ok = True
                err = None
            except Exception as e2:
                err = f"{err or ''} | no-tools error: {e2}"

        if ok:
            try:
                # Extract usage safely
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0
                total_tokens = (getattr(usage, "total_tokens", None) or (input_tokens + output_tokens))

                # cached tokens may be nested under input_tokens_details
                cached_input_tokens = 0
                details = getattr(usage, "input_tokens_details", None)
                if details is not None:
                    cached_input_tokens = getattr(details, "cached_tokens", 0) or 0

                price_usd = compute_price(model, PRICING_TIER, input_tokens, cached_input_tokens, output_tokens)

                output = text.strip().replace("\n", " ")
                if len(output) > MAX_PREVIEW_CHARS:
                    output = output[:MAX_PREVIEW_CHARS] + "…"

            except Exception as e:
                ok = False
                err = f"post-process error: {e}"

        results.append(
            RunResult(
                model=model,
                supports_browsing=supports_browsing,
                ok=ok,
                error=err,
                input_tokens=int(input_tokens),
                cached_input_tokens=int(cached_input_tokens),
                output_tokens=int(output_tokens),
                total_tokens=int(total_tokens),
                price_usd=float(price_usd) if price_usd == price_usd else float("nan"),
                output=output,
            )
        )

    if OUTPUT_CSV:
        try:
            from dataclasses import asdict
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(RunResult.__dataclass_fields__))
                writer.writeheader()
                writer.writerows(asdict(r) for r in results)
            print(f"Saved {len(results)} results to {OUTPUT_CSV}")
        except OSError as exc:
            print(f"Failed to save CSV: {exc}", file=sys.stderr)
            sys.exit(1)
    if any(not r.ok for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()
