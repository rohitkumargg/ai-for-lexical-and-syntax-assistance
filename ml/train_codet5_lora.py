import os
import argparse
import torch
from torch.utils.data import Dataset, DataLoader

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
)
from torch.optim import AdamW

from peft import LoraConfig, get_peft_model

from ml.dataset_loader import load_jsonl_inputs_targets


MODEL_NAME = "Salesforce/codet5-base"

MAX_LEN = 256
BATCH_SIZE = 8
EPOCHS = 3
LR = 5e-5


class PatchDataset(Dataset):
    def __init__(self, inputs, targets, tokenizer):
        self.inputs = inputs
        self.targets = targets
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        source = self.inputs[idx]
        target = self.targets[idx]

        src = self.tokenizer(
            source,
            truncation=True,
            padding="max_length",
            max_length=MAX_LEN,
            return_tensors="pt",
        )

        tgt = self.tokenizer(
            target,
            truncation=True,
            padding="max_length",
            max_length=MAX_LEN,
            return_tensors="pt",
        )

        labels = tgt.input_ids.squeeze(0)
        labels[labels == self.tokenizer.pad_token_id] = -100

        return {
            "input_ids": src.input_ids.squeeze(0),
            "attention_mask": src.attention_mask.squeeze(0),
            "labels": labels,
        }


def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q", "k", "v", "o"],
        lora_dropout=0.05,
        bias="none",
        task_type="SEQ_2_SEQ_LM",
    )

    model = get_peft_model(model, lora_config)
    return tokenizer, model


def evaluate_loss(model, dataloader, device):
    model.eval()
    total = 0.0
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
            total += outputs.loss.item()
            steps += 1

    return total / max(steps, 1)


def train(train_path: str, val_path: str, out_dir: str):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)

    print("Loading model...")
    tokenizer, model = load_model()
    model.to(device)

    print("Loading datasets...")
    train_inputs, train_targets = load_jsonl_inputs_targets(train_path, src_key="input", tgt_key="target")
    val_inputs, val_targets = load_jsonl_inputs_targets(val_path, src_key="input", tgt_key="target")

    train_dataset = PatchDataset(train_inputs, train_targets, tokenizer)
    val_dataset = PatchDataset(val_inputs, val_targets, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    optimizer = AdamW(model.parameters(), lr=LR)

    print("Starting training...")
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0

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

            if step % 200 == 0:
                print(f"  epoch {epoch+1} step {step}/{len(train_loader)} loss={loss.item():.4f}")

        avg_train_loss = total_loss / len(train_loader)
        avg_val_loss = evaluate_loss(model, val_loader, device)

        print(f"Epoch {epoch+1}/{EPOCHS} | train loss: {avg_train_loss:.4f} | val loss: {avg_val_loss:.4f}")

    print("Saving LoRA adapter + tokenizer...")
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    print("Saved to:", out_dir)
    print("Training complete.")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--train", type=str, required=True, help="Path to train.jsonl")
    p.add_argument("--val", type=str, required=True, help="Path to val.jsonl")
    p.add_argument("--out", type=str, default="models/codet5_lora", help="Output dir for adapter+tokenizer")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args.train, args.val, args.out)