"""Render the diagnostic figures used by reports/baseline_v0.md."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "output" / "novel_pairs_100_title_localizations.csv"
OUTPUT_DIR = ROOT / "reports" / "assets"
DIMENSIONS = [
    "semantic_fidelity",
    "natural_english",
    "genre_tone_fit",
    "target_market_fit",
    "reader_appeal",
    "memorability_distinctiveness",
    "clarity_concision",
    "integrity_safety",
]
SHORT_LABELS = [
    "Fidelity", "Natural", "Genre fit", "Market fit",
    "Appeal", "Memory", "Clarity", "Integrity",
]
COLORS = {
    "ink": "#243746", "muted": "#657786", "grid": "#D9E2E8",
    "blue": "#5B8DB8", "light_blue": "#DCEAF7", "teal": "#2A9D8F",
    "red": "#D1495B", "background": "#FAFCFD",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def canvas(width: int, height: int, title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.text((width // 2, 32), title, fill=COLORS["ink"], font=font(28, True), anchor="ma")
    return image, draw


def load_data() -> pd.DataFrame:
    data = pd.read_csv(INPUT, encoding="utf-8-sig")
    numeric = ["rank", "candidate_total_score", "selected_score", *DIMENSIONS]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data[data["status"].eq("success")].copy()


def save_dimension_boxplot(data: pd.DataFrame) -> None:
    image, draw = canvas(1500, 820, "Baseline V0: candidate score distributions (n=1,190)")
    left, top, right, bottom = 105, 105, 1450, 690
    y = lambda value: bottom - (value - 1) / 9 * (bottom - top)
    for value in range(1, 11):
        yy = y(value)
        draw.line((left, yy, right, yy), fill=COLORS["grid"], width=1)
        draw.text((left - 18, yy), str(value), fill=COLORS["muted"], font=font(18), anchor="rm")
    step = (right - left) / len(DIMENSIONS)
    for index, (column, label) in enumerate(zip(DIMENSIONS, SHORT_LABELS)):
        values = data[column].dropna()
        q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
        low, high = values.min(), values.max()
        x = left + step * (index + 0.5)
        box_width = 82
        draw.line((x, y(high), x, y(low)), fill=COLORS["blue"], width=3)
        draw.line((x - 22, y(high), x + 22, y(high)), fill=COLORS["blue"], width=3)
        draw.line((x - 22, y(low), x + 22, y(low)), fill=COLORS["blue"], width=3)
        draw.rectangle((x - box_width / 2, y(q3), x + box_width / 2, y(q1)),
                       fill=COLORS["light_blue"], outline=COLORS["blue"], width=3)
        draw.line((x - box_width / 2, y(median), x + box_width / 2, y(median)),
                  fill=COLORS["red"], width=4)
        draw.text((x, bottom + 30), label, fill=COLORS["ink"], font=font(17), anchor="ma")
        draw.text((x, bottom + 58), f"mean {values.mean():.2f}", fill=COLORS["muted"], font=font(15), anchor="ma")
    draw.text((18, 78), "Judge score (1–10)", fill=COLORS["ink"], font=font(18), anchor="la")
    image.save(OUTPUT_DIR / "baseline_v0_dimension_distributions.png")


def save_margin_histogram(data: pd.DataFrame) -> None:
    ranked = data.pivot(index="sample_id", columns="rank", values="candidate_total_score")
    margins = ranked[1] - ranked[2]
    counts = margins.value_counts().sort_index()
    image, draw = canvas(1300, 760, "Baseline V0: Top-1 minus Top-2 score margin (n=100)")
    left, top, right, bottom = 100, 110, 1240, 630
    max_count = int(counts.max())
    for value in range(0, max_count + 1, 2):
        yy = bottom - value / max_count * (bottom - top)
        draw.line((left, yy, right, yy), fill=COLORS["grid"], width=1)
        draw.text((left - 15, yy), str(value), fill=COLORS["muted"], font=font(17), anchor="rm")
    bar_width = (right - left) / len(counts)
    for index, (margin, count) in enumerate(counts.items()):
        x1 = left + index * bar_width + 4
        x2 = left + (index + 1) * bar_width - 4
        y1 = bottom - count / max_count * (bottom - top)
        draw.rectangle((x1, y1, x2, bottom), fill=COLORS["blue"])
        draw.text(((x1 + x2) / 2, bottom + 25), f"{margin:g}", fill=COLORS["ink"], font=font(15), anchor="ma")
        draw.text(((x1 + x2) / 2, y1 - 5), str(int(count)), fill=COLORS["muted"], font=font(14), anchor="ms")
    draw.text(((left + right) / 2, 695), f"Score margin   |   mean {margins.mean():.2f}   median {margins.median():.2f}",
              fill=COLORS["ink"], font=font(18), anchor="ma")
    image.save(OUTPUT_DIR / "baseline_v0_top12_margin.png")


def save_genre_summary(data: pd.DataFrame) -> None:
    winners = data[data["rank"].eq(1)].copy()
    second = data[data["rank"].eq(2)].set_index("sample_id")["candidate_total_score"]
    winners["margin"] = winners["selected_score"] - winners["sample_id"].map(second)
    summary = winners.groupby("genre").agg(
        samples=("sample_id", "size"), winner_score=("selected_score", "mean"), margin=("margin", "mean")
    ).sort_values("winner_score")
    image, draw = canvas(1450, 780, "Baseline V0 diagnostics by top-level genre")
    panel_specs = [(90, 690, "winner_score", 65, 90, COLORS["blue"], "Mean selected score"),
                   (790, 1370, "margin", 0, 5, COLORS["teal"], "Mean Top-1–Top-2 margin")]
    top, row_height = 155, 80
    for left, right, column, low, high, color, subtitle in panel_specs:
        draw.text(((left + right) / 2, 102), subtitle, fill=COLORS["ink"], font=font(21, True), anchor="ma")
        for row_index, (genre, row) in enumerate(summary.iterrows()):
            yy = top + row_index * row_height
            draw.text((left, yy + 21), genre, fill=COLORS["ink"], font=font(18), anchor="lm")
            bar_left, bar_right = left + 110, right - 80
            baseline = bar_left + (row[column] - low) / (high - low) * (bar_right - bar_left)
            draw.rectangle((bar_left, yy + 5, baseline, yy + 38), fill=color)
            suffix = f'{row[column]:.1f} (n={int(row["samples"])})' if column == "winner_score" else f'{row[column]:.2f}'
            draw.text((baseline + 8, yy + 21), suffix, fill=COLORS["muted"], font=font(16), anchor="lm")
        draw.line((left + 110, top - 12, left + 110, top + len(summary) * row_height - 25), fill=COLORS["grid"], width=2)
    image.save(OUTPUT_DIR / "baseline_v0_genre_summary.png")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_data()
    save_dimension_boxplot(data)
    save_margin_histogram(data)
    save_genre_summary(data)


if __name__ == "__main__":
    main()
