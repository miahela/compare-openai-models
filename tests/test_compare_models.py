import csv
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace as NS

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("app_test", Path(__file__).resolve().parents[1] / "compare_models.py")
        self.app = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"app_test": self.app, "openai": NS(OpenAI=None), "dotenv": NS(load_dotenv=lambda: None)}), patch.dict(os.environ, {}, clear=True):
            spec.loader.exec_module(self.app)

    def export(self, responses, failed=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.csv"
            self.app.OPENAI_API_KEY = "fake"
            self.app.MODELS = ["gpt-4.1-mini"]
            self.app.DELAY_BETWEEN_CALLS = 0
            self.app.OUTPUT_CSV = str(path)
            create = Mock(side_effect=responses)
            self.app.OpenAI = lambda **kwargs: NS(responses=NS(create=create))
            if failed:
                with self.assertRaises(SystemExit) as error:
                    self.app.main()
                self.assertEqual(error.exception.code, 1)
            else:
                self.app.main()
            with path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle)), create

    def test_fallback_csv_clears_error_and_handles_missing_total(self):
        response = NS(output_text="Hello, shop!", usage=NS(input_tokens=100, output_tokens=20, total_tokens=None))
        rows, create = self.export([RuntimeError("unsupported tool"), response])
        self.assertEqual(create.call_count, 2)
        self.assertNotIn("tools", create.call_args.kwargs)
        self.assertEqual(rows[0]["error"], "")
        self.assertEqual(rows[0]["total_tokens"], "120")
        self.assertEqual(rows[0]["output"], "Hello, shop!")

    def test_empty_text_does_not_dump_metadata(self):
        rows, _ = self.export([NS(output_text="", usage=None)])
        self.assertEqual(rows[0]["output"], "")
        self.assertEqual(rows[0]["ok"], "True")

    def test_failed_models_export_and_exit_nonzero(self):
        rows, _ = self.export([RuntimeError("tool failed"), RuntimeError("plain failed")], failed=True)
        self.assertEqual(rows[0]["ok"], "False")
        self.assertIn("plain failed", rows[0]["error"])

    def test_cached_price(self):
        self.assertAlmostEqual(self.app.compute_price("gpt-4.1-mini", "Standard", 100, 40, 20), (60*.4 + 40*.1 + 20*1.6)/1000000)

    def test_export_failure_exits_nonzero(self):
        self.app.OPENAI_API_KEY = "fake"
        self.app.MODELS = []
        self.app.OpenAI = lambda **kwargs: None
        with tempfile.TemporaryDirectory() as folder:
            self.app.OUTPUT_CSV = folder
            with self.assertRaises(SystemExit) as error:
                self.app.main()
            self.assertEqual(error.exception.code, 1)

    def test_models_and_prices_are_loaded_from_config(self):
        import json
        config = json.loads((Path(__file__).resolve().parents[1] / "models_config.json").read_text())
        self.assertEqual(self.app.MODELS, config["models"])
        self.assertEqual(self.app.PRICES, config["prices"])
        self.assertEqual(self.app.PRICING_TIER, config["pricing_tier"])
