"""Compare synthetic baseline/candidate PDFs using ONE fixed renderer.

Usage: python integrationtests/compare_renderings.py BASELINE_DIR CANDIDATE_DIR
Run this from one candidate test image, with both artifact folders mounted.
"""
from pathlib import Path
import sys

import fitz
from PIL import Image, ImageChops, ImageStat

baseline, candidate = map(Path, sys.argv[1:])
names = sorted(p.name for p in baseline.glob("*.pdf"))
assert names and names == sorted(p.name for p in candidate.glob("*.pdf")), "Artifact sets must match and be nonempty"
for name in names:
    with fitz.open(baseline / name) as old, fitz.open(candidate / name) as new:
        assert len(old) == len(new)
        for i, (left, right) in enumerate(zip(old, new)):
            a, b = [page.get_pixmap(dpi=100, colorspace=fitz.csRGB, alpha=False) for page in [left, right]]
            assert (a.width, a.height) == (b.width, b.height), (name, i)
            diff = ImageChops.difference(Image.frombytes("RGB", (a.width, a.height), a.samples),
                                        Image.frombytes("RGB", (b.width, b.height), b.samples))
            mean_error = sum(ImageStat.Stat(diff).mean) / (3 * 255)
            assert mean_error < 0.01, (name, i, mean_error)
            print(f"{name} page {i + 1}: mean normalized pixel difference {mean_error:.6f}")
print(f"Compared {len(names)} PDFs using PyMuPDF {fitz.VersionBind}; tolerance 0.01 at 100 DPI")
