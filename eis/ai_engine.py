from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

import torch
import torch.nn as nn
from torchvision import models, transforms

from .config import ModelConfig


@dataclass
class PredictionResult:
    manufacturer: str
    probabilities: Dict[str, float]


def build_transfer_model(num_classes: int) -> nn.Module:
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    for p in model.parameters():
        p.requires_grad = False
    model.fc = nn.Sequential(
        nn.Linear(model.fc.in_features, 256),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(256, num_classes),
    )
    return model


class AIEngine:
    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or ModelConfig()
        self.class_names = tuple(self.config.class_names)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_transfer_model(len(self.class_names))
        self._transform = transforms.Compose(
            [
                transforms.Resize((self.config.input_size, self.config.input_size)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        model_path = Path(self.config.model_path)
        if model_path.exists():
            loaded = torch.load(model_path, map_location=self.device)
            state = loaded["state_dict"] if isinstance(loaded, dict) and "state_dict" in loaded else loaded
            if isinstance(loaded, dict) and loaded.get("class_names"):
                self.class_names = tuple(loaded["class_names"])
                self.model = build_transfer_model(len(self.class_names))
            self.model.load_state_dict(state)
        self.model.to(self.device)
        self.model.eval()

    def save_model(self) -> None:
        path = Path(self.config.model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": self.model.state_dict(), "class_names": list(self.class_names)}, path)

    def predict_image(self, image_path: str | Path) -> PredictionResult:
        image = Image.open(image_path).convert("RGB")
        tensor = self._transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(tensor), dim=1).squeeze(0).cpu().numpy()
        mapping = {name: float(probs[i]) for i, name in enumerate(self.class_names)}
        return PredictionResult(manufacturer=max(mapping, key=mapping.get), probabilities=mapping)

    def extract_frames(self, video_path: str | Path) -> List[Path]:
        if cv2 is None:
            raise RuntimeError("OpenCV is required for video inference.")
        src = Path(video_path)
        out_dir = Path("tmp_frames") / src.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(str(src))
        idx, saved = 0, []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % self.config.frame_interval == 0:
                out = out_dir / f"frame_{idx:06d}.jpg"
                cv2.imwrite(str(out), frame)
                saved.append(out)
            idx += 1
        cap.release()
        return saved

    def aggregate(self, results: Sequence[PredictionResult]) -> PredictionResult:
        mean_probs = {k: 0.0 for k in self.class_names}
        for r in results:
            for k, v in r.probabilities.items():
                mean_probs[k] += v
        count = max(len(results), 1)
        for k in mean_probs:
            mean_probs[k] /= count
        majority = Counter(r.manufacturer for r in results).most_common(1)[0][0]
        top = max(mean_probs, key=mean_probs.get)
        return PredictionResult(top if mean_probs[top] >= 0.5 else majority, mean_probs)

    def predict_video(self, video_path: str | Path) -> PredictionResult:
        frames = self.extract_frames(video_path)
        if not frames:
            raise ValueError("No frames extracted from video.")
        return self.aggregate([self.predict_image(f) for f in frames])

