"""AI Sarthi — GovHealth-SLM QLoRA Fine-Tuning Pipeline.

Optimized for Google Colab (Free Tier T4 GPU, 15GB VRAM) or any Linux/Windows GPU with >= 8GB VRAM.
Fine-tunes Qwen/Qwen2.5-1.5B-Instruct or Qwen/Qwen3-1.7B on AI Sarthi Public Health Dataset.

Requirements:
    pip install torch transformers peft bitsandbytes datasets trl accelerate
"""
import os
import sys
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# Configuration
MODEL_ID = os.environ.get("BASE_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
TRAIN_FILE = os.environ.get("TRAIN_FILE", "train.jsonl")
VAL_FILE = os.environ.get("VAL_FILE", "val.jsonl")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./ai_sarthi_qwen_qlora")

def format_prompts(batch):
    formatted = []
    for messages in batch["messages"]:
        # Standard chat template formatting
        text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                text += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == "user":
                text += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == "assistant":
                text += f"<|im_start|>assistant\n{content}<|im_end|>\n"
        formatted.append(text)
    return {"text": formatted}

def train():
    print(f"=== Starting AI Sarthi Training Pipeline ===")
    print(f"Base Model: {MODEL_ID}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")

    # 1. 4-bit Quantization Config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    # 2. Load Tokenizer & Model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # 3. LoRA Configuration
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. Load Dataset
    data_files = {"train": TRAIN_FILE, "validation": VAL_FILE}
    dataset = load_dataset("json", data_files=data_files)
    dataset = dataset.map(format_prompts, batched=True)

    # 5. Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        num_train_epochs=3,
        logging_steps=20,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        load_best_model_at_end=True,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        report_to="none",
    )

    # 6. SFT Trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        dataset_text_field="text",
        max_seq_length=1024,
        tokenizer=tokenizer,
        args=training_args,
    )

    print("Beginning fine-tuning...")
    trainer.train()

    print(f"Saving final LoRA adapter to {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("Training complete! Adapter ready for Hugging Face or local integration.")

if __name__ == "__main__":
    train()
