import sys
import time
import json
from dataclasses import dataclass
from typing import Optional, List
from openai import OpenAI
# from tabulate import tabulate
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
PRICING_TIER = "Standard"

# Models to test (add/remove as you need)
MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-chat-latest",
    "gpt-5-codex",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
]

PROMPT = (
    """Enter Prompt Here"""
)

OUTPUT_CSV = "model_comparison_results.csv"
MAX_PREVIEW_CHARS = 240

# Rate limit pause between calls (seconds)
DELAY_BETWEEN_CALLS = float("0.5")

# Prices per 1M tokens for each tier (inputs, cached inputs, outputs) gathered from https://platform.openai.com/docs/pricing?latest-pricing=standard
PRICES = {
    "gpt-5": {
        "Standard": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    },
    "gpt-5-mini": {
        "Standard": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    },
    "gpt-5-nano": {
        "Standard": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    },
    "gpt-5-chat-latest": {
        "Standard": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    },
    "gpt-5-codex": {
        "Standard": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    },
    "gpt-4.1": {
        "Standard": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
    },
    "gpt-4.1-mini": {
        "Standard": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    },
    "gpt-4o": {
        "Standard": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    },
}

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
        print("Please set OPENAI_API_KEY at the start of the code", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

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
            text = getattr(resp, "output_text", None) or json.dumps(resp.dict(), indent=2)
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
                text = getattr(resp, "output_text", None) or json.dumps(resp.dict(), indent=2)
                usage = getattr(resp, "usage", None)
                ok = True
            except Exception as e2:
                err = f"{err or ''} | no-tools error: {e2}"

        if ok:
            try:
                # Extract usage safely
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0
                total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)

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

    rows = []
    for r in results:
        rows.append([
            r.model,
            "yes" if r.supports_browsing else "no",
            "ok" if r.ok else "error",
            r.input_tokens,
            r.cached_input_tokens,
            r.output_tokens,
            r.total_tokens,
            f"${r.price_usd:.6f}" if r.price_usd == r.price_usd else "n/a",
            r.output if r.ok else (r.error or "")
        ])

    headers = [
        "Model",
        "Browsing?",
        "Run",
        "Input",
        "Cached",
        "Output",
        "Total",
        f"Cost ({PRICING_TIER})",
        "Preview / Error"
    ]

    # print(tabulate(rows, headers=headers, tablefmt="github"))

    if OUTPUT_CSV:
        try:
            import pandas as pd
            df = pd.DataFrame([{
                "model": r.model,
                "supports_browsing": r.supports_browsing,
                "ok": r.ok,
                "error": r.error,
                "input_tokens": r.input_tokens,
                "cached_input_tokens": r.cached_input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "price_usd": r.price_usd,
                "output": r.output
            } for r in results])
            df.to_csv(OUTPUT_CSV, index=False)
            print(f"\nSaved results to {OUTPUT_CSV}")
        except Exception as e:
            print(f"\nFailed to save CSV: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
