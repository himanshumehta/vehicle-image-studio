#!/usr/bin/env python3
"""Offline eval suite: edit preservation, background-removal mask quality, input guards.

    python evals/run_evals.py                    # deterministic suites, stub segmentation model
    python evals/run_evals.py --bg-model u2net   # also score the real u2net on 20 synthetic scenes

Writes ``evals/results.json`` and ``evals/results.md`` (``--out-dir`` to change).
No network and no API keys: provider keys are blanked before the app is imported,
the Gemini adapter only ever sees recorded-shape responses from a stub client,
and ``--bg-model u2net`` refuses to run unless the weights are already cached.

Exit status is 1 if any deterministic gate fails. Live-model scores are reported,
not gated. Findings (known issues the suite surfaces) are reported, not gated.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from statistics import mean
from unittest.mock import MagicMock, patch

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

# Same isolation as backend/tests/conftest.py, applied before any app module is imported.
os.environ.update({
    "STORAGE_BACKEND": "local",
    "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="vis-evals-storage-"),
    "SEED_SAMPLES": "false",
    "ALLOWED_HOSTS": "test,localhost,127.0.0.1",
})
for _secret in ("OPENAI_API_KEY", "GEMINI_API_KEY", "HF_TOKEN"):
    os.environ[_secret] = ""  # blanked so no provider can be configured, whatever the shell exports
sys.path[:0] = [str(BACKEND_DIR), str(REPO_ROOT)]

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from evals import fixtures  # noqa: E402
from evals.metrics import (  # noqa: E402
    DEFAULT_BAND_PX,
    DEFAULT_CHANGE_THRESHOLD,
    DEFAULT_MARGIN_PX,
    MAX_CHANGED_OUTSIDE,
    MIN_CHANGED_INSIDE,
    MIN_PSNR_OUTSIDE_DB,
    dilate,
    edit_preservation,
    mask_iou,
    preservation_verdict,
)


def png_bytes(image) -> bytes:
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def rnd(x, digits=4):
    return None if x is None else round(float(x), digits)


# --- 1. edit preservation -----------------------------------------------------

def inpaint(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """A stand-in for a correct clean-up: OpenCV inpainting touches only the masked pixels."""
    return cv2.inpaint(image, mask.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)


EDIT_CASES = {
    # name: (description, expected verdict or None for informational, builder(before, mask))
    "good_edit": ("inpaint exactly the plate + watermark boxes", "pass",
                  lambda b, m: inpaint(b, m)),
    "bleeding_edit": ("inpaint the boxes grown by 24 px", "fail",
                      lambda b, m: inpaint(b, dilate(m, 24))),
    "global_colour_shift": ("good edit, then RGB +12/+4/-8 on the whole frame", "fail",
                            lambda b, m: np.clip(inpaint(b, m).astype(int) + [12, 4, -8], 0, 255).astype(np.uint8)),
    "no_op": ("output identical to the input", "no_edit_inside_mask",
              lambda b, m: b.copy()),
    "resized_output": ("good edit returned at 16:9 instead of 3:2", "size_mismatch",
                       lambda b, m: np.asarray(Image.fromarray(inpaint(b, m)).resize((1024, 576)))),
    "good_edit_jpeg_q92": ("good edit, then a whole-frame JPEG q92 re-encode", None,
                           lambda b, m: np.asarray(fixtures.jpeg_roundtrip(Image.fromarray(inpaint(b, m)), 92))),
}


def run_edit_preservation(scenes) -> dict:
    rows, gates = {}, []
    for name, (desc, expected, build) in EDIT_CASES.items():
        scores, verdicts = [], []
        for scene in scenes:
            before = np.asarray(scene.image)
            score = edit_preservation(before, build(before, scene.edit_mask), scene.edit_mask)
            scores.append(score)
            verdicts.append(preservation_verdict(score))
        if expected is None:
            ok = None
        elif expected == "fail":
            ok = all(v != "pass" for v in verdicts)
        else:
            ok = all(v == expected for v in verdicts)

        def stat(field, scores=scores):
            vals = [getattr(s, field) for s in scores if getattr(s, field) is not None]
            return {"min": rnd(min(vals)), "max": rnd(max(vals))} if vals else None

        rows[name] = {
            "description": desc,
            "expected": expected,
            "verdicts": {v: verdicts.count(v) for v in sorted(set(verdicts))},
            "changed_outside_frac": stat("changed_outside_frac"),
            "changed_near_mask_frac": stat("changed_near_mask_frac"),
            "psnr_outside_db": stat("psnr_outside_db"),
            "changed_inside_frac": stat("changed_inside_frac"),
            "gate": ok,
        }
        if ok is not None:
            gates.append((f"edit_preservation/{name}", ok))
    # The metric must separate the good edit from both failure modes on every scene.
    good = rows["good_edit"]["changed_outside_frac"]["max"]
    worst_bad = min(rows["bleeding_edit"]["changed_outside_frac"]["min"],
                    rows["global_colour_shift"]["changed_outside_frac"]["min"])
    gates.append(("edit_preservation/separation", good < worst_bad))
    return {
        "scenes": len(scenes),
        "params": {"threshold": DEFAULT_CHANGE_THRESHOLD, "margin_px": DEFAULT_MARGIN_PX, "band_px": DEFAULT_BAND_PX,
                   "max_changed_outside": MAX_CHANGED_OUTSIDE, "min_psnr_outside_db": MIN_PSNR_OUTSIDE_DB,
                   "min_changed_inside": MIN_CHANGED_INSIDE},
        "cases": rows,
        "separation": {"good_max_changed_outside": good, "bad_min_changed_outside": worst_bad},
        "_gates": gates,
    }


# --- 2. Gemini adapter on recorded-shape responses ------------------------------

def gemini_stub(response_dict: dict, seen: list):
    from google.genai import types

    from image_edit_providers.gemini_editor import GeminiImageEditor

    response = types.GenerateContentResponse.model_validate(response_dict)

    def generate_content(model, contents, config):
        seen.append(config.image_config.aspect_ratio)
        return response

    editor = GeminiImageEditor(api_key="offline-stub")  # never reaches the network: _client is a stub
    editor._client = MagicMock()
    editor._client.models.generate_content.side_effect = generate_content
    return editor


async def run_gemini_adapter(scene) -> dict:
    from httpx import ASGITransport, AsyncClient

    from image_edit_providers.base import ImageEditError
    from main import app

    before = np.asarray(scene.image)
    edited = inpaint(before, scene.edit_mask)
    gates, cases = [], {}

    # a) a successful response: the adapter must hand back the model's pixels unchanged.
    seen: list = []
    editor = gemini_stub(fixtures.gemini_image_response(png_bytes(edited)), seen)
    error = None
    try:
        result = await editor.edit_image(png_bytes(before), "remove the plate")
    except Exception as e:  # recorded, then gated
        result, error = None, f"{type(e).__name__}: {e}"
    if result is not None:
        out = np.asarray(Image.open(io.BytesIO(result.image_bytes)).convert("RGB"))
        score = edit_preservation(before, out, scene.edit_mask)
        verdict = preservation_verdict(score)
        cases["success_response"] = {"verdict": verdict, "identical_to_fixture": bool(np.array_equal(out, edited)),
                                     "changed_outside_frac": rnd(score.changed_outside_frac),
                                     "provider": result.provider, "size": [result.width, result.height]}
        gates.append(("gemini/success_response", verdict == "pass" and np.array_equal(out, edited)))
    else:
        cases["success_response"] = {"error": error}
        gates.append(("gemini/success_response", False))

    # b) a blocked response must become a client-safe ImageEditError (502), not a crash.
    editor = gemini_stub(fixtures.gemini_blocked_response(), [])
    try:
        await editor.edit_image(png_bytes(before), "remove the plate")
        outcome = "no error"
    except ImageEditError as e:
        outcome = f"ImageEditError(retryable={e.retryable})"
    except Exception as e:
        outcome = f"{type(e).__name__}"
    cases["blocked_response"] = {"outcome": outcome}
    gates.append(("gemini/blocked_response", outcome == "ImageEditError(retryable=False)"))

    # c) the same two responses through POST /api/process/llm-edit.
    statuses = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for label, response_dict, want in (("success", fixtures.gemini_image_response(png_bytes(edited)), 200),
                                           ("blocked", fixtures.gemini_blocked_response(), 502)):
            stub = gemini_stub(response_dict, [])
            with patch("routers.processing.create_image_edit_provider", return_value=stub):
                resp = await client.post("/api/process/llm-edit", data={"preset": "remove_plate"},
                                         files={"file": ("car.png", png_bytes(before), "image/png")})
            statuses[label] = {"status": resp.status_code, "expected": want,
                               "x_edit_provider": resp.headers.get("x-edit-provider")}
            gates.append((f"gemini/http_{label}", resp.status_code == want))
    cases["http"] = statuses

    # d) finding (not gated): the aspect ratio the adapter asks Gemini for, per input shape.
    from google.genai import types
    supported = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
    doc = types.ImageConfig.model_fields["aspect_ratio"].description or ""
    aspect_rows = []
    for w, h in ((1200, 800), (1024, 1024), (800, 1200), (1600, 1200), (1920, 1080)):
        seen = []
        editor = gemini_stub(fixtures.gemini_image_response(png_bytes(np.zeros((h, w, 3), np.uint8))), seen)
        await editor.edit_image(png_bytes(np.zeros((h, w, 3), np.uint8)), "x")
        rw, rh = (int(v) for v in seen[0].split(":"))
        aspect_rows.append({"input": f"{w}x{h}", "input_ratio": round(w / h, 3), "requested": seen[0],
                            "requested_ratio": round(rw / rh, 3), "matches": abs(w / h - rw / rh) < 0.05})
    mismatches = [r["input"] for r in aspect_rows if not r["matches"]]
    cases["aspect_ratio"] = {
        "rows": aspect_rows,
        "sdk_supported_ratios": [r for r in supported if f'"{r}"' in doc],
        "finding": (f"requested aspect ratio differs from the input for {', '.join(mismatches)}; "
                    "the output cannot be compared pixel-for-pixel with the input") if mismatches else None,
    }
    return {"cases": cases, "_gates": gates}


# --- 3. background removal ----------------------------------------------------

def rembg_weights_path(name: str):
    """Path of an already cached rembg model, or None. Never downloads."""
    import rembg.sessions as registry

    if hasattr(registry, "sessions"):  # rembg 2.0.8x: {name: class}
        session_cls = registry.sessions.get(name)
    else:  # older rembg: parallel lists
        session_cls = next((c for c in registry.sessions_class if c.name() == name), None)
    if session_cls is None:
        return None
    home = session_cls.u2net_home()
    for candidate in (Path(home) / f"{name}.onnx", Path(home) / "models" / name / f"{name}.onnx"):
        if candidate.is_file():
            return candidate
    return None


def no_download_guard():
    """Make any attempt by rembg to fetch weights fail instead of downloading."""
    import pooch

    real = pooch.retrieve

    def guarded(url, known_hash=None, fname=None, path=None, **kw):
        if not (fname and path and (Path(path) / fname).is_file()):
            raise RuntimeError(f"evals refuse to download model weights ({url})")
        return real(url, known_hash, fname=fname, path=path, **kw)

    return patch("pooch.retrieve", guarded)


def score_service(service, scenes) -> dict:
    """Run ``service.remove_background`` on every scene; IoU of the raw and the refined mask vs ground truth."""
    raw_masks = {}
    predict = service._predict_mask

    def capture(img):
        m = predict(img)
        raw_masks["last"] = m
        return m

    service._predict_mask = capture
    rows = []
    for scene in scenes:
        t0 = time.perf_counter()
        out = Image.open(io.BytesIO(service.remove_background(png_bytes(scene.image))))
        elapsed = time.perf_counter() - t0
        alpha = np.asarray(out.getchannel("A"))
        rows.append({"scene": scene.name, "kind": scene.kind,
                     "iou_refined": rnd(mask_iou(alpha, scene.subject_mask)),
                     "iou_raw": rnd(mask_iou(raw_masks["last"], scene.subject_mask)),
                     "seconds": round(elapsed, 3)})
    service._predict_mask = predict

    def summary(field, kind=None):
        vals = [r[field] for r in rows if kind is None or r["kind"] == kind]
        return {"mean": rnd(mean(vals)), "min": rnd(min(vals)), "max": rnd(max(vals))}

    return {
        "iou_refined": summary("iou_refined"), "iou_raw": summary("iou_raw"),
        "iou_refined_car": summary("iou_refined", "car"), "iou_refined_bike": summary("iou_refined", "bike"),
        "seconds_per_image": summary("seconds"), "per_scene": rows,
    }


def stub_service(predict):
    from services.background_removal import BackgroundRemovalService

    svc = BackgroundRemovalService(model_name="stub")
    svc._session = object()  # loaded: load_model() is never called
    svc._predict_mask = predict
    return svc


def run_bg_harness(scenes) -> dict:
    """Scoring-harness check with stub models whose quality is known in advance."""
    gt = {}

    def lookup(img):
        return gt[img.size, np.asarray(img)[::97, ::89].tobytes()]

    for s in scenes:
        gt[s.image.size, np.asarray(s.image.convert("RGB"))[::97, ::89].tobytes()] = s.subject_mask

    stubs = {
        "oracle": lambda img: lookup(img).astype(np.float32),
        "shifted_40px": lambda img: np.roll(lookup(img), 40, axis=1).astype(np.float32),
        "empty": lambda img: np.zeros((img.height, img.width), np.float32),
    }
    results = {name: score_service(stub_service(fn), scenes) for name, fn in stubs.items()}
    o, s, e = (results[k]["iou_refined"] for k in ("oracle", "shifted_40px", "empty"))
    gates = [
        ("bg_harness/oracle_scores_high", o["min"] >= 0.95),
        ("bg_harness/empty_scores_zero", e["max"] == 0.0),
        ("bg_harness/ordering", o["min"] > s["max"] and s["min"] > e["max"]),
    ]
    for r in results.values():
        r.pop("per_scene")
        r.pop("seconds_per_image")
    return {"stubs": results, "_gates": gates}


def run_bg_live(scenes, model: str) -> dict:
    from services.background_removal import BackgroundRemovalService

    weights = rembg_weights_path(model)
    if weights is None:
        return {"model": model, "skipped": f"weights for '{model}' are not cached; run backend/scripts/download_models.py"}
    svc = BackgroundRemovalService(model_name=model)
    with no_download_guard():
        t0 = time.perf_counter()
        svc.load_model()
        load_s = time.perf_counter() - t0
        scored = score_service(svc, scenes)
    return {"model": model, "weights": str(weights).replace(str(Path.home()), "~"),
            "weights_bytes": weights.stat().st_size, "load_seconds": round(load_s, 2), **scored}


# --- 4. input guards ----------------------------------------------------------

async def run_guards() -> dict:
    from httpx import ASGITransport, AsyncClient

    from config import MAX_UPLOAD_BYTES, get_settings
    from main import app

    def encoded(fmt, size=(32, 32), mode="RGB"):
        buf = io.BytesIO()
        Image.new(mode, size).save(buf, format=fmt)
        return buf.getvalue()

    limit = get_settings().max_image_pixels
    side = int(limit ** 0.5) + 1
    bomb = encoded("PNG", (side, side), "L")  # declares > MAX_IMAGE_PIXELS, a few KB on disk
    ok_png = encoded("PNG")
    html = b"<html><script>alert(1)</script></html>"

    # Background removal with a stub model, so the real decode path runs but no weights load.
    seg = stub_service(lambda img: np.ones((img.height, img.width), np.float32))
    provider = MagicMock()
    provider.edit_image = MagicMock(side_effect=RuntimeError("paid call made"))

    cases = [
        # (name, endpoint, form data, file bytes, expected status)
        ("html_bytes_named_png", "/api/process/remove-background", {}, html, 400),
        ("gif_upload", "/api/process/remove-background", {}, encoded("GIF"), 400),
        ("bmp_upload", "/api/process/mirror", {}, encoded("BMP"), 400),
        ("tiff_upload", "/api/process/mirror", {}, encoded("TIFF"), 400),
        ("pixel_bomb_header", "/api/process/mirror", {}, bomb, 400),
        ("upload_over_25mb", "/api/process/mirror", {}, b"\0" * (MAX_UPLOAD_BYTES + 1), 413),
        ("upscale_output_over_limit", "/api/process/upscale", {"scale": "8"}, encoded("PNG", (400, 300)), 413),
        ("upscale_bad_scale", "/api/process/upscale", {"scale": "3"}, ok_png, 400),
        ("llm_edit_junk_before_paid_call", "/api/process/llm-edit", {"preset": "remove_plate"}, html, 400),
        ("llm_edit_prompt_too_long", "/api/process/llm-edit", {"prompt": "x" * 2001}, ok_png, 422),
        ("llm_edit_unknown_preset", "/api/process/llm-edit", {"preset": "remove_everything"}, ok_png, 400),
        ("valid_png_accepted", "/api/process/remove-background", {}, ok_png, 200),
    ]
    rows, gates = [], []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("routers.processing.bg_removal_service", seg), \
             patch("routers.processing.upscale_service") as upscaler, \
             patch("routers.processing.create_image_edit_provider", return_value=provider):
            for name, url, data, payload, want in cases:
                resp = await client.post(url, data=data, files={"file": ("upload.png", payload, "image/png")})
                rows.append({"case": name, "endpoint": url, "expected": want, "status": resp.status_code})
                gates.append((f"guards/{name}", resp.status_code == want))
            no_model_call = not upscaler.upscale.called
            no_paid_call = not provider.edit_image.called
        with patch("routers.processing.create_image_edit_provider", return_value=None):
            resp = await client.post("/api/process/llm-edit", data={"preset": "remove_plate"},
                                     files={"file": ("a.png", ok_png, "image/png")})
            rows.append({"case": "llm_edit_without_key", "endpoint": "/api/process/llm-edit",
                         "expected": 503, "status": resp.status_code})
            gates.append(("guards/llm_edit_without_key", resp.status_code == 503))
    gates.append(("guards/upscaler_not_run_for_refused_requests", no_model_call))
    gates.append(("guards/no_paid_call_for_refused_requests", no_paid_call))
    return {"cases": rows, "upscaler_called": not no_model_call, "provider_called": not no_paid_call,
            "bomb_bytes": len(bomb), "_gates": gates}


# --- report -------------------------------------------------------------------

def environment() -> dict:
    import importlib.metadata as md

    versions = {}
    for pkg in ("numpy", "pillow", "opencv-python-headless", "onnxruntime", "rembg", "google-genai", "fastapi"):
        try:
            versions[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            versions[pkg] = None
    return {"python": platform.python_version(), "platform": f"{platform.system()} {platform.machine()}",
            "packages": versions}


def fmt(x, digits=4):
    if x is None:
        return "n/a"
    if isinstance(x, dict):
        lo, hi = fmt(x["min"], digits), fmt(x["max"], digits)
        return lo if lo == hi else f"{lo} – {hi}"
    return f"{x:.{digits}f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def markdown(results: dict) -> str:
    ep, gm, bg, gd = (results[k] for k in ("edit_preservation", "gemini_adapter", "background_removal", "guards"))
    p = ep["params"]
    lines = [
        "# Eval results",
        "",
        f"Generated by `python evals/run_evals.py{' --bg-model ' + results['bg_model'] if results['bg_model'] != 'stub' else ''}`"
        f" on {results['environment']['platform']}, Python {results['environment']['python']}. "
        f"Gates: **{results['summary']['passed']}/{results['summary']['total']} passed**.",
        "",
        f"## Edit preservation ({ep['scenes']} synthetic scenes, mask = plate + watermark boxes)",
        "",
        f"A pixel counts as changed when an RGB channel moves by more than {p['threshold']}/255; the mask is grown by "
        f"{p['margin_px']} px first; \"near mask\" is the {p['band_px']} px ring around it. Pass = at most "
        f"{p['max_changed_outside']:.0%} changed outside, PSNR outside ≥ {p['min_psnr_outside_db']:.0f} dB, "
        f"and at least {p['min_changed_inside']:.0%} changed inside. Ranges are min – max over the scenes; "
        f"a PSNR of 99 means identical pixels (capped).",
        "",
        "| Case | Changed outside | Changed near mask | PSNR outside (dB) | Changed inside | Verdicts | Expected |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in ep["cases"].items():
        verdicts = ", ".join(f"{k} {v}" for k, v in r["verdicts"].items())
        lines.append(f"| {name} | {fmt(r['changed_outside_frac'])} | {fmt(r['changed_near_mask_frac'])} | "
                     f"{fmt(r['psnr_outside_db'], 1)} | {fmt(r['changed_inside_frac'])} | {verdicts} | "
                     f"{r['expected'] or 'informational'} |")
    s = gm["cases"]
    lines += [
        "",
        "## Gemini adapter on recorded-shape responses (stub client, no API call)",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Success response: pixels returned unchanged, preservation verdict | "
        f"{s['success_response'].get('verdict', s['success_response'].get('error'))}"
        f"{', identical' if s['success_response'].get('identical_to_fixture') else ''} |",
        f"| Blocked response | {s['blocked_response']['outcome']} |",
        f"| HTTP `/api/process/llm-edit`, success / blocked | {s['http']['success']['status']} / "
        f"{s['http']['blocked']['status']} |",
    ]
    for row in s["aspect_ratio"]["rows"]:
        lines.append(f"| Aspect ratio requested for {row['input']} | {row['requested']}"
                     f"{'' if row['matches'] else ' (mismatch: finding)'} |")
    lines += ["", "## Background removal (mask IoU vs ground truth)", ""]
    lines += ["| Model | Scenes | IoU refined mean (min – max) | IoU raw mean | Car | Motorcycle | s/image |",
              "|---|---|---|---|---|---|---|"]
    for name, r in bg["harness"]["stubs"].items():
        lines.append(f"| stub: {name} | {ep['scenes']} | {fmt(r['iou_refined']['mean'])} "
                     f"({fmt(r['iou_refined'])}) | {fmt(r['iou_raw']['mean'])} | "
                     f"{fmt(r['iou_refined_car']['mean'])} | {fmt(r['iou_refined_bike']['mean'])} | n/a |")
    live = bg.get("live")
    if live and "skipped" not in live:
        lines.append(f"| **{live['model']}** | {len(live['per_scene'])} | **{fmt(live['iou_refined']['mean'])}** "
                     f"({fmt(live['iou_refined'])}) | {fmt(live['iou_raw']['mean'])} | "
                     f"{fmt(live['iou_refined_car']['mean'])} | {fmt(live['iou_refined_bike']['mean'])} | "
                     f"{fmt(live['seconds_per_image']['mean'], 2)} |")
    elif live:
        lines.append(f"| {live['model']} | skipped: {live['skipped']} | | | | | |")
    else:
        lines.append("| live model | not run (use `--bg-model u2net`) | | | | | |")
    lines += ["", "## Input guards (through the ASGI app)", "", "| Case | Endpoint | Expected | Got |",
              "|---|---|---|---|"]
    for r in gd["cases"]:
        lines.append(f"| {r['case']} | `{r['endpoint']}` | {r['expected']} | {r['status']} |")
    lines.append(f"\nUpscaler called for refused requests: {gd['upscaler_called']}. "
                 f"Paid provider called for refused requests: {gd['provider_called']}.")
    if results["findings"]:
        lines += ["", "## Findings (reported, not gated)", ""] + [f"- {f}" for f in results["findings"]]
    failed = [name for name, ok in results["gates"].items() if not ok]
    if failed:
        lines += ["", "## Failed gates", ""] + [f"- {n}" for n in failed]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bg-model", default="stub", choices=["stub", "u2net", "isnet-general-use"],
                        help="also score this cached rembg model (default: stub models only)")
    parser.add_argument("--scenes", type=int, default=20, help="number of synthetic scenes (default 20)")
    parser.add_argument("--out-dir", default=str(EVALS_DIR), help="where results.json / results.md go")
    args = parser.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per ASGI request otherwise

    t0 = time.perf_counter()
    scenes = fixtures.build_scenes(args.scenes)
    results = {"bg_model": args.bg_model, "environment": environment(), "scenes": [s.name for s in scenes]}
    results["edit_preservation"] = run_edit_preservation(scenes)
    results["gemini_adapter"] = asyncio.run(run_gemini_adapter(scenes[0]))
    results["background_removal"] = {"harness": run_bg_harness(scenes)}
    if args.bg_model != "stub":
        results["background_removal"]["live"] = run_bg_live(scenes, args.bg_model)
    results["guards"] = asyncio.run(run_guards())

    gates = {}
    for section in (results["edit_preservation"], results["gemini_adapter"],
                    results["background_removal"]["harness"], results["guards"]):
        gates.update({name: bool(ok) for name, ok in section.pop("_gates")})
    results["gates"] = gates
    results["summary"] = {"passed": sum(gates.values()), "total": len(gates),
                          "seconds": round(time.perf_counter() - t0, 1)}
    findings = []
    if results["gemini_adapter"]["cases"]["aspect_ratio"]["finding"]:
        findings.append("Gemini adapter: " + results["gemini_adapter"]["cases"]["aspect_ratio"]["finding"])
    results["findings"] = findings

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "results.md").write_text(markdown(results), encoding="utf-8")
    failed = [n for n, ok in gates.items() if not ok]
    print(f"{results['summary']['passed']}/{len(gates)} gates passed in {results['summary']['seconds']} s; "
          f"results in {out / 'results.json'} and {out / 'results.md'}")
    for name in failed:
        print(f"FAILED: {name}")
    for f in findings:
        print(f"finding: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
