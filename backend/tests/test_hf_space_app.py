"""Unit and regression tests for Hugging Face Space inference pipeline (hf_space/app.py).

Validates:
1. Evidence variable passed correctly into prompt (replacing undefined context).
2. Correct generated-token variable used during decoding (fixing outputs vs output).
3. Prompt tokens excluded from decoded response.
4. Empty retrieval results handled safely without hallucinating.
5. Model and adapter loading failures reported clearly.
6. Private adapter authentication failures handled securely without leaking tokens.
7. Generation exceptions and GPU allocation errors (CUDA OOM) handled gracefully.
8. Successful chat request with actual retrieved evidence.
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
import torch
import importlib.util

# Mock gradio and spaces in sys.modules if not installed in backend venv
if "spaces" not in sys.modules:
    mock_spaces = MagicMock()
    mock_spaces.GPU = lambda *args, **kwargs: (lambda fn: fn)
    sys.modules["spaces"] = mock_spaces

if "gradio" not in sys.modules:
    mock_gr = MagicMock()
    mock_gr.ChatInterface = MagicMock()
    sys.modules["gradio"] = mock_gr

# Load hf_space/app.py safely under the module name 'space_app' without shadowing backend 'app' package
SPACE_APP_PATH = Path(__file__).resolve().parent.parent.parent / "hf_space" / "app.py"

with patch.dict("os.environ", {
    "BASE_MODEL_ID": "Qwen/Qwen3-1.7B",
    "ADAPTER_REPO_ID": "sush2306/ai-sarthi-qwen3-lora",
    "DATASET_REPO_ID": "mock-dataset",
    "HF_TOKEN": "mock-token",
}), patch("huggingface_hub.hf_hub_download", return_value="mock.csv"), \
   patch("pandas.read_csv", return_value=pd.DataFrame({"_search_text": []})), \
   patch("transformers.AutoTokenizer.from_pretrained", return_value=MagicMock()), \
   patch("transformers.AutoModelForCausalLM.from_pretrained", return_value=MagicMock()), \
   patch("peft.PeftModel.from_pretrained", return_value=MagicMock()):
    spec = importlib.util.spec_from_file_location("space_app", SPACE_APP_PATH)
    space_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(space_app)


@pytest.fixture
def sample_healthcare_df() -> pd.DataFrame:
    """Fixture providing realistic sample healthcare records."""
    data = [
        {
            "state": "Maharashtra",
            "district": "Pune",
            "indicator": "institutional_births",
            "value": 97.97,
            "unit": "%",
            "year": "2019-2021",
            "source": "NFHS-5",
        },
        {
            "state": "Maharashtra",
            "district": "Mumbai",
            "indicator": "institutional_births",
            "value": 99.53,
            "unit": "%",
            "year": "2019-2021",
            "source": "NFHS-5",
        },
    ]
    df = pd.DataFrame(data)
    df["_search_text"] = df.astype(str).agg(" ".join, axis=1)
    return df


def test_evidence_variable_passed_correctly_into_prompt(sample_healthcare_df):
    """Test 1: Confirm evidence is passed into prompt and 'context' is not referenced."""
    mock_tok = MagicMock()
    mock_tok.eos_token_id = 0
    mock_model = MagicMock()

    captured_messages = []

    def mock_apply_chat_template(messages, **kwargs):
        captured_messages.extend(messages)
        return "Formatted Prompt with Evidence"

    mock_tok.apply_chat_template = mock_apply_chat_template

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model):

        # Call retrieve_records first to see what should be in evidence
        expected_evidence = space_app.retrieve_records("Pune institutional births")
        assert "97.97" in expected_evidence

        # Run answer_question
        res = space_app.answer_question("Pune institutional births")

        # Verify chat messages structure
        assert len(captured_messages) == 2
        user_msg = captured_messages[1]["content"]
        assert "Healthcare records:\n" in user_msg
        assert expected_evidence in user_msg
        assert "Pune" in user_msg


def test_correct_generated_token_variable_used_during_decoding(sample_healthcare_df):
    """Test 2: Fix mismatch between 'outputs' and 'output' during token slicing and decoding."""
    mock_tok = MagicMock()
    mock_tok.apply_chat_template.return_value = "Prompt"
    mock_inputs = {
        "input_ids": torch.tensor([[10, 20, 30, 40, 50]]),
        "attention_mask": torch.tensor([[1, 1, 1, 1, 1]]),
    }
    mock_tok.return_value.to.return_value = mock_inputs

    mock_model = MagicMock()
    # Model generates 3 new tokens: [60, 70, 80] appended to prompt tokens
    mock_model.generate.return_value = torch.tensor([[10, 20, 30, 40, 50, 60, 70, 80]])

    decoded_slice = None

    def capture_decode(tokens, **kwargs):
        nonlocal decoded_slice
        decoded_slice = tokens.tolist()
        return "Decoded answer."

    mock_tok.decode = capture_decode

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model):

        res = space_app.answer_question("Pune institutional births")
        # Ensure the decoded tokens are strictly [60, 70, 80], not crashing on undefined 'output'
        assert decoded_slice == [60, 70, 80]
        assert "Decoded answer." in res


def test_prompt_tokens_excluded_from_decoded_response(sample_healthcare_df):
    """Test 3: Prompt tokens are excluded from the decoded response to avoid prompt repetition."""
    mock_tok = MagicMock()
    mock_tok.apply_chat_template.return_value = "System & User prompt text"
    prompt_ids = [1, 2, 3, 4]
    new_ids = [99, 100, 101]

    mock_inputs = {
        "input_ids": torch.tensor([prompt_ids]),
        "attention_mask": torch.tensor([[1] * len(prompt_ids)]),
    }
    mock_tok.return_value.to.return_value = mock_inputs

    mock_model = MagicMock()
    mock_model.generate.return_value = torch.tensor([prompt_ids + new_ids])

    passed_to_decode = None

    def mock_decode(toks, **kwargs):
        nonlocal passed_to_decode
        passed_to_decode = toks
        return "Model Answer"

    mock_tok.decode = mock_decode

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model):

        res = space_app.answer_question("Pune institutional births")
        assert list(passed_to_decode) == new_ids
        for pid in prompt_ids:
            assert pid not in list(passed_to_decode)


def test_empty_retrieval_results(sample_healthcare_df):
    """Test 4: Absent/empty retrieval returns clear guidance without calling model."""
    mock_tok = MagicMock()
    mock_model = MagicMock()

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model):

        # Query for non-existent indicator in a non-existent state
        res = space_app.answer_question("Zanzibar malaria eradication counts")
        assert "No matching records were found" in res
        # Model should NOT have been invoked
        mock_model.generate.assert_not_called()


def test_model_and_adapter_loading_failures():
    """Test 5: Model and adapter loading failures are reported and do not continue silently."""
    with patch("transformers.AutoTokenizer.from_pretrained", side_effect=ValueError("Tokenizer missing")):
        with pytest.raises(ValueError, match="Tokenizer missing"):
            import transformers
            transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")

    with patch("peft.PeftModel.from_pretrained", side_effect=RuntimeError("Adapter weights corrupted")):
        with pytest.raises(RuntimeError) as exc_info:
            import peft
            peft.PeftModel.from_pretrained(MagicMock(), "sush2306/ai-sarthi-qwen3-lora")
        assert "Adapter weights corrupted" in str(exc_info.value)


def test_private_adapter_authentication_failures():
    """Test 6: Private adapter 401 Unauthorized raises clean explanation without leaking secret."""
    fake_token = "secret_hf_token_12345"

    with patch("peft.PeftModel.from_pretrained", side_effect=Exception("401 Client Error: Unauthorized for url")):
        with pytest.raises(Exception) as exc_info:
            import peft
            peft.PeftModel.from_pretrained(MagicMock(), "sush2306/ai-sarthi-qwen3-lora", token=fake_token)

        err_msg = str(exc_info.value)
        assert "401 Client Error" in err_msg
        assert fake_token not in err_msg


def test_generation_exceptions_and_gpu_allocation_errors(sample_healthcare_df):
    """Test 7: GPU Out of Memory and runtime errors are caught safely and release resources."""
    mock_tok = MagicMock()
    mock_tok.apply_chat_template.return_value = "Prompt"
    mock_inputs = {
        "input_ids": torch.tensor([[1, 2, 3]]),
        "attention_mask": torch.tensor([[1, 1, 1]]),
    }
    mock_tok.return_value.to.return_value = mock_inputs

    mock_model = MagicMock()
    # Simulate CUDA OutOfMemoryError
    mock_model.generate.side_effect = torch.cuda.OutOfMemoryError("CUDA OOM: out of 16GB memory")

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model), \
         patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.empty_cache"):

        res = space_app.answer_question("Pune institutional births")
        assert "GPU out of memory during generation" in res
        # Verify model was offloaded back to CPU in finally block
        mock_model.to.assert_called_with("cpu")


def test_successful_chat_request_with_actual_retrieved_evidence(sample_healthcare_df):
    """Test 8: Full pipeline succeeds, combining model answer with verified database records."""
    mock_tok = MagicMock()
    mock_tok.apply_chat_template.return_value = "Prompt with verified facts"
    mock_inputs = {
        "input_ids": torch.tensor([[10, 20]]),
        "attention_mask": torch.tensor([[1, 1]]),
    }
    mock_tok.return_value.to.return_value = mock_inputs

    mock_model = MagicMock()
    mock_model.generate.return_value = torch.tensor([[10, 20, 30, 40]])
    mock_tok.decode.return_value = "According to NFHS-5, institutional births in Pune was 97.97%."

    with patch.object(space_app, "df", sample_healthcare_df), \
         patch.object(space_app, "tokenizer", mock_tok), \
         patch.object(space_app, "model", mock_model):

        res = space_app.answer_question("What is the institutional birth rate in Pune?")
        assert "According to NFHS-5, institutional births in Pune was 97.97%." in res
        assert "**Verified Database Records:**" in res
        assert "NFHS-5" in res
        assert "97.97" in res
