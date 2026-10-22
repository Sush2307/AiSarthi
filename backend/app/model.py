"""GovHealth-SLM Model Service.

Provides evidence-grounded natural language explanation with 3-tier provider architecture:
Level 1: Primary Hosted Qwen Model (Space)
Level 2: Independent Local Qwen Model (PEFT/Transformers)
Level 3: Deterministic Evidence Provider (Dataset Verified)
"""
from __future__ import annotations
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any
from . import config
from .providers import (
    OpenRouterProvider,
    HostedQwenProvider,
    LocalQwenProvider,
    DeterministicEvidenceProvider,
    SYSTEM_PROMPT,
    build_compact_evidence_context,
)

log = logging.getLogger("sarthi.model")


class ModelService:
    def __init__(self) -> None:
        self.openrouter_provider = OpenRouterProvider()
        self.hosted_provider = HostedQwenProvider()
        self.local_provider = LocalQwenProvider()
        self.deterministic_provider = DeterministicEvidenceProvider()
        self.error: str | None = None
        self.diagnostic: str | None = None
        self._lock = threading.Lock()

    @property
    def model(self) -> Any:
        return self.local_provider.model

    @model.setter
    def model(self, val: Any) -> None:
        self.local_provider.model = val

    @property
    def tokenizer(self) -> Any:
        return self.local_provider.tokenizer

    @tokenizer.setter
    def tokenizer(self, val: Any) -> None:
        self.local_provider.tokenizer = val

    @property
    def device(self) -> str:
        return self.local_provider.device

    @device.setter
    def device(self, val: str) -> None:
        self.local_provider.device = val

    @property
    def precision(self) -> str:
        return self.local_provider.precision

    @precision.setter
    def precision(self, val: str) -> None:
        self.local_provider.precision = val

    @property
    def base_model_id(self) -> str:
        return self.local_provider.base_model_id

    @base_model_id.setter
    def base_model_id(self, val: str) -> None:
        self.local_provider.base_model_id = val

    @property
    def adapter_path_str(self) -> str:
        return str(self.local_provider.adapter_path)

    @property
    def enabled(self) -> bool:
        return config.model_enabled()

    @property
    def loaded(self) -> bool:
        return self.local_provider.loaded

    @property
    def available(self) -> bool:
        return self.loaded and self.error is None

    def get_status(self) -> dict[str, Any]:
        return {
            "model_enabled": self.enabled,
            "model_loaded": self.loaded,
            "model_available": self.available,
            "device": self.device,
            "precision": self.precision,
            "base_model_id": self.base_model_id,
            "adapter_path": self.adapter_path_str,
            "model_error": self.error,
            "diagnostic": self.diagnostic,
            "max_new_tokens": config.model_max_new_tokens(),
            "temperature": config.model_temperature(),
            "primary_provider": config.primary_provider(),
            "circuit_breaker": self.hosted_provider.circuit_open or self.openrouter_provider.circuit_open,
            "providers": {
                "openrouter": self.openrouter_provider.get_status(),
                "hosted": self.hosted_provider.get_status(),
                "local": self.local_provider.get_status(),
                "deterministic": self.deterministic_provider.get_status(),
            },
        }

    def load(self) -> None:
        """Initialize the local model if configured and enabled."""
        if not self.enabled:
            self.diagnostic = "Model disabled by configuration (retrieval-only mode active)."
            log.info(self.diagnostic)
            return

        adapter_dir = config.local_model_path()
        if not adapter_dir.exists():
            msg = (
                f"Adapter directory not found at '{adapter_dir}'. "
                "System continuing in deterministic retrieval-only mode."
            )
            self.diagnostic = msg
            self.error = "Adapter directory not found"
            log.warning(msg)
            if config.strict_model_required():
                raise FileNotFoundError(msg)
            return

        cfg_path = adapter_dir / "adapter_config.json"
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
            self.local_provider.load()
            self.error = self.local_provider.error
            self.diagnostic = self.local_provider.diagnostic
        except Exception as e:
            self.error = str(e)
            self.diagnostic = f"Model initialization failed: {e}. Running in retrieval-only mode."
            if config.strict_model_required():
                raise RuntimeError(self.diagnostic) from e

    def build_evidence_context(self, records: list[dict[str, Any]], max_records: int = 8) -> str:
        return build_compact_evidence_context(records, max_records)

    def generate(self, question: str, records: list[dict[str, Any]]) -> str:
        """Direct generation method for backward compatibility."""
        primary = config.primary_provider()
        if primary == "openrouter" and self.openrouter_provider.is_available():
            return self.openrouter_provider.generate(question, records)
        elif self.available:
            return self.local_provider.generate(question, records)
        elif self.hosted_provider.is_available():
            return self.hosted_provider.generate(question, records)
        elif self.openrouter_provider.is_available():
            return self.openrouter_provider.generate(question, records)
        raise RuntimeError(f"Model is not available: {self.error or self.diagnostic}")

    def generate_routed(
        self,
        question: str,
        records: list[dict[str, Any]],
        intent: str = "exact_statistic",
        scheme_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Orchestrate multi-tier response generation with evidence grounding and circuit breakers."""
        primary = config.primary_provider()
        fallback_used = False
        fallback_reason: str | None = None

        # Level 1A: OpenRouter Provider
        if config.openrouter_enabled() or primary == "openrouter":
            if self.openrouter_provider.is_available():
                try:
                    candidate = self.openrouter_provider.generate(question, records, intent)
                    is_grounded, failure_reason = self.validate_evidence_grounding(candidate, records)
                    if is_grounded:
                        return {
                            "answer": candidate,
                            "answer_type": "ai_generated",
                            "mode": "live",
                            "inference_mode": "openrouter",
                            "fallback_used": False,
                            "fallback_reason": None,
                        }
                    else:
                        fallback_used = True
                        fallback_reason = f"OpenRouter numerical grounding check failed: {failure_reason}"
                        log.warning(fallback_reason)
                except Exception as e:
                    fallback_used = True
                    safe_e = OpenRouterProvider._redact_secrets(str(e))
                    fallback_reason = f"OpenRouter provider unavailable or failed: {safe_e}"
                    log.info(fallback_reason)
            else:
                if primary == "openrouter":
                    fallback_used = True
                    fallback_reason = "OpenRouter provider is unavailable or cooling down"

        # Level 1B: Primary Hosted Provider (Space)
        if config.hosted_model_enabled() and (primary == "hosted" or fallback_used or not self.openrouter_provider.is_available()):
            if self.hosted_provider.is_available():
                try:
                    candidate = self.hosted_provider.generate(question, records, intent)
                    is_grounded, failure_reason = self.validate_evidence_grounding(candidate, records)
                    if is_grounded:
                        return {
                            "answer": candidate,
                            "answer_type": "ai_generated",
                            "mode": "live",
                            "inference_mode": "hosted-qwen",
                            "fallback_used": fallback_used,
                            "fallback_reason": fallback_reason,
                        }
                    else:
                        fallback_used = True
                        h_msg = f"Hosted numerical grounding check failed: {failure_reason}"
                        fallback_reason = (fallback_reason + "; " + h_msg) if fallback_reason else h_msg
                        log.warning(h_msg)
                except Exception as e:
                    fallback_used = True
                    safe_h_e = OpenRouterProvider._redact_secrets(str(e))
                    h_msg = f"Hosted provider unavailable or failed: {safe_h_e}"
                    fallback_reason = (fallback_reason + "; " + h_msg) if fallback_reason else h_msg
                    log.info(h_msg)
            elif self.hosted_provider.circuit_open or primary == "hosted":
                fallback_used = True
                h_msg = "Hosted provider is unavailable or cooling down"
                fallback_reason = (fallback_reason + "; " + h_msg) if fallback_reason else h_msg

        # Level 2: Independent Local Provider
        if self.available:
            try:
                candidate = self.local_provider.generate(question, records, intent)
                is_grounded, failure_reason = self.validate_evidence_grounding(candidate, records)
                if is_grounded:
                    return {
                        "answer": candidate,
                        "answer_type": "ai_generated",
                        "mode": "live",
                        "inference_mode": "local-qwen",
                        "fallback_used": fallback_used,
                        "fallback_reason": fallback_reason,
                    }
                else:
                    fallback_used = True
                    loc_msg = f"Local numerical grounding check failed: {failure_reason}"
                    fallback_reason = (fallback_reason + "; " + loc_msg) if fallback_reason else loc_msg
                    log.warning(loc_msg)
            except Exception as e:
                fallback_used = True
                safe_loc_e = OpenRouterProvider._redact_secrets(str(e))
                loc_msg = f"Local execution failed: {safe_loc_e}"
                fallback_reason = (fallback_reason + "; " + loc_msg) if fallback_reason else loc_msg
                log.info(loc_msg)

        # Level 3: Deterministic Evidence Fallback
        deterministic_answer = self.deterministic_provider.generate(question, records, intent)
        if scheme_info:
            deterministic_answer += f"\n\n*Related Healthcare Scheme: {scheme_info.get('name')} - {scheme_info.get('summary')}*"

        inference_mode = "retrieval-only-fallback" if fallback_used else "retrieval-only"

        return {
            "answer": deterministic_answer,
            "answer_type": "dataset_only",
            "mode": "retrieval-only",
            "inference_mode": inference_mode,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
        }

    @staticmethod
    def validate_evidence_grounding(
        generated_text: str, records: list[dict[str, Any]]
    ) -> tuple[bool, str | None]:
        """Verify that any specific numerical values stated in the generated text

        appear in the retrieved records or legitimate summary aggregates.
        Prevents hallucinated numbers from reaching the user.
        """
        if not records:
            return True, None

        # Extract all verified numbers from records
        valid_numbers: set[float] = set()
        for r in records:
            val = r.get("value")
            if isinstance(val, (int, float)):
                valid_numbers.add(round(float(val), 2))
                valid_numbers.add(round(float(val), 1))
                valid_numbers.add(float(int(val)))
            # Also include numbers embedded in indicator titles, reporting periods, and metadata
            for field in ("indicator", "year", "source", "unit", "state", "district"):
                field_val = str(r.get(field) or "").replace("_", " ")
                for m in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", field_val):
                    try:
                        valid_numbers.add(float(m.replace(",", "")))
                    except ValueError:
                        pass

        # Also add summary stats (min, max, mean, count)
        record_values = [r["value"] for r in records if isinstance(r.get("value"), (int, float))]
        if record_values:
            valid_numbers.add(round(float(min(record_values)), 2))
            valid_numbers.add(round(float(max(record_values)), 2))
            mean_val = sum(record_values) / len(record_values)
            valid_numbers.add(round(float(mean_val), 2))
            valid_numbers.add(round(float(mean_val), 1))
            valid_numbers.add(float(len(records)))

        # Extract decimal numbers, comma-formatted numbers, and percentages from generated text
        # Ignore 4-digit years (e.g. 2010 to 2030) and tiny integers (1, 2, 3)
        num_patterns = re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\b\d+(?:\.\d+)?%?", generated_text)

        suspicious_numbers = []
        for pat in num_patterns:
            clean = pat.replace(",", "").rstrip("%")
            try:
                num = float(clean)
            except ValueError:
                continue

            # Skip years (e.g. 2010 to 2030)
            if 2010 <= num <= 2030 and "." not in clean:
                continue
            # Skip record counts or small integers <= 10 if whole number
            if num <= 10 and "." not in clean:
                continue

            # Check if this number matches any verified number with reasonable tolerance
            matched = any(abs(num - v) < 0.15 for v in valid_numbers)
            if not matched:
                suspicious_numbers.append(clean)

        if suspicious_numbers:
            return False, f"Generated answer contained unverified numbers: {', '.join(suspicious_numbers)}"

        return True, None
