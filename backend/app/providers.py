"""Model Providers for AI Sarthi: Hosted, Local, and Deterministic Fallback.

Level 1: Primary Hosted Qwen Model (Space)
Level 2: Independent Local Qwen Model (Offline PEFT/Transformers)
Level 3: Deterministic Evidence Provider (Direct healthcare dataset synthesis)
"""
from __future__ import annotations
import json
import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import Any
import httpx

from . import config

log = logging.getLogger("sarthi.providers")

SYSTEM_PROMPT = (
    "You are GovHealth-SLM, an evidence-grounded AI assistant for Indian public healthcare statistics. "
    "Answer using ONLY the provided database evidence. Do NOT invent values, indicators, years, sources, or locations. "
    "Do NOT format data as a Markdown table with pipe (|) characters. State observations in clear, readable paragraphs and bullet points; detailed records are presented separately in the user interface. "
    "Distinguish survey percentages from administrative counts and state-level data from district-level data. "
    "Always state the official source (HMIS, NFHS-5, AHS), reporting period, and recorded unit when mentioning a number. "
    "Your response is strictly informational and not medical advice or clinical diagnosis."
)

def build_compact_evidence_context(records: list[dict[str, Any]], max_records: int = 8) -> str:
    """Create a compact, unambiguous JSON evidence slice for model context."""
    compact = []
    for r in records[:max_records]:
        geo = r.get("geographic_level")
        st = r.get("state")
        dt = r.get("district")
        loc = (st or "India") if (geo == "state" or not dt) else dt
        compact.append({
            "location": loc,
            "state": st,
            "district": dt if geo != "state" else None,
            "indicator": r.get("indicator"),
            "value": r.get("value"),
            "unit": r.get("unit") or ("%" if "percent" in str(r.get("indicator", "")).lower() else None),
            "year": r.get("year"),
            "source": r.get("source"),
            "geographic_level": r.get("geographic_level"),
        })
    return json.dumps(compact, ensure_ascii=False)


class BaseModelProvider(ABC):
    """Abstract base class for model providers."""
    provider_id: str
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is currently operational."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Returns structured diagnostic status."""
        pass

    @abstractmethod
    def generate(self, question: str, records: list[dict[str, Any]], intent: str = "exact_statistic") -> str:
        """Generate response text grounded in the provided records."""
        pass

    def close(self) -> None:
        """Resource cleanup hook."""
        pass


class OpenRouterProvider(BaseModelProvider):
    """OpenRouter inference provider for high-quality conversational reasoning.

    Uses OpenRouter chat completions API with evidence-grounding constraints,
    circuit breaker, rate limit handling, and bounded retries.
    """
    provider_id = "openrouter"
    name = "OpenRouter AI Provider"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        cooldown_seconds: float | None = None,
        max_retries: int | None = None,
        failure_threshold: int = 2,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._cooldown_seconds = cooldown_seconds
        self._max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0
        self.last_error: str | None = None
        self.total_requests = 0
        self.successful_requests = 0
        self._lock = threading.Lock()

    @property
    def api_key(self) -> str | None:
        return self._api_key or config.openrouter_api_key()

    @property
    def model_id(self) -> str:
        return self._model or config.openrouter_model()

    @property
    def base_url(self) -> str:
        return (self._base_url or config.openrouter_base_url()).rstrip("/")

    @property
    def timeout(self) -> float:
        return self._timeout if self._timeout is not None else config.openrouter_timeout()

    @property
    def cooldown_seconds(self) -> float:
        return self._cooldown_seconds if self._cooldown_seconds is not None else config.openrouter_cooldown()

    @property
    def max_retries(self) -> int:
        return self._max_retries if self._max_retries is not None else config.openrouter_max_retries()

    @property
    def enabled(self) -> bool:
        return config.openrouter_enabled() and bool(self.api_key)

    @property
    def circuit_open(self) -> bool:
        """Circuit is open (cooling down) after threshold consecutive failures."""
        if self.consecutive_failures >= self.failure_threshold:
            elapsed = time.time() - self.last_failure_time
            if elapsed < self.cooldown_seconds:
                return True
        return False

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if self.circuit_open:
            return False
        return True

    def get_status(self) -> dict[str, Any]:
        elapsed = time.time() - self.last_failure_time if self.last_failure_time > 0 else 0
        cooldown_remaining = max(0.0, self.cooldown_seconds - elapsed) if self.circuit_open else 0.0
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "enabled": self.enabled,
            "configured": bool(self.api_key),
            "available": self.is_available(),
            "circuit_open": self.circuit_open,
            "cooldown_remaining_seconds": round(cooldown_remaining, 1),
            "model": self.model_id,
            "timeout_seconds": self.timeout,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "last_error": self.last_error,
        }

    def _record_success(self) -> None:
        with self._lock:
            self.consecutive_failures = 0
            self.last_error = None
            self.successful_requests += 1

    def _record_failure(self, err: str) -> None:
        with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.time()
            self.last_error = err
            if self.consecutive_failures >= self.failure_threshold:
                log.warning(
                    "OpenRouterProvider: Circuit tripped after %d consecutive failures. Cooldown for %.1fs. Error: %s",
                    self.consecutive_failures, self.cooldown_seconds, err,
                )

    @staticmethod
    def _redact_secrets(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"sk-[a-zA-Z0-9_\-]{10,}", "[REDACTED_API_KEY]", str(text))

    def _build_payload(self, question: str, records: list[dict[str, Any]], intent: str, model_id: str | None = None) -> tuple[dict[str, str], dict[str, Any]]:
        evidence_str = build_compact_evidence_context(records)
        extra_guidance = ""
        if intent == "evidence_summary":
            extra_guidance = "\nTask: Summarize these retrieved healthcare records in simple, plain language. Clearly state the indicator, locations, observed values, and official sources."
        elif intent == "metadata_explanation":
            extra_guidance = "\nTask: Explain the official data source (HMIS, NFHS-5, AHS), survey cycle, and reporting methodology based strictly on the retrieved records."
        elif intent == "ranking":
            extra_guidance = "\nTask: Rank the retrieved locations by their recorded values, highlighting highest and lowest performance."
        elif intent == "aggregation":
            extra_guidance = "\nTask: Summarize the district statistics (mean, min, max). Clarify that the average is an unweighted mean across reporting districts."

        user_prompt = (
            f"User Question: {question}\n\n"
            f"Retrieved Healthcare Database Evidence (JSON):\n{evidence_str}\n\n"
            f"Query Intent: {intent}{extra_guidance}\n\n"
            "Instructions:\n"
            "1. Answer using ONLY facts and numbers present in the retrieved evidence.\n"
            "2. State the exact numeric value, indicator name, geography, source (e.g. HMIS, NFHS-5, AHS), and reporting period.\n"
            "3. If multiple locations or survey periods are provided, compare them accurately.\n"
            "4. Do NOT extrapolate, invent, or estimate any statistics not directly stated in the evidence.\n"
            "5. If the evidence is empty or insufficient, state clearly that no matching record was found.\n"
            "6. Do NOT format your response as a Markdown table (no '|---|' or pipe characters). Present your answer in clear, readable prose and bullet points."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": config.openrouter_site_url(),
            "X-Title": config.openrouter_app_title(),
        }

        payload = {
            "model": model_id or self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.model_temperature(),
            "max_tokens": config.openrouter_max_tokens(),
        }
        return headers, payload

    def generate(self, question: str, records: list[dict[str, Any]], intent: str = "exact_statistic") -> str:
        """Execute OpenRouter chat completions request with safe diagnostics, retries, and model fallback."""
        if not self.enabled:
            if not self.api_key:
                raise RuntimeError("OpenRouter API key is not configured.")
            raise RuntimeError("OpenRouter provider is disabled in configuration.")
        if self.circuit_open:
            elapsed = time.time() - self.last_failure_time
            remaining = round(self.cooldown_seconds - elapsed, 1)
            raise RuntimeError(f"OpenRouter circuit breaker active ({remaining}s remaining). Last error: {self.last_error}")

        self.total_requests += 1
        url = f"{self.base_url}/chat/completions"

        # Prepare candidate models (support auto-fallback between :free and base slugs)
        candidate_models = [self.model_id]
        if self.model_id.endswith(":free"):
            candidate_models.append(self.model_id[:-5])
        else:
            candidate_models.append(f"{self.model_id}:free")

        last_error_msg: str | None = None

        for model_idx, active_model in enumerate(candidate_models):
            headers, payload = self._build_payload(question, records, intent, model_id=active_model)
            max_attempts = max(1, self.max_retries + 1)

            log.info("OpenRouter: Dispatching inference to model=%s (timeout=%.1fs)", active_model, self.timeout)

            for attempt in range(max_attempts):
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.post(url, headers=headers, json=payload)

                        if resp.status_code == 200:
                            data = resp.json()
                            choices = data.get("choices")
                            if not choices or not isinstance(choices, list):
                                raise RuntimeError(f"OpenRouter returned malformed response with no choices: {str(data)[:200]}")

                            message = choices[0].get("message", {})
                            raw_content = message.get("content")
                            raw_reasoning = message.get("reasoning")
                            content = (raw_content if raw_content is not None else (raw_reasoning or "")).strip()

                            if not content:
                                raise RuntimeError("OpenRouter returned empty completion content.")

                            # Normalize unicode typography characters to standard ASCII
                            content = (
                                content
                                .replace("\u2011", "-")
                                .replace("\u2013", "-")
                                .replace("\u2014", "-")
                                .replace("\u202f", " ")
                                .replace("\u00a0", " ")
                            )

                            self._record_success()
                            log.info("OpenRouter: Generation successful using model=%s (length=%d)", active_model, len(content))
                            return content

                        # Extract error details safely without leaking secrets
                        try:
                            err_data = resp.json()
                            raw_err = err_data.get("error", {}).get("message") or resp.text[:200]
                        except Exception:
                            raw_err = resp.text[:200]
                        safe_err = self._redact_secrets(raw_err)

                        log.warning(
                            "OpenRouter HTTP %d on model=%s: %s (attempt %d/%d)",
                            resp.status_code, active_model, safe_err, attempt + 1, max_attempts,
                        )

                        if resp.status_code == 401:
                            err_msg = "OpenRouter authentication failed: Invalid or missing API key."
                            self._record_failure(err_msg)
                            raise RuntimeError(err_msg)

                        elif resp.status_code == 402:
                            m_afford = re.search(r"can only afford (\d+)", safe_err)
                            if m_afford:
                                affordable = int(m_afford.group(1))
                                if affordable >= 50 and payload.get("max_tokens", 600) > affordable:
                                    log.info("Adapting max_tokens to %d based on OpenRouter credit budget", affordable)
                                    payload["max_tokens"] = affordable
                                    continue
                            err_msg = f"OpenRouter account balance insufficient ({safe_err})."
                            last_error_msg = err_msg
                            # Try next candidate model if available
                            break

                        elif resp.status_code == 429:
                            err_msg = f"OpenRouter rate limit reached: {safe_err}"
                            last_error_msg = err_msg
                            # If this was free tier exhaustion and we have another candidate model, try next candidate
                            if "free-models-per-day" in safe_err.lower() and model_idx < len(candidate_models) - 1:
                                log.info("OpenRouter free tier limit hit. Trying candidate model: %s", candidate_models[model_idx + 1])
                                break
                            if attempt < max_attempts - 1:
                                time.sleep(1.0 * (2 ** attempt))
                                continue
                            self._record_failure(err_msg)
                            raise RuntimeError(err_msg)

                        elif resp.status_code == 404:
                            err_msg = f"OpenRouter model not found: {active_model} ({safe_err})"
                            last_error_msg = err_msg
                            break

                        else:
                            err_msg = f"OpenRouter HTTP error {resp.status_code}: {safe_err}"
                            last_error_msg = err_msg
                            if attempt < max_attempts - 1:
                                time.sleep(0.5 * (2 ** attempt))
                                continue
                            self._record_failure(err_msg)
                            raise RuntimeError(err_msg)

                except httpx.TimeoutException as e:
                    err_msg = f"OpenRouter request timed out after {self.timeout}s on model {active_model}."
                    last_error_msg = err_msg
                    log.warning(err_msg)
                    if attempt < max_attempts - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    self._record_failure(err_msg)
                    raise RuntimeError(err_msg) from e

                except httpx.RequestError as e:
                    err_msg = f"OpenRouter network error on model {active_model}: {type(e).__name__}"
                    last_error_msg = err_msg
                    log.warning(err_msg)
                    if attempt < max_attempts - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    self._record_failure(err_msg)
                    raise RuntimeError(err_msg) from e

        final_err = last_error_msg or "OpenRouter request failed across all candidate models."
        self._record_failure(final_err)
        raise RuntimeError(final_err)


class HostedQwenProvider(BaseModelProvider):
    """Level 1: Primary Hosted Qwen Model running on Hugging Face Space.

    Includes circuit breaker and configurable timeout to prevent remote failures from blocking requests.
    """
    provider_id = "hosted_qwen"
    name = "Primary Hosted Qwen Model (Space)"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        cooldown_seconds: float | None = None,
        failure_threshold: int = 2,
    ) -> None:
        self.base_url = (base_url or config.hosted_model_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else config.hosted_model_timeout()
        self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else config.hosted_model_cooldown()
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0
        self.last_error: str | None = None
        self.total_requests = 0
        self.successful_requests = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return config.hosted_model_enabled() and bool(self.base_url)

    @property
    def circuit_open(self) -> bool:
        """Circuit is open (cooling down) after threshold consecutive failures."""
        if self.consecutive_failures >= self.failure_threshold:
            elapsed = time.time() - self.last_failure_time
            if elapsed < self.cooldown_seconds:
                return True
        return False

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if self.circuit_open:
            return False
        return True

    def get_status(self) -> dict[str, Any]:
        elapsed = time.time() - self.last_failure_time if self.last_failure_time > 0 else 0
        cooldown_remaining = max(0.0, self.cooldown_seconds - elapsed) if self.circuit_open else 0.0
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "enabled": self.enabled,
            "available": self.is_available(),
            "circuit_open": self.circuit_open,
            "cooldown_remaining_seconds": round(cooldown_remaining, 1),
            "base_url": self.base_url,
            "timeout_seconds": self.timeout,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "last_error": self.last_error,
        }

    def _record_success(self) -> None:
        with self._lock:
            self.consecutive_failures = 0
            self.last_error = None
            self.successful_requests += 1

    def _record_failure(self, err: str) -> None:
        with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.time()
            self.last_error = err
            if self.consecutive_failures >= self.failure_threshold:
                log.warning(
                    "HostedQwenProvider: Circuit tripped after %d consecutive failures. Cooldown for %.1fs. Error: %s",
                    self.consecutive_failures, self.cooldown_seconds, err,
                )

    def generate(self, question: str, records: list[dict[str, Any]], intent: str = "exact_statistic") -> str:
        """Call hosted Gradio Space /gradio_api/call/chat endpoint with evidence."""
        if not self.enabled:
            raise RuntimeError("HostedQwenProvider is disabled in configuration.")
        if self.circuit_open:
            elapsed = time.time() - self.last_failure_time
            remaining = round(self.cooldown_seconds - elapsed, 1)
            raise RuntimeError(f"HostedQwenProvider circuit is cooling down ({remaining}s remaining). Last error: {self.last_error}")

        self.total_requests += 1
        evidence_str = build_compact_evidence_context(records)
        formatted_message = f"Question: {question}\n\nEvidence:\n{evidence_str}"

        call_url = f"{self.base_url}/gradio_api/call/chat"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                post_resp = client.post(call_url, json={"data": [formatted_message]})
                if post_resp.status_code != 200:
                    raise RuntimeError(f"Hosted Space call returned HTTP {post_resp.status_code}: {post_resp.text[:200]}")

                event_data = post_resp.json()
                event_id = event_data.get("event_id")
                if not event_id:
                    raise RuntimeError(f"No event_id returned by hosted endpoint: {event_data}")

                stream_url = f"{self.base_url}/gradio_api/call/chat/{event_id}"
                answer_text = None
                with client.stream("GET", stream_url, timeout=self.timeout) as stream:
                    for line in stream.iter_lines():
                        if not line:
                            continue
                        if line.startswith("event: error"):
                            raise RuntimeError(f"Hosted Space reported execution error for event {event_id}")
                        if line.startswith("data:"):
                            payload_str = line[len("data:"):].strip()
                            if payload_str and payload_str != "null":
                                try:
                                    payload = json.loads(payload_str)
                                    if isinstance(payload, list) and len(payload) > 0:
                                        answer_text = str(payload[0])
                                    elif isinstance(payload, str):
                                        answer_text = payload
                                    elif isinstance(payload, dict) and "value" in payload:
                                        answer_text = str(payload["value"])
                                except json.JSONDecodeError:
                                    answer_text = payload_str

                if not answer_text or not answer_text.strip():
                    raise RuntimeError("Hosted Space returned an empty answer.")

                # Success
                self._record_success()
                return answer_text.strip()

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            self._record_failure(err_msg)
            raise RuntimeError(f"Hosted generation failed: {err_msg}") from e


class LocalQwenProvider(BaseModelProvider):
    """Level 2: Independent Local Model (Offline PEFT/Transformers).

    Safely executes without remote network access using local artifacts.
    """
    provider_id = "local_qwen"
    name = "Independent Local Qwen Model (Offline)"

    def __init__(self) -> None:
        self.model: Any = None
        self.tokenizer: Any = None
        self.device: str = "not loaded"
        self.precision: str = "none"
        self.error: str | None = None
        self.diagnostic: str | None = None
        self.base_model_id: str = config.base_model_id()
        self.adapter_path = config.local_model_path()
        self._lock = threading.Lock()
        self.total_requests = 0
        self.successful_requests = 0

    @property
    def enabled(self) -> bool:
        return config.local_model_enabled()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def is_available(self) -> bool:
        return self.loaded and self.error is None

    def get_status(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "enabled": self.enabled,
            "available": self.is_available(),
            "loaded": self.loaded,
            "device": self.device,
            "precision": self.precision,
            "base_model_id": self.base_model_id,
            "adapter_path": str(self.adapter_path),
            "adapter_exists": self.adapter_path.exists(),
            "error": self.error,
            "diagnostic": self.diagnostic,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
        }

    def load(self) -> None:
        """Safely initialize local tokenizer, model, and adapter."""
        if not self.enabled:
            self.diagnostic = "Local model disabled by configuration."
            log.info(self.diagnostic)
            return

        if not self.adapter_path.exists():
            msg = f"Local adapter directory not found at '{self.adapter_path}'. Offline model inference unavailable."
            self.diagnostic = msg
            self.error = "Adapter directory not found"
            log.warning(msg)
            if config.strict_model_required():
                raise FileNotFoundError(msg)
            return

        cfg_path = self.adapter_path / "adapter_config.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    base_in_cfg = cfg_data.get("base_model_name_or_path")
                    if base_in_cfg:
                        self.base_model_id = base_in_cfg
            except Exception as e:
                log.warning("Could not read adapter_config.json: %s", e)

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
            from peft import PeftModel

            log.info("Loading local tokenizer from %s / %s", self.adapter_path, self.base_model_id)
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(str(self.adapter_path), trust_remote_code=True)
            except Exception:
                self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_id, trust_remote_code=True)

            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

            target_device = config.model_device()
            use_cuda = (target_device == "cuda") or (target_device == "auto" and torch.cuda.is_available())

            if use_cuda and torch.cuda.is_available():
                log.info("Loading Qwen base model on CUDA with 4-bit NF4 quantization...")
                try:
                    q = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                    )
                    base = AutoModelForCausalLM.from_pretrained(
                        self.base_model_id,
                        quantization_config=q,
                        device_map="auto",
                        torch_dtype=torch.float16,
                        trust_remote_code=True,
                    )
                    gpu_name = torch.cuda.get_device_name(0)
                    self.device = f"cuda ({gpu_name})"
                    self.precision = "4-bit NF4"
                except Exception as bnb_err:
                    log.warning("4-bit quantization failed (%s), falling back to float16 on CUDA", bnb_err)
                    base = AutoModelForCausalLM.from_pretrained(
                        self.base_model_id,
                        device_map="auto",
                        torch_dtype=torch.float16,
                        trust_remote_code=True,
                    )
                    self.device = "cuda (float16)"
                    self.precision = "float16"
            else:
                log.info("Loading Qwen base model on CPU (float32)...")
                base = AutoModelForCausalLM.from_pretrained(
                    self.base_model_id,
                    torch_dtype=torch.float32,
                    trust_remote_code=True,
                )
                self.device = "cpu"
                self.precision = "float32"

            log.info("Attaching PEFT adapter from %s...", self.adapter_path)
            self.model = PeftModel.from_pretrained(base, str(self.adapter_path)).eval()
            self.error = None
            self.diagnostic = f"Local model ready on {self.device} ({self.precision})."
            log.info("LocalQwenProvider initialized: %s", self.diagnostic)

        except Exception as e:
            self.model = None
            self.tokenizer = None
            self.error = str(e)
            self.diagnostic = f"Local model initialization failed: {e}"
            log.error(self.diagnostic)
            if config.strict_model_required():
                raise RuntimeError(self.diagnostic) from e

    def generate(self, question: str, records: list[dict[str, Any]], intent: str = "exact_statistic") -> str:
        """Run offline thread-safe local generation."""
        if not self.is_available():
            raise RuntimeError(f"LocalQwenProvider is not available: {self.error or self.diagnostic}")

        import torch
        self.total_requests += 1

        evidence = build_compact_evidence_context(records)
        user_prompt = (
            f"Question: {question}\n\n"
            f"Verified Database Evidence:\n{evidence}\n\n"
            "Provide a concise, direct, evidence-grounded explanation. "
            "Cite the exact numeric values, the locations, the source, and the reporting period from the evidence. "
            "Do NOT invent numbers or extrapolate unrecorded trends."
        )

        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        else:
            prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"

        inputs = self.tokenizer(prompt, return_tensors="pt")
        target_dev = getattr(self.model, "device", "cpu")
        inputs = {k: v.to(target_dev) for k, v in inputs.items()}

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": config.model_max_new_tokens(),
            "pad_token_id": self.tokenizer.pad_token_id,
            "repetition_penalty": 1.15,
        }
        temp = config.model_temperature()
        if temp > 0.0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temp
            gen_kwargs["top_p"] = 0.9
        else:
            gen_kwargs["do_sample"] = False

        with self._lock, torch.inference_mode():
            outputs = self.model.generate(**inputs, **gen_kwargs)

        input_len = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_len:]
        text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        text = re.sub(r"<\|im_end\|>.*$", "", text, flags=re.DOTALL).strip()

        self.successful_requests += 1
        return text


class DeterministicEvidenceProvider(BaseModelProvider):
    """Level 3: Deterministic Evidence Provider.

    Generates verified, statistically sound natural-language responses directly
    from indexed database records without language model hallucinations.
    """
    provider_id = "deterministic"
    name = "Deterministic Evidence Provider (Dataset Verified)"

    def is_available(self) -> bool:
        return True

    def get_status(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "available": True,
            "deterministic": True,
        }

    def generate(self, question: str, records: list[dict[str, Any]], intent: str = "exact_statistic") -> str:
        """Synthesize verified explanation deterministically based on query intent and records."""
        if not records:
            return (
                "I could not find matching records in the current healthcare database. "
                "Try a more specific indicator (e.g. 'institutional births', 'immunization', 'anaemia'), "
                "state, district, source, or year."
            )

        if intent == "available_sources":
            return self._format_available_sources(records, question)
        elif intent == "available_years":
            return self._format_available_years(records, question)
        elif intent == "available_districts":
            return self._format_available_districts(records, question)
        elif intent == "available_indicators":
            return self._format_available_indicators(records, question)
        elif intent == "comparison":
            return self._format_comparison(records)
        elif intent == "trend":
            return self._format_trend(records, question)
        elif intent == "evidence_summary":
            return self._format_evidence_summary(records, question)
        elif intent == "metadata_explanation":
            return self._format_metadata_explanation(records, question)
        elif intent == "ranking":
            return self._format_ranking(records, question)
        elif intent == "aggregation":
            return self._format_aggregation(records, question)
        elif len(records) == 1:
            return self._format_single_record(records[0])
        else:
            return self._format_multiple_records(records)

    def _format_evidence_summary(self, records: list[dict[str, Any]], question: str = "") -> str:
        loc = self._get_loc_label(records, question)
        distinct_inds = sorted(list({str(r.get("indicator", "")) for r in records if r.get("indicator")}))
        sources = sorted(list({str(r.get("source", "")) for r in records if r.get("source")}))
        years = sorted(list({str(r.get("year", "")) for r in records if r.get("year")}))

        lines = [
            f"### Healthcare Evidence Summary for **{loc}** (Simple Terms)\n",
            f"Here is a plain-language summary of the **{len(records)} verified healthcare record(s)** retrieved from official government health reporting systems:\n",
        ]

        if len(distinct_inds) == 1:
            ind_clean = distinct_inds[0].replace("_", " ").title()
            first_r = records[0]
            raw_u = first_r.get("unit") or ("%" if "percent" in str(first_r.get("indicator", "")).lower() else "")
            unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")
            numeric_vals = [r["value"] for r in records if isinstance(r.get("value"), (int, float))]

            lines.append(f"- **Health Metric**: **{ind_clean}**")
            lines.append(f"- **Reporting Source**: {', '.join(sources)} ({', '.join(years)})")

            if len(records) == 1:
                val = records[0].get("value")
                val_str = f"{val:,}" if isinstance(val, (int, float)) else str(val or "N/A")
                lines.append(f"- **Recorded Value**: **{val_str}{unit}**")
            elif numeric_vals:
                min_v = min(numeric_vals)
                max_v = max(numeric_vals)
                avg_v = round(sum(numeric_vals) / len(numeric_vals), 2)
                lines.append(f"- **Observed Spread**: Values range from **{min_v:,}{unit}** to **{max_v:,}{unit}**, with an average of **{avg_v:,}{unit}** across reporting areas.")

            lower_ind = distinct_inds[0].lower()
            if "institutional_births" in lower_ind:
                lines.append("\n**What this means**: This measures the percentage of childbirths delivered in medical facilities (public hospitals or private clinics) under the care of skilled health personnel, which reduces maternal and neonatal health risks.")
            elif "anaemic" in lower_ind:
                lines.append("\n**What this means**: This measures the percentage of individuals with low haemoglobin levels in the blood, indicating iron deficiency and nutritional vulnerability.")
            elif "stunted" in lower_ind:
                lines.append("\n**What this means**: This measures the percentage of young children whose height is significantly low for their age, reflecting chronic undernutrition.")
            elif "wasted" in lower_ind:
                lines.append("\n**What this means**: This measures acute undernutrition, where a child's weight is significantly below normal for their height.")
            elif "fully_vaccinated" in lower_ind:
                lines.append("\n**What this means**: This measures the percentage of young children who have received all essential early childhood immunizations (BCG, Polio, DPT/Pentavalent, Measles).")
            elif "caesarean" in lower_ind:
                lines.append("\n**What this means**: This measures deliveries performed via surgical C-section in medical facilities.")
        else:
            lines.append(f"- **Coverage**: The records cover **{len(distinct_inds)} distinct health indicators** across **{', '.join(sources)}** ({', '.join(years)}).")
            lines.append("- **Key Indicators Indexed**:")
            for i, ind in enumerate(distinct_inds[:8], 1):
                lines.append(f"  {i}. {ind.replace('_', ' ').title()}")
            lines.append("\nEach of these metrics is strictly recorded from verified public health datasets.")

        return "\n".join(lines)

    def _format_metadata_explanation(self, records: list[dict[str, Any]], question: str = "") -> str:
        loc = self._get_loc_label(records, question)
        sources = sorted(list({str(r.get("source", "")) for r in records if r.get("source")}))
        years = sorted(list({str(r.get("year", "")) for r in records if r.get("year")}))
        geo_levels = sorted(list({str(r.get("geographic_level", "")) for r in records if r.get("geographic_level")}))

        lines = [
            f"### Official Source & Reporting Metadata for **{loc}**\n",
            f"- **Official Data Source(s)**: **{', '.join(sources)}**",
            f"- **Reporting Cycle / Survey Period**: **{', '.join(years)}**",
            f"- **Geographic Resolution**: {', '.join(geo_levels).title()} level",
            "\n**Source Descriptions & Methodology**:",
        ]

        if any("HMIS" in s for s in sources):
            lines.append(
                "- **HMIS (Health Management Information System)**: Operated by the Ministry of Health and Family Welfare (MoHFW), "
                "HMIS captures monthly administrative service-delivery records uploaded directly by public and accredited health facilities across India."
            )
        if any("NFHS" in s for s in sources):
            lines.append(
                "- **NFHS-5 (National Family Health Survey, 2019-2021)**: Conducted under the stewardship of MoHFW with the International Institute "
                "for Population Sciences (IIPS) as the nodal agency. It provides representative sample survey estimates at district and state levels."
            )
        if any("AHS" in s for s in sources):
            lines.append(
                "- **AHS (Annual Health Survey)**: Conducted across high-priority focus states to track core demographic and maternal-child health parameters."
            )

        lines.append(
            "\nAll observations in AI Sarthi are deterministically extracted from these official government partitions without generative extrapolation."
        )
        return "\n".join(lines)

    def _format_ranking(self, records: list[dict[str, Any]], question: str = "") -> str:
        if not records:
            return "No valid observations available for ranking."

        q_lower = question.lower()
        is_ascending = any(k in q_lower for k in ["lowest", "bottom", "least", "worst", "smallest"])

        distinct_inds = sorted(list({str(r.get("indicator", "")) for r in records if r.get("indicator")}))
        if len(distinct_inds) > 1:
            return "Cannot perform ranking across multiple different healthcare indicators. Please request a ranking for a single specific indicator."

        ind_clean = distinct_inds[0].replace("_", " ").title()
        raw_u = records[0].get("unit") or ("%" if "percent" in str(records[0].get("indicator", "")).lower() else "")
        unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")
        src = str(records[0].get("source", "Official"))
        yr = str(records[0].get("year", ""))

        numeric_entries = []
        for r in records:
            loc = r.get("district_clean") or r.get("district") or r.get("state_standard") or r.get("state")
            val = r.get("value")
            if loc and isinstance(val, (int, float)):
                numeric_entries.append((loc, float(val)))

        seen = set()
        deduped = []
        for loc, val in numeric_entries:
            if loc not in seen:
                seen.add(loc)
                deduped.append((loc, val))

        deduped.sort(key=lambda x: x[1], reverse=not is_ascending)

        direction_label = "Lowest" if is_ascending else "Top"
        lines = [
            f"### **{direction_label} District Ranking for '{ind_clean}'** ({src}, {yr})\n",
        ]
        for rank, (loc, val) in enumerate(deduped[:10], 1):
            lines.append(f"{rank}. **{loc}**: {val:,}{unit}")

        if len(deduped) >= 2:
            top_loc, top_v = deduped[0]
            last_loc, last_v = deduped[-1]
            diff = round(abs(top_v - last_v), 2)
            lines.append(f"\n**Analysis**: {top_loc} records {top_v:,}{unit} compared to {last_loc} with {last_v:,}{unit} (spread of {diff:,}{unit}).")

        return "\n".join(lines)

    def _format_aggregation(self, records: list[dict[str, Any]], question: str = "") -> str:
        if not records:
            return "No valid records available for statistical calculation."

        distinct_inds = sorted(list({str(r.get("indicator", "")) for r in records if r.get("indicator")}))
        if len(distinct_inds) > 1:
            return "Cannot calculate statistical aggregates across multiple different indicators or incompatible units."

        ind_clean = distinct_inds[0].replace("_", " ").title()
        raw_u = records[0].get("unit") or ("%" if "percent" in str(records[0].get("indicator", "")).lower() else "")
        unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")
        src = str(records[0].get("source", "Official"))
        yr = str(records[0].get("year", ""))
        state_name = records[0].get("state_standard") or records[0].get("state") or "the state"

        vals = [float(r["value"]) for r in records if isinstance(r.get("value"), (int, float))]
        if not vals:
            return f"No numeric observations available to compute averages for '{ind_clean}'."

        min_v = round(min(vals), 2)
        max_v = round(max(vals), 2)
        mean_v = round(sum(vals) / len(vals), 2)

        return (
            f"### **Deterministic Summary for '{ind_clean}' in {state_name}** ({src}, {yr})\n\n"
            f"- **Reporting Districts Evaluated**: **{len(vals)}**\n"
            f"- **District Average (Mean)**: **{mean_v:,}{unit}**\n"
            f"- **Minimum Value**: **{min_v:,}{unit}**\n"
            f"- **Maximum Value**: **{max_v:,}{unit}**\n"
            f"- **Range Spread**: **{round(max_v - min_v, 2):,}{unit}**\n\n"
            f"*Statistical Note: The district average of {mean_v:,}{unit} is an unweighted arithmetic mean across the {len(vals)} "
            f"reporting districts in this dataset partition. It is not an official census-weighted statewide rate.*"
        )

    @staticmethod
    def _get_loc_label(records: list[dict[str, Any]], question: str = "") -> str:
        if not records:
            return "the selected geography"
        q_lower = question.lower()
        dists = {str(r.get("district_clean") or r.get("district") or "") for r in records if r.get("district_clean") or r.get("district")}
        states = {str(r.get("state_standard") or r.get("state") or "") for r in records if r.get("state_standard") or r.get("state")}

        # 1. Check if user explicitly asked for a specific district
        for d in sorted(dists, key=len, reverse=True):
            if d and d.lower() in q_lower:
                return d

        # 2. Check if user explicitly asked for a state
        for s in sorted(states, key=len, reverse=True):
            if s and (s.lower() in q_lower or (s.lower() == "maharastra" and "maharashtra" in q_lower)):
                return "Maharashtra" if s.lower() == "maharastra" else s

        # 3. If no district was in the query, but records belong to a single state, prefer state
        if len(states) == 1:
            st = next(iter(states))
            return "Maharashtra" if st.lower() == "maharastra" else st

        # 4. Fallback to single district or first available
        if len(dists) == 1:
            return next(iter(dists))
        return records[0].get("district") or records[0].get("state") or "the selected geography"

    def _format_available_sources(self, records: list[dict[str, Any]], question: str = "") -> str:
        loc = self._get_loc_label(records, question)
        sources = sorted(list({str(r.get("source", "")) for r in records if r.get("source")}))
        lines = [
            f"Verified healthcare records for **{loc}** are available from {len(sources)} official source(s):",
        ]
        for s in sources:
            s_recs = [r for r in records if r.get("source") == s]
            years = sorted(list({str(r.get("year", "")) for r in s_recs if r.get("year")}))
            y_str = f" (reporting period: {', '.join(years)})" if years else ""
            lines.append(f"- **{s}**: {len(s_recs)} observation(s) indexed{y_str}")
        return "\n".join(lines)

    def _format_available_years(self, records: list[dict[str, Any]], question: str = "") -> str:
        ind = str(records[0].get("indicator", "")).replace("_", " ")
        loc = self._get_loc_label(records, question)
        years_by_source: dict[str, list[str]] = {}
        for r in records:
            src = str(r.get("source", "Official"))
            yr = str(r.get("year", ""))
            if yr:
                years_by_source.setdefault(src, []).append(yr)
        lines = [
            f"Reporting period(s) indexed for '**{ind}**' in **{loc}**:",
        ]
        for src, yrs in sorted(years_by_source.items()):
            distinct_yrs = sorted(list(set(yrs)))
            lines.append(f"- **{src}**: {', '.join(distinct_yrs)}")
        return "\n".join(lines)

    def _format_available_districts(self, records: list[dict[str, Any]]) -> str:
        ind = str(records[0].get("indicator", "")).replace("_", " ")
        districts = sorted(list({str(r.get("district_clean") or r.get("district", "")) for r in records if r.get("district_clean") or r.get("district")}))
        src = str(records[0].get("source", "official reporting systems"))
        yr = str(records[0].get("year", ""))
        y_str = f" ({yr})" if yr else ""
        lines = [
            f"Verified observations for '**{ind}**' from {src}{y_str} are recorded across **{len(districts)} district(s)**:",
        ]
        for d in districts[:10]:
            lines.append(f"- **{d}**")
        if len(districts) > 10:
            lines.append(f"\n*(and {len(districts) - 10} additional indexed districts across India)*")
        return "\n".join(lines)

    def _format_single_record(self, r: dict[str, Any]) -> str:
        val = r.get("value")
        val_str = f"{val:,}" if isinstance(val, (int, float)) else str(val or "N/A")
        raw_u = r.get("unit") or ("%" if "percent" in str(r.get("indicator", "")).lower() else "")
        unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")
        loc = r.get("district") or r.get("state") or "India"
        ind = str(r.get("indicator", "")).replace("_", " ")
        yr = str(r.get("year", ""))
        src = str(r.get("source", ""))
        geo = str(r.get("geographic_level", ""))

        level_note = f" ({geo} level)" if geo else ""
        return (
            f"Based on verified records from {src} ({yr}), the indicator '{ind}' "
            f"in {loc}{level_note} is recorded as {val_str}{unit}. "
            f"This observation is strictly grounded in official public health reporting data."
        )

    def _format_comparison(self, records: list[dict[str, Any]]) -> str:
        # Group by location
        loc_map: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            loc = r.get("district") or r.get("state") or "Unknown"
            loc_map.setdefault(loc, []).append(r)

        loc_keys = list(loc_map.keys())
        first_r = records[0]
        ind_clean = str(first_r.get("indicator", "")).replace("_", " ")
        raw_u = first_r.get("unit") or ("%" if "percent" in str(first_r.get("indicator", "")).lower() else "")
        unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")
        src = str(first_r.get("source", "official reporting systems"))
        yr = str(first_r.get("year", ""))

        lines = [
            f"**Comparative Analysis for '{ind_clean}'** ({src}, {yr}):",
        ]

        numeric_locs = []
        for loc in loc_keys[:6]:
            rec = loc_map[loc][0]
            val = rec.get("value")
            if isinstance(val, (int, float)):
                numeric_locs.append((loc, float(val)))
                lines.append(f"- **{loc}**: {val:,}{unit}")
            else:
                lines.append(f"- **{loc}**: N/A{unit}")

        if len(numeric_locs) >= 2:
            # Sort descending
            numeric_locs.sort(key=lambda x: x[1], reverse=True)
            top_loc, top_val = numeric_locs[0]
            bottom_loc, bottom_val = numeric_locs[-1]
            diff = round(top_val - bottom_val, 2)
            lines.append(
                f"\n**Summary**: {top_loc} recorded the highest observation ({top_val:,}{unit}), "
                f"which is {diff:,}{unit} higher than {bottom_loc} ({bottom_val:,}{unit})."
            )

        return "\n".join(lines)

    def _format_trend(self, records: list[dict[str, Any]], question: str = "") -> str:
        # Sort chronologically by year
        sorted_recs = sorted(records, key=lambda r: str(r.get("year", "")))
        first_r = sorted_recs[0]
        loc = self._get_loc_label(records, question) if question else (first_r.get("district") or first_r.get("state") or "India")
        ind = str(first_r.get("indicator", "")).replace("_", " ")
        src = str(first_r.get("source", ""))
        raw_u = first_r.get("unit") or ("%" if "percent" in str(first_r.get("indicator", "")).lower() else "")
        unit = f"{raw_u}" if raw_u.startswith("%") else (f" {raw_u}" if raw_u else "")

        lines = [
            f"**Multi-Period Trend for '{ind}' in {loc}** ({src}):",
        ]
        numeric_series = []
        for r in sorted_recs:
            yr = r.get("year", "")
            val = r.get("value")
            if isinstance(val, (int, float)):
                numeric_series.append((yr, float(val)))
                lines.append(f"- **{yr}**: {val:,}{unit}")
            else:
                lines.append(f"- **{yr}**: N/A")

        if len(numeric_series) >= 2:
            start_yr, start_val = numeric_series[0]
            end_yr, end_val = numeric_series[-1]
            change = round(end_val - start_val, 2)
            direction = "an increase" if change > 0 else ("a decrease" if change < 0 else "no change")
            lines.append(
                f"\n**Trend Summary**: From {start_yr} ({start_val:,}{unit}) to {end_yr} ({end_val:,}{unit}), "
                f"there is {direction} of {abs(change):,}{unit}."
            )

        return "\n".join(lines)

    def _format_available_indicators(self, records: list[dict[str, Any]], question: str = "") -> str:
        loc = self._get_loc_label(records, question)
        distinct_inds = sorted(list({str(r.get("indicator", "")) for r in records if r.get("indicator")}))
        sources = sorted(list({str(r.get("source", "")) for r in records if r.get("source")}))
        years = sorted(list({str(r.get("year", "")) for r in records if r.get("year")}))

        lines = [
            f"Verified healthcare dataset indexes {len(distinct_inds)} key indicators for **{loc}** "
            f"across {', '.join(sources)} ({', '.join(years)}):\n",
        ]

        # Group representative indicators
        for i, ind in enumerate(distinct_inds[:10], 1):
            clean_name = ind.replace("_", " ").title()
            lines.append(f"{i}. **{clean_name}**")

        if len(distinct_inds) > 10:
            lines.append(f"\n*(and {len(distinct_inds) - 10} additional indexed indicators in this dataset)*")

        lines.append(
            "\nYou can ask specific questions about any of these indicators, "
            "e.g. 'Show institutional births in Maharashtra' or 'Compare child immunization across districts'."
        )
        return "\n".join(lines)

    def _format_multiple_records(self, records: list[dict[str, Any]]) -> str:
        first_r = records[0]
        ind = str(first_r.get("indicator", "")).replace("_", " ")
        src = str(first_r.get("source", ""))
        yr = str(first_r.get("year", ""))
        raw_u = first_r.get("unit") or ("%" if "percent" in str(first_r.get("indicator", "")).lower() else "")
        unit = f" {raw_u}" if raw_u and not raw_u.startswith("%") else raw_u

        distinct_inds = sorted(list({str(r.get("indicator", "")) for r in records if r.get("indicator")}))
        distinct_units = sorted(list({str(r.get("unit") or ("%" if "percent" in str(r.get("indicator", "")).lower() else "")) for r in records}))
        same_indicator_and_unit = (len(distinct_inds) <= 1) and (len(distinct_units) <= 1)

        vals = [r["value"] for r in records if isinstance(r.get("value"), (int, float))]
        locations = sorted(list({r.get("district") or r.get("state") for r in records if r.get("district") or r.get("state")}))

        loc_str = f" for {', '.join(locations[:3])}" if locations else ""
        if vals and same_indicator_and_unit:
            min_val = min(vals)
            max_val = max(vals)
            mean_val = round(sum(vals) / len(vals), 2)
            return (
                f"Based on verified records from {src} ({yr}){loc_str}, retrieved {len(records)} observations for '{ind}'. "
                f"Values range from {min_val:,}{unit} to {max_val:,}{unit}, "
                f"with an average of {mean_val:,}{unit}. "
                f"Refer to the table below for observation breakdown."
            )

        return (
            f"Based on verified records{loc_str}, retrieved {len(records)} observations across {len(locations)} location(s) and "
            f"{len(distinct_inds)} indicator(s). "
            f"Refer to the table below for detailed observations with their respective units."
        )
