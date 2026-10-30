"""Build docs/demo.gif, a page tour of the app, from the screenshots in docs/images/.

Run: python scripts/make_demo_gif.py
"""

from PIL import Image

from planpilot.config import ROOT

IMAGES = ROOT / "docs" / "images"
SIZE = (800, 500)
SECONDS = 2.5
# (file, crop box (left, top, right, bottom)); None keeps the whole 800x500 image
FRAMES = [
    ("01_home_brief_generate.jpg", None),
    ("02_wbs_plan_checks.jpg", None),
    ("03_gantt_critical_path.jpg", None),
    ("04_risk_register_heatmap.jpg", None),
    ("05_monte_carlo_histogram_scurve.jpg", None),
    ("06_tornado_criticality.jpg", None),
    ("07_evm_dashboard_rag_report.jpg", (0, 260, 800, 760)),
    ("08_decision_comparison_memo.jpg", (0, 180, 800, 680)),
    ("08_decision_comparison_memo.jpg", (0, 870, 800, 1370)),
]


def main() -> None:
    frames = []
    for name, box in FRAMES:
        img = Image.open(IMAGES / name).convert("RGB")
        if box:
            img = img.crop(box)
        assert img.size == SIZE, (name, img.size)
        frames.append(img.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    out = ROOT / "docs" / "demo.gif"
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=int(SECONDS * 1000),
        loop=0,
        optimize=True,
    )
    print(f"{out.relative_to(ROOT)}: {len(frames)} frames, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
