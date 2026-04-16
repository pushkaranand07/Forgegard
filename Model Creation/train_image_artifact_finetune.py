"""
Lightweight fine-tuning script for REAL vs AI-generated image detection.

This script keeps the existing project style (PyTorch) and introduces:
  - Dual-branch features: RGB backbone + artifact map branch
  - BCE + Focal loss blend (handles class imbalance/hard examples)
  - Validation metrics: F1, AUC, EER proxy threshold sweep
"""

import os
import random
import argparse
from dataclasses import dataclass

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class TrainConfig:
    data_root: str = "./data/ai_image_detection"
    epochs: int = 8
    batch_size: int = 16
    lr: float = 1e-4
    image_size: int = 224
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    out_path: str = "./artifacts/image_detector_finetuned.pt"


def make_artifact_map(img_bgr: np.ndarray) -> np.ndarray:
    """Create a single-channel artifact map from frequency + residual cues."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=30, sigmaSpace=30)
    residual = np.abs(gray - denoised)

    fft = np.fft.fftshift(np.fft.fft2(gray))
    mag = np.log1p(np.abs(fft))
    mag = (mag - mag.min()) / (mag.max() - mag.min() + 1e-8)

    residual = (residual - residual.min()) / (residual.max() - residual.min() + 1e-8)
    artifact = 0.6 * residual + 0.4 * mag
    return artifact.astype(np.float32)


class RealVsAIDataset(Dataset):
    """
    Expected structure:
      data_root/
        train/real, train/fake
        val/real,   val/fake
    """

    def __init__(self, split_root: str, image_size: int):
        self.samples = []
        self.rgb_tf = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.art_tf = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
        ])

        for class_name, label in (("real", 0), ("fake", 1)):
            folder = os.path.join(split_root, class_name)
            if not os.path.isdir(folder):
                continue
            for f in os.listdir(folder):
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    self.samples.append((os.path.join(folder, f), label))
        random.shuffle(self.samples)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img_bgr = cv2.imread(path)
        if img_bgr is None:
            raise ValueError(f"Could not read {path}")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        artifact = make_artifact_map(img_bgr)

        rgb_tensor = self.rgb_tf(img_rgb)
        art_tensor = self.art_tf(artifact)  # [1,H,W]
        return rgb_tensor, art_tensor, torch.tensor([float(label)], dtype=torch.float32)


class ArtifactAwareDetector(nn.Module):
    """RGB feature branch + artifact map feature branch."""

    def __init__(self):
        super().__init__()
        backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.rgb = nn.Sequential(*list(backbone.children())[:-1])  # [B,512,1,1]

        self.art_branch = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )

        self.head = nn.Sequential(
            nn.Linear(512 + 32, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward(self, rgb, art):
        rgb_feat = self.rgb(rgb).flatten(1)
        art_feat = self.art_branch(art).flatten(1)
        fused = torch.cat([rgb_feat, art_feat], dim=1)
        return self.head(fused)


class FocalLossBinary(nn.Module):
    """Binary focal loss on logits."""

    def __init__(self, alpha=0.25, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.bce = nn.BCEWithLogitsLoss(reduction="none")

    def forward(self, logits, targets):
        bce = self.bce(logits, targets)
        probs = torch.sigmoid(logits)
        pt = torch.where(targets == 1, probs, 1 - probs)
        focal = self.alpha * ((1 - pt) ** self.gamma) * bce
        return focal.mean()


def compute_metrics(y_true, y_prob):
    """Threshold sweep for best F1 + EER proxy."""
    best_f1 = 0.0
    best_t = 0.5
    best_far_frr_gap = 1e9
    eer_proxy = 1.0

    for t in np.linspace(0.1, 0.9, 161):
        y_pred = (y_prob >= t).astype(np.int32)
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        tn = np.sum((y_true == 0) & (y_pred == 0))
        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)
        far = fp / (fp + tn + 1e-8)  # false accept rate
        frr = fn / (fn + tp + 1e-8)  # false reject rate
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
        gap = abs(far - frr)
        if gap < best_far_frr_gap:
            best_far_frr_gap = gap
            eer_proxy = (far + frr) / 2.0

    return {"best_f1": float(best_f1), "best_threshold": best_t, "eer_proxy": float(eer_proxy)}


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune artifact-aware REAL vs AI image detector.")
    parser.add_argument("--data_dir", type=str, default="./data/ai_image_detection", help="Dataset root directory.")
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs.")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size.")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate.")
    parser.add_argument("--image_size", type=int, default=224, help="Input image size.")
    parser.add_argument("--out_path", type=str, default="./artifacts/image_detector_finetuned.pt", help="Output checkpoint path.")
    return parser.parse_args()


def run():
    args = parse_args()
    cfg = TrainConfig(
        data_root=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        image_size=args.image_size,
        out_path=args.out_path,
    )
    os.makedirs(os.path.dirname(cfg.out_path), exist_ok=True)

    train_ds = RealVsAIDataset(os.path.join(cfg.data_root, "train"), cfg.image_size)
    val_ds = RealVsAIDataset(os.path.join(cfg.data_root, "val"), cfg.image_size)
    train_dl = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, num_workers=2)
    val_dl = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=2)

    model = ArtifactAwareDetector().to(cfg.device)
    bce = nn.BCEWithLogitsLoss()
    focal = FocalLossBinary(alpha=0.30, gamma=2.0)
    optimizer = optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=1e-4)

    best_val_f1 = -1.0
    for epoch in range(cfg.epochs):
        model.train()
        running_loss = 0.0
        for rgb, art, y in train_dl:
            rgb, art, y = rgb.to(cfg.device), art.to(cfg.device), y.to(cfg.device)
            logits = model(rgb, art)
            loss = 0.7 * bce(logits, y) + 0.3 * focal(logits, y)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item())

        model.eval()
        all_probs, all_y = [], []
        with torch.no_grad():
            for rgb, art, y in val_dl:
                rgb, art = rgb.to(cfg.device), art.to(cfg.device)
                logits = model(rgb, art)
                probs = torch.sigmoid(logits).detach().cpu().numpy().reshape(-1)
                all_probs.extend(probs.tolist())
                all_y.extend(y.numpy().reshape(-1).tolist())

        y_true = np.array(all_y, dtype=np.int32)
        y_prob = np.array(all_probs, dtype=np.float32)
        metrics = compute_metrics(y_true, y_prob)

        print(
            f"Epoch {epoch + 1}/{cfg.epochs} "
            f"loss={running_loss / max(1, len(train_dl)):.4f} "
            f"val_f1={metrics['best_f1']:.4f} "
            f"thr={metrics['best_threshold']:.3f} "
            f"eer~={metrics['eer_proxy']:.4f}"
        )

        if metrics["best_f1"] > best_val_f1:
            best_val_f1 = metrics["best_f1"]
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "best_threshold": metrics["best_threshold"],
                    "best_f1": metrics["best_f1"],
                    "eer_proxy": metrics["eer_proxy"],
                },
                cfg.out_path,
            )

    print(f"Saved best checkpoint to {cfg.out_path}")


if __name__ == "__main__":
    run()
