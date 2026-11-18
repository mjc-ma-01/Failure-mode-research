#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import torch
import torch.nn.functional as functional
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)

from data import UpwardSFTDataset, WeightedDataCollator, load_jsonl


LORA_TARGETS = (
    r".*model\.layers\.\d+\."
    r"(?:self_attn\.(?:q_proj|k_proj|v_proj|o_proj)|"
    r"linear_attn\.(?:in_proj_qkv|out_proj)|"
    r"mlp\.(?:gate_proj|up_proj|down_proj))$"
)


class WeightedAssistantTrainer(Trainer):
    def compute_loss(
        self,
        model,
        inputs,
        return_outputs=False,
        num_items_in_batch=None,
    ):
        weights = inputs.pop("sampling_weight").to(model.device)
        inputs.pop("length", None)
        outputs = model(**inputs)
        shift_logits = outputs.logits[:, :-1, :].contiguous()
        shift_labels = inputs["labels"][:, 1:].contiguous()
        token_losses = functional.cross_entropy(
            shift_logits.float().view(-1, shift_logits.size(-1)),
            shift_labels.view(-1),
            reduction="none",
            ignore_index=-100,
        ).view(shift_labels.shape)
        target_mask = shift_labels.ne(-100)
        target_counts = target_mask.sum(dim=1)
        if torch.any(target_counts == 0):
            raise RuntimeError("A batch example has no assistant target tokens")
        example_losses = (token_losses * target_mask).sum(dim=1) / target_counts
        loss = (example_losses * weights).sum() / weights.sum()
        return (loss, outputs) if return_outputs else loss


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--micro-batch-size", type=int, default=4)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--resume-from-checkpoint", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for training")
    set_seed(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    rows = load_jsonl(args.data)
    dataset = UpwardSFTDataset(rows, tokenizer, max_length=args.max_length)
    collator = WeightedDataCollator(tokenizer)

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=LORA_TARGETS,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.micro_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        bf16=True,
        tf32=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch_fused",
        logging_strategy="steps",
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=3,
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=args.num_workers,
        dataloader_pin_memory=True,
        train_sampling_strategy="group_by_length",
        length_column_name="length",
        seed=args.seed,
        data_seed=args.seed,
    )
    run_config = {
        "model": args.model,
        "data": args.data,
        "rows": len(rows),
        "max_length": args.max_length,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "micro_batch_size": args.micro_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "effective_batch_size": (
            args.micro_batch_size
            * args.gradient_accumulation_steps
            * int(os.environ.get("WORLD_SIZE", "1"))
        ),
        "seed": args.seed,
        "sampling": "no oversampling; sampling_weight is applied in loss",
        "loss": "per-example mean assistant-token CE, weighted example mean",
        "lora": {
            "rank": 16,
            "alpha": 32,
            "dropout": 0.05,
            "target_regex": LORA_TARGETS,
        },
    }
    (output_dir / "run_config.json").write_text(
        json.dumps(run_config, indent=2) + "\n",
        encoding="utf-8",
    )

    trainer = WeightedAssistantTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        processing_class=tokenizer,
    )
    result = trainer.train(
        resume_from_checkpoint=args.resume_from_checkpoint or None
    )
    trainer.save_model(str(output_dir / "final_adapter"))
    tokenizer.save_pretrained(str(output_dir / "final_adapter"))
    trainer.save_state()
    metrics = dict(result.metrics)
    metrics["train_samples"] = len(dataset)
    trainer.log_metrics("train", metrics)
    trainer.save_metrics("train", metrics)


if __name__ == "__main__":
    main()
