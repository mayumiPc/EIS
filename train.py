from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from eis.ai_engine import AIEngine
from eis.config import ModelConfig


def train(dataset_root: Path, epochs: int = 10, batch_size: int = 16, lr: float = 1e-3, model_path: Path = Path("models/eis_classifier_base.pt")) -> None:
    train_ds = datasets.ImageFolder(dataset_root / "train", transform=transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]))
    val_ds = datasets.ImageFolder(dataset_root / "val", transform=transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]))
    if len(train_ds.classes) < 2:
        raise ValueError("Need at least 2 classes.")

    engine = AIEngine(ModelConfig(class_names=tuple(train_ds.classes), model_path=model_path))
    device = engine.device
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(engine.model.fc.parameters(), lr=lr)

    for epoch in range(epochs):
        engine.model.train()
        loss_sum = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            out = engine.model(x)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item()

        engine.model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                pred = torch.argmax(engine.model(x), dim=1)
                correct += (pred == y).sum().item()
                total += y.size(0)
        print(f"[epoch {epoch + 1}] loss={loss_sum / max(len(train_loader), 1):.4f} val_acc={correct / max(total, 1):.4f}")

    engine.save_model()
    print(f"Model saved to {model_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, default=Path("dataset"))
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--model-path", type=Path, default=Path("models/eis_classifier_base.pt"))
    a = p.parse_args()
    train(a.dataset, a.epochs, a.batch_size, a.lr, a.model_path)

