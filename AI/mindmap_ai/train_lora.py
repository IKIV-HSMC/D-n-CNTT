"""
train_lora.py - Fine-tune Qwen2.5-3B-Instruct bằng QLoRA (Unsloth). CHẠY TRÊN GPU (Colab T4 / Kaggle).

Cài (Colab):   pip install unsloth trl datasets
Chạy:          python train_lora.py --train train.jsonl --val train.val.jsonl
Kết quả:       thư mục mindmap-model/ (model đã gộp LoRA), dùng được với vLLM / Ollama / Transformers.
"""
import argparse
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

ap = argparse.ArgumentParser()
ap.add_argument("--train", default="train.jsonl")
ap.add_argument("--val", default="train.val.jsonl")
ap.add_argument("--base", default="unsloth/Qwen2.5-3B-Instruct")
ap.add_argument("--epochs", type=int, default=2)
a = ap.parse_args()

model, tok = FastLanguageModel.from_pretrained(a.base, max_seq_length=4096, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

ds = load_dataset("json", data_files={"train": a.train, "validation": a.val})
fmt = lambda ex: {"text": tok.apply_chat_template(ex["messages"], tokenize=False)}
ds = ds.map(fmt)

import inspect
params = inspect.signature(SFTConfig).parameters     # tương thích nhiều phiên bản TRL
cfg = dict(output_dir="out", dataset_text_field="text",
           per_device_train_batch_size=2, gradient_accumulation_steps=8,
           num_train_epochs=a.epochs, learning_rate=2e-4, warmup_ratio=0.05,
           logging_steps=10, save_strategy="epoch", bf16=False, fp16=True)
cfg["max_length" if "max_seq_length" not in params and "max_length" in params else "max_seq_length"] = 4096
cfg["eval_strategy" if "eval_strategy" in params else "evaluation_strategy"] = "epoch"

SFTTrainer(
    model=model, tokenizer=tok,
    train_dataset=ds["train"], eval_dataset=ds["validation"],
    args=SFTConfig(**cfg),
).train()

model.save_pretrained_merged("mindmap-model", tok, save_method="merged_16bit")
print("Đã lưu model vào ./mindmap-model")
