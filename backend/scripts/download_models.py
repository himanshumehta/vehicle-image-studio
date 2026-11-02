#!/usr/bin/env python3
"""Download the model weights the studio needs. Nothing here is committed to git.

    python backend/scripts/download_models.py            # everything below
    python backend/scripts/download_models.py --only rembg
    python backend/scripts/download_models.py --only realesrgan

1. rembg segmentation model (BG_REMOVAL_MODEL, default ``u2net``),
   cached by rembg under ~/.u2net (override with U2NET_HOME).
2. Real-ESRGAN x4plus: downloads the official ``RealESRGAN_x4plus.pth``
   (~64 MB, BSD-3-Clause, github.com/xinntao/Real-ESRGAN) and exports it to
   ONNX at ``$MODELS_DIR/realesrgan_x4plus.onnx`` (default backend/models/).
   The export needs torch once: ``pip install -r backend/requirements-models.txt``.

The RRDBNet architecture below is inlined from basicsr to avoid that dependency.
"""

import argparse
import os
import sys

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # torch is only needed for the Real-ESRGAN export
    torch = None
    nn = None


# ---------------------------------------------------------------------------
# RRDBNet architecture (from basicsr — inlined to avoid the dependency)
# ---------------------------------------------------------------------------

if nn is not None:

    class ResidualDenseBlock(nn.Module):
        def __init__(self, num_feat=64, num_grow_ch=32):
            super().__init__()
            self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
            self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x


    class RRDB(nn.Module):
        def __init__(self, num_feat, num_grow_ch=32):
            super().__init__()
            self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

        def forward(self, x):
            out = self.rdb1(x)
            out = self.rdb2(out)
            out = self.rdb3(out)
            return out * 0.2 + x


    class RRDBNet(nn.Module):
        def __init__(self, num_in_ch=3, num_out_ch=3, scale=4,
                     num_feat=64, num_block=23, num_grow_ch=32):
            super().__init__()
            self.scale = scale
            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = nn.Sequential(
                *[RRDB(num_feat, num_grow_ch) for _ in range(num_block)]
            )
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            feat = self.conv_first(x)
            body_feat = self.conv_body(self.body(feat))
            feat = feat + body_feat
            feat = self.lrelu(self.conv_up1(
                F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(
                F.interpolate(feat, scale_factor=2, mode="nearest")))
            out = self.conv_last(self.lrelu(self.conv_hr(feat)))
            return out


# ---------------------------------------------------------------------------
# Download + convert
# ---------------------------------------------------------------------------

PTH_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/"
    "v0.1.0/RealESRGAN_x4plus.pth"
)
PTH_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
from config import get_settings  # noqa: E402

MODEL_DIR = get_settings().models_dir
PTH_PATH = os.path.join(MODEL_DIR, "RealESRGAN_x4plus.pth")
ONNX_PATH = os.path.join(MODEL_DIR, "realesrgan_x4plus.onnx")


def download_pth():
    import requests

    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(PTH_PATH):
        print(f"PyTorch weights already exist: {PTH_PATH}")
        return

    print("Downloading RealESRGAN_x4plus.pth (~64 MB)...")
    resp = requests.get(PTH_URL, stream=True, timeout=120)
    resp.raise_for_status()
    tmp = PTH_PATH + ".tmp"
    total = 0
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            total += len(chunk)
            mb = total / (1024 * 1024)
            print(f"\r  {mb:.1f} MB downloaded", end="", flush=True)
    import hashlib

    h = hashlib.sha256()
    with open(tmp, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != PTH_SHA256:
        os.remove(tmp)
        sys.exit(f"Checksum mismatch for RealESRGAN_x4plus.pth: {h.hexdigest()}")
    os.rename(tmp, PTH_PATH)
    print(f"\n  Saved to {PTH_PATH} (sha256 verified)")


def convert():
    print("Loading PyTorch model...")
    model = RRDBNet(
        num_in_ch=3, num_out_ch=3, scale=4,
        num_feat=64, num_block=23, num_grow_ch=32,
    )
    state = torch.load(PTH_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state["params_ema"])
    model.eval()

    dummy = torch.randn(1, 3, 64, 64)

    print("Exporting to ONNX (fp32, dynamic axes)...")
    export_kwargs = dict(
        opset_version=11,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {2: "height", 3: "width"},
            "output": {2: "height", 3: "width"},
        },
    )
    try:  # torch >= 2.5: force the TorchScript exporter (no onnxscript needed)
        torch.onnx.export(model, dummy, ONNX_PATH, dynamo=False, **export_kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, ONNX_PATH, **export_kwargs)
    size_mb = os.path.getsize(ONNX_PATH) / (1024 * 1024)
    print(f"ONNX model saved: {ONNX_PATH} ({size_mb:.1f} MB)")

    # Clean up .pth to save space
    os.remove(PTH_PATH)
    print(f"Removed PyTorch weights: {PTH_PATH}")


def download_rembg():
    name = get_settings().bg_removal_model
    if name in ("birefnet", "rmbg-2.0"):
        print(f"BG_REMOVAL_MODEL={name} is a transformers model; it downloads from Hugging Face on first use.")
        return
    from rembg import new_session

    cache = os.environ.get("U2NET_HOME", os.path.expanduser("~/.u2net"))
    print(f"Fetching rembg model '{name}' (cache: {cache})...")
    new_session(name, providers=["CPUExecutionProvider"])
    print("  ok")


def download_realesrgan():
    if os.path.exists(ONNX_PATH):
        print(f"Real-ESRGAN ONNX already present: {ONNX_PATH}")
        return
    if torch is None:
        sys.exit(
            "torch is required once to export Real-ESRGAN to ONNX.\n"
            "  pip install -r backend/requirements-models.txt"
        )
    download_pth()
    convert()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["rembg", "realesrgan"], help="fetch just one model")
    args = parser.parse_args()
    if args.only in (None, "rembg"):
        download_rembg()
    if args.only in (None, "realesrgan"):
        download_realesrgan()
    print("Done.")
