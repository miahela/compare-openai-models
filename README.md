# Compare OpenAI Models

Run the same prompt against several OpenAI models and export response previews, token usage, and estimated token costs to CSV. Use the results to inspect responses before choosing a model for an automation workflow.

The [sample CSV](examples/sample_results.csv) is synthetic and contains no client data.

## Run on Windows

Requires Python 3.10 or newer and an OpenAI API key with access to the chosen models.

~~~powershell
cd path\to\compare-openai-models
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe compare_models.py
Import-Csv .\model_comparison_results.csv | Format-Table
~~~

Set the key, prompt, and comma-separated model IDs in .env. Shell variables take precedence. The example selects one model for a short live test. Without configuration the original multi-model list is used. Requests incur API charges.

## Behavior

Each model first receives a Responses API request with web_search. Any failure triggers one attempt without tools. supports_browsing means the tool-enabled request was accepted, not that a search occurred. Successful fallback clears the first error.

.env.example documents configuration. Relative output paths use the working directory. CSV export overwrites existing files. Failed models are exported alongside successful ones with exit status 1. Export failure also returns status 1.

## Stack

Python, OpenAI Python SDK, python-dotenv, and standard-library CSV export. No pandas dependency is needed.

## Offline tests

~~~powershell
py -B -m unittest discover -s tests -v
~~~

Tests use fake responses and need no key, installed SDK, or network.

## Models and prices

Edit models_config.json to change the default model list, pricing tier, and USD rates per million input, cached input, and output tokens. MODELS in .env overrides the configured list. The config is loaded relative to the script.

Prices last checked: **unknown**. The original table had no recorded verification date. It was carried over without online verification on **2026-10-30**; this is not a price-check date. The config records prices_last_checked as null. After checking the linked pricing source, update the rates and record the actual check date here and in the config.

## Known limits

- Model availability and the historical prices in models_config.json have not been checked against current official OpenAI documentation. Update prices before relying on estimates.
- Costs cover tokens only, excluding search fees and other charges. Unknown models produce nan; unknown pricing tiers fall back to Standard.
- Tool-enabled and fallback responses may have different context.
- Previews stop at 240 characters. Full responses, quality scores, and latency are not exported.
- Any tool-request error triggers fallback, including authentication and network errors. Requests have a 60-second timeout and SDK retries disabled. Delay does not guarantee rate-limit compliance.
- Review generated previews and errors before sharing because they may contain prompt or account details.

Live API validation has not been run. Offline tests cover local behavior with fake responses.
