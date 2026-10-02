"""Stage 4 CodeT5+LoRA Fine-Tuning for Semantic Error Repair.

Trains a Seq2Seq LoRA adapter on data/semantic_splits to predict line-relative edits
for model-targeted semantic error kinds:
1. undeclared (context-dependent declaration / usage repair)
2. redeclared (variable renaming / disambiguation)
3. unknown_member (struct member access correction)

Target format: LINE <L>: <repaired_line>
"""
import os
import argparse
import json
import time
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from peft import LoraConfig, get_peft_model, PeftModel

BASE_MODEL_NAME = "Salesforce/codet5-base"
LOCAL_TOKENIZER_PATH = "models/codet5_patch_adapter"
MAX_SRC_LEN = 144
MAX_TGT_LEN = 32


def format_prompt(row: dict) -> str:
    """Format input prompt for CodeT5 semantic repair."""
    code = row.get("input", "")
    family = row.get("family", "")
    line = row.get("error_line", 1)
    col = row.get("error_col", 0)
    name = row.get("target_name", "")

    prompt = f"repair_semantic kind={family} name={name} line={line} col={col}\n{code}\n--> edit:"
    return prompt.strip()


class SemanticPatchDataset(Dataset):
    def __init__(self, data_path: str, tokenizer, samples_per_kind: int = None, max_samples: int = None):
        from collections import defaultdict
        by_kind = defaultdict(list)
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                prompt = format_prompt(row)
                target = row.get("target_edit", "")
                kind = row.get("family", "unknown")
                if prompt and target:
                    if samples_per_kind is None or len(by_kind[kind]) < samples_per_kind:
                        by_kind[kind].append((prompt, target))

        self.samples = []
        for k, items in by_kind.items():
            self.samples.extend(items)
        if max_samples:
            self.samples = self.samples[:max_samples]

        import random
        random.seed(42)
        random.shuffle(self.samples)
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        src_text, tgt_text = self.samples[idx]

        src_enc = self.tokenizer(
            src_text,
            truncation=True,
            padding="max_length",
            max_length=MAX_SRC_LEN,
            return_tensors="pt",
        )

        tgt_enc = self.tokenizer(
            tgt_text,
            truncation=True,
            padding="max_length",
            max_length=MAX_TGT_LEN,
            return_tensors="pt",
        )

        labels = tgt_enc.input_ids.squeeze(0)
        labels[labels == self.tokenizer.pad_token_id] = -100

        return {
            "input_ids": src_enc.input_ids.squeeze(0),
            "attention_mask": src_enc.attention_mask.squeeze(0),
            "labels": labels,
        }


def evaluate_loss(model, dataloader, device) -> float:
    model.eval()
    total_loss = 0.0
    steps = 0
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            total_loss += outputs.loss.item()
            steps += 1
            if steps >= 25:  # Cap eval steps for speed on CPU
                break
    return total_loss / max(steps, 1)


def train_adapter(
    train_path: str,
    val_path: str,
    out_dir: str,
    epochs: int = 2,
    batch_size: int = 8,
    lr: float = 1e-4,
    samples_per_kind: int = 100,
    max_train_samples: int = None,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        try:
            torch.set_num_threads(8)
        except Exception:
            pass
    print(f"Using device: {device}", flush=True)

    print("Loading tokenizer and base model...", flush=True)
    if os.path.exists(LOCAL_TOKENIZER_PATH):
        tokenizer = AutoTokenizer.from_pretrained(LOCAL_TOKENIZER_PATH)
    else:
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)

    base_model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q", "v"],
        lora_dropout=0.05,
        bias="none",
        task_type="SEQ_2_SEQ_LM",
    )

    model = get_peft_model(base_model, lora_config)
    model.print_trainable_parameters()
    model.to(device)

    print(f"Loading datasets from {train_path} and {val_path} (balanced: {samples_per_kind}/kind)...", flush=True)
    train_ds = SemanticPatchDataset(train_path, tokenizer, samples_per_kind=samples_per_kind, max_samples=max_train_samples)
    val_ds = SemanticPatchDataset(val_path, tokenizer, samples_per_kind=30, max_samples=100)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    print(f"Loaded {len(train_ds)} train samples, {len(val_ds)} val samples.", flush=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        start_time = time.time()

        for step, batch in enumerate(train_loader, start=1):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            loss.backward()

            optimizer.step()
            optimizer.zero_grad()

            total_loss += loss.item()

            if step % 10 == 0 or step == len(train_loader):
                elapsed = time.time() - start_time
                print(f"Epoch {epoch+1}/{epochs} | Step {step}/{len(train_loader)} | Loss: {loss.item():.4f} | Elapsed: {elapsed:.1f}s", flush=True)

        avg_train_loss = total_loss / len(train_loader)
        avg_val_loss = evaluate_loss(model, val_loader, device)
        print(f"--- Epoch {epoch+1} Complete | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} ---", flush=True)

    print(f"Saving fine-tuned adapter to {out_dir}...", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    # Save metadata
    meta = {
        "base_model": BASE_MODEL_NAME,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "train_samples": len(train_ds),
        "target_kinds": ["undeclared", "redeclared", "unknown_member"],
        "target_format": "LINE <L>: <repaired_line>",
    }
    with open(os.path.join(out_dir, "training_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("Training finished successfully.", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", type=str, default="data/semantic_splits/train.jsonl")
    p.add_argument("--val", type=str, default="data/semantic_splits/val.jsonl")
    p.add_argument("--out", type=str, default="models/codet5_semantic_adapter")
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--batch_size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--samples_per_kind", type=int, default=100)
    p.add_argument("--max_samples", type=int, default=None)
    args = p.parse_args()

    train_adapter(
        train_path=args.train,
        val_path=args.val,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        samples_per_kind=args.samples_per_kind,
        max_train_samples=args.max_samples,
    )


if __name__ == "__main__":
    main()
