"""
train_lora.py - Fine-tune Qwen2.5-3B-Instruct bằng QLoRA (Unsloth) tối ưu dung lượng cho Kaggle GPU T4.
Xuất file GGUF (q4_k_m ~1.9GB) nạp thẳng vào Ollama, chống tràn ổ đĩa 19.5GB.
"""
import argparse
import os
import shutil
import inspect
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="train.jsonl")
    ap.add_argument("--val", default="train.val.jsonl")
    ap.add_argument("--base", default="unsloth/Qwen2.5-3B-Instruct")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-seq-len", type=int, default=2048)
    a = ap.parse_args()

    print(f"=== Bắt đầu tải Base Model: {a.base} (4-bit QLoRA) ===")
    model, tok = FastLanguageModel.from_pretrained(
        a.base,
        max_seq_length=a.max_seq_len,
        load_in_4bit=True
    )

    print("=== Thiết lập LoRA Adapters ===")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )

    print(f"=== Tải dữ liệu: {a.train} và {a.val} ===")
    ds = load_dataset("json", data_files={"train": a.train, "validation": a.val})
    fmt = lambda ex: {"text": tok.apply_chat_template(ex["messages"], tokenize=False)}
    ds = ds.map(fmt)

    params = inspect.signature(SFTConfig).parameters
    cfg = dict(
        output_dir="/tmp/checkpoints",
        dataset_text_field="text",
        per_device_train_batch_size=a.batch_size,
        gradient_accumulation_steps=a.grad_accum,
        num_train_epochs=a.epochs,
        learning_rate=a.lr,
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="no",
        bf16=False,
        fp16=True
    )
    if "max_seq_length" in params:
        cfg["max_seq_length"] = a.max_seq_len
    elif "max_length" in params:
        cfg["max_length"] = a.max_seq_len

    trainer = SFTTrainer(
        model=model,
        tokenizer=tok,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        args=SFTConfig(**cfg),
    )

    print("=== Đang tiến hành huấn luyện (Training)... ===")
    trainer.train()

    print("=== Xuất định dạng GGUF q4_k_m cho Ollama (Chỉ ~1.9GB) ===")
    model.save_pretrained_gguf("mindmap-model-gguf", tok, quantization_method="q4_k_m")
    print("-> Đã xuất thành công GGUF vào ./mindmap-model-gguf/")

    shutil.rmtree("/tmp/checkpoints", ignore_errors=True)
    print("=== HUẤN LUYỆN VÀ XUẤT MODEL THÀNH CÔNG! ===")

if __name__ == "__main__":
    main()
