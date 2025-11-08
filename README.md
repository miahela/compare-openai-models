# Compare Models

This script allows you to easily compare different OpenAI models by running the same prompt against each one and collecting their responses, token usage, and estimated pricing.

---

## 🚀 How to Use

### 1. Set Up Your Environment

Create a `.env` file in the project directory and add your OpenAI API key:

```
OPENAI_API_KEY=your_api_key_here
```


You can get your API key from the [OpenAI dashboard](https://platform.openai.com/account/api-keys).

---

### 2. Edit the Prompt

Open `compare_models.py` and replace the placeholder text:

```python
PROMPT = """Enter Prompt Here"""
```
with the prompt you want to test.

---

### 3. Run the Script

In your terminal, run:
```
python compare_models.py
```
The script will send your prompt to multiple models, wait briefly between requests, and log the results.

---

### 4. View the Results

Once the run is complete, the results will be saved to:
```
model_comparison_results.csv
```

This file includes details such as:
- Model name
- Whether browsing is supported
- Token usage (input, cached, output, total)
- Estimated cost
- Short preview of the model’s output

---

⚙️ Requirements
Install dependencies before running:
```
pip install openai python-dotenv pandas
```
(Optional) You can also install tabulate if you want to print formatted tables in the console.

---

🧩 Notes

The script automatically calculates estimated prices using predefined model pricing.

You can modify the list of models in the MODELS variable.

Default delay between API calls is 0.5 seconds to avoid rate limits.