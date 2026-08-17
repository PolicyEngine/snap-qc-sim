"""Generate the migrations-paper figures from committed JSON artifacts only.

No models are fitted here.  The exact artifact key paths consumed are:

* paths and window: ``units.{RI,KY}.specifications.``
  ``primary_exclude_fy2016_drop_fy2021.outcomes.``
  ``strict_computing_dollars_per_case_month.path`` in
  ``analysis/riky_event_study_results.json``; Oregon uses
  ``specifications.primary_drop_fy2021.outcomes.``
  ``strict_computing_dollars_per_case_month.path`` in
  ``analysis/event_study_results.json``.
* placebo: ``units.RI.permutation_inference.``
  ``strict_computing_dollars_per_case_month.{placebo_effects,absolute_rank,``
  ``rank_denominator}`` and the RI primary-specification ``effect`` above.
  The artifact has placebo effects, not placebo paths, so the permitted
  effect-distribution fallback is drawn.
* channels: ``inferential_channels.<channel>.{effect,p_value}`` and
  ``descriptive_channels.<channel>.effect`` in
  ``analysis/uhip_decomposition_results.json``; fixed-donor values use
  ``side_by_side.fixed_donor.<channel>.{effect,p_value,status}`` and the check
  uses ``reproduction_check.passed`` in
  ``analysis/fixed_donor_decomposition_results.json``.

Usage: ``python paper-causal/generate_figures.py [--output-dir DIR]``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "figures"
ARTIFACT_FILES = {
    "riky": "riky_event_study_results.json",
    "oregon": "event_study_results.json",
    "joint": "uhip_decomposition_results.json",
    "fixed": "fixed_donor_decomposition_results.json",
}
FIGURE_FILES = (
    "fig-paths.png",
    "fig-placebo.png",
    "fig-channels.png",
    "fig-window.png",
)

# PolicyEngine-adjacent, colorblind-safe palette.
BLUE = "#0284C7"
NAVY = "#0F172A"
ORANGE = "#D97706"
GRAY = "#94A3B8"
LIGHT_BLUE = "#E0F2FE"
LIGHT_GRAY = "#F1F5F9"
TEXT_GRAY = "#475569"


def load_artifacts(artifact_dir: Path) -> dict[str, Any]:
    """Load only the four committed analysis artifacts."""
    return {
        name: json.loads((artifact_dir / filename).read_text())
        for name, filename in ARTIFACT_FILES.items()
    }


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.edgecolor": GRAY,
            "axes.linewidth": 0.7,
            "xtick.color": TEXT_GRAY,
            "ytick.color": TEXT_GRAY,
            "text.color": NAVY,
            "savefig.dpi": 300,
            "savefig.facecolor": "white",
        }
    )


def _clean_axis(ax: Any) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def _dollars(value: float, _position: float) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value):.0f}"


def _path(data: dict[str, Any], state: str) -> list[dict[str, float]]:
    if state in {"RI", "KY"}:
        return data["riky"]["units"][state]["specifications"][
            "primary_exclude_fy2016_drop_fy2021"
        ]["outcomes"]["strict_computing_dollars_per_case_month"]["path"]
    return data["oregon"]["specifications"]["primary_drop_fy2021"]["outcomes"][
        "strict_computing_dollars_per_case_month"
    ]["path"]


def _shade_protocol(ax: Any, state: str) -> None:
    if state in {"RI", "KY"}:
        ax.axvspan(2011.5, 2015.5, color=LIGHT_GRAY, zorder=-2)
        ax.axvspan(2016.5, 2024.5, color=LIGHT_BLUE, alpha=0.55, zorder=-2)
        ax.axvspan(
            2015.5, 2016.5, facecolor="white", edgecolor=GRAY, hatch="////", lw=0
        )
    else:
        ax.axvspan(2016.5, 2020.5, color=LIGHT_GRAY, zorder=-2)
        ax.axvspan(2021.5, 2024.5, color=LIGHT_BLUE, alpha=0.55, zorder=-2)
    ax.axvline(2021, color=GRAY, ls=":", lw=1)
    ax.text(
        2021,
        0.98,
        "FY2021 dropped",
        ha="center",
        va="top",
        fontsize=7.5,
        color=TEXT_GRAY,
        transform=ax.get_xaxis_transform(),
    )


def figure_paths(data: dict[str, Any], output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4), sharey=True)
    names = {"RI": "Rhode Island", "KY": "Kentucky", "OR": "Oregon"}
    for ax, state in zip(axes, names):
        path = _path(data, state)
        years = [row["year"] for row in path]
        _shade_protocol(ax, state)
        ax.plot(
            years,
            [row["treated"] for row in path],
            color=BLUE,
            lw=2,
            marker="o",
            ms=3,
            label="Treated",
            zorder=3,
        )
        ax.plot(
            years,
            [row["synthetic_donor"] for row in path],
            color=ORANGE,
            lw=1.7,
            marker="s",
            ms=2.8,
            label="Synthetic",
            zorder=3,
        )
        ax.set_title(names[state], loc="left")
        ax.set_xlim(min(years) - 0.4, max(years) + 0.4)
        ax.set_xticks([year for year in years if year % 2 == 0])
        ax.tick_params(axis="x", rotation=45)
        _clean_axis(ax)
    axes[0].set_ylabel("Strict outcome ($ per weighted case-month)")
    axes[0].yaxis.set_major_formatter(FuncFormatter(_dollars))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 1.01),
    )
    fig.suptitle(
        "Treated and synthetic strict-outcome paths", x=0.06, ha="left", y=1.08
    )
    fig.tight_layout()
    fig.savefig(output_dir / "fig-paths.png", bbox_inches="tight")
    plt.close(fig)


def figure_placebo(data: dict[str, Any], output_dir: Path) -> None:
    ri = data["riky"]["units"]["RI"]
    inference = ri["permutation_inference"]["strict_computing_dollars_per_case_month"]
    observed = ri["specifications"]["primary_exclude_fy2016_drop_fy2021"]["outcomes"][
        "strict_computing_dollars_per_case_month"
    ]["effect"]
    effects = sorted(
        inference["placebo_effects"].items(), key=lambda item: (item[1], item[0])
    )

    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    for index, (state, effect) in enumerate(effects):
        ax.scatter(effect, index, s=18, color=GRAY, alpha=0.75, edgecolors="none")
        if index in {0, len(effects) - 1}:
            ax.text(
                effect, index, f" {state}", va="center", fontsize=7, color=TEXT_GRAY
            )
    ax.axvline(0, color=GRAY, lw=0.8)
    ax.axvline(observed, color=BLUE, lw=2)
    ax.scatter(observed, len(effects) / 2, s=55, color=BLUE, zorder=3)
    ax.annotate(
        f"Rhode Island: ${observed:.2f}\nrank {inference['absolute_rank']} of "
        f"{inference['rank_denominator']}",
        xy=(observed, len(effects) / 2),
        xytext=(-78, 28),
        textcoords="offset points",
        arrowprops={"arrowstyle": "-", "color": BLUE},
        color=NAVY,
        fontsize=8,
    )
    ax.set_title("Rhode Island in-space placebo effects", loc="left")
    ax.set_xlabel("Post-period strict-outcome effect ($ per weighted case-month)")
    ax.set_ylabel("Pseudo-treated donors")
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(FuncFormatter(_dollars))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _clean_axis(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "fig-placebo.png", bbox_inches="tight")
    plt.close(fig)


def figure_channels(data: dict[str, Any], output_dir: Path) -> None:
    channels = [
        "mass_change",
        "defect_or_mass_change",
        "disregard",
        "defect",
        "entry",
        "arithmetic",
        "user",
    ]
    labels = {
        "mass_change": "Mass change",
        "defect_or_mass_change": "Defect or mass change",
        "disregard": "Disregard",
        "defect": "Defect",
        "entry": "Entry",
        "arithmetic": "Arithmetic",
        "user": "User",
    }
    fixed = data["fixed"]["side_by_side"]["fixed_donor"]
    inferential = data["joint"]["inferential_channels"]
    descriptive = data["joint"]["descriptive_channels"]
    joint_channels = inferential | descriptive
    y = list(range(len(channels)))[::-1]
    joint = [joint_channels[channel]["effect"] for channel in channels]
    fixed_effects = [fixed[channel]["effect"] for channel in channels]

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    for index, channel in enumerate(channels):
        color = BLUE if index < 3 else GRAY
        ax.plot(
            [joint[index], fixed_effects[index]],
            [y[index], y[index]],
            color=color,
            alpha=0.55,
            lw=1.3,
        )
        ax.scatter(
            joint[index],
            y[index],
            s=46,
            color=color,
            marker="o",
            zorder=3,
            label="Joint fit" if index == 0 else None,
        )
        ax.scatter(
            fixed_effects[index],
            y[index],
            s=46,
            facecolor="white",
            edgecolor=color,
            marker="s",
            linewidth=1.4,
            zorder=3,
            label="Fixed donor" if index == 0 else None,
        )
        if index < 3:
            p_joint = inferential[channel]["p_value"]
            p_fixed = fixed[channel]["p_value"]
            ax.text(
                max(joint[index], fixed_effects[index]) + 0.09,
                y[index],
                f"p={p_joint:.3f} / {p_fixed:.3f}",
                va="center",
                fontsize=7.5,
                color=TEXT_GRAY,
            )
    ax.axvline(0, color=GRAY, lw=0.8)
    ax.axhline(3.5, color="#CBD5E1", lw=0.8)
    ax.text(-0.02, 1.01, "Inferential", transform=ax.transAxes, color=BLUE, fontsize=8)
    ax.text(
        -0.02, 0.47, "Descriptive", transform=ax.transAxes, color=TEXT_GRAY, fontsize=8
    )
    ax.set_yticks(y, [labels[channel] for channel in channels])
    ax.set_xlabel("Effect ($ per weighted case-month)")
    ax.xaxis.set_major_formatter(FuncFormatter(_dollars))
    ax.set_title("Decomposition effects under both estimators", loc="left", pad=34)
    status = "passed" if data["fixed"]["reproduction_check"]["passed"] else "failed"
    ax.text(
        1,
        1.01,
        f"Client-placebo reproduction check: {status}",
        ha="right",
        transform=ax.transAxes,
        fontsize=8,
        color=TEXT_GRAY,
    )
    ax.legend(frameon=False, ncol=2, loc="lower right")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _clean_axis(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "fig-channels.png", bbox_inches="tight")
    plt.close(fig)


def figure_window(data: dict[str, Any], output_dir: Path) -> None:
    path = _path(data, "RI")
    years = [row["year"] for row in path]
    gaps = [row["gap"] for row in path]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    ax.axvspan(2016.5, 2019.5, color=LIGHT_BLUE, zorder=-2)
    ax.axvspan(2019.5, 2024.5, color=LIGHT_GRAY, zorder=-3)
    ax.axhline(0, color=GRAY, lw=0.8)
    ax.plot(years, gaps, color=BLUE, lw=1.8, marker="o", ms=3.5)
    ax.scatter(
        [2021],
        [gaps[years.index(2021)]],
        facecolors="white",
        edgecolors=GRAY,
        s=38,
        zorder=4,
    )
    ax.text(
        2021,
        gaps[years.index(2021)] - 0.65,
        "FY2021 dropped",
        ha="center",
        fontsize=7.5,
        color=TEXT_GRAY,
    )
    ax.text(
        2018,
        0.96,
        "FY2017–19 pre-named window",
        ha="center",
        va="top",
        transform=ax.get_xaxis_transform(),
        fontsize=8,
        color=TEXT_GRAY,
    )
    ax.set_xlim(2011.5, 2024.5)
    ax.set_xticks(range(2012, 2025, 2))
    ax.set_ylabel("RI strict gap ($)")
    ax.set_xlabel("Fiscal year")
    ax.yaxis.set_major_formatter(FuncFormatter(_dollars))
    ax.set_title("Rhode Island strict-outcome gap by fiscal year", loc="left")
    _clean_axis(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "fig-window.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "analysis")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _style()
    data = load_artifacts(args.artifact_dir)
    figure_paths(data, args.output_dir)
    figure_placebo(data, args.output_dir)
    figure_channels(data, args.output_dir)
    figure_window(data, args.output_dir)
    for filename in FIGURE_FILES:
        print(f"wrote {args.output_dir / filename}")


if __name__ == "__main__":
    main()
