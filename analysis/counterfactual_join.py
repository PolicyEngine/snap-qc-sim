"""Join Colorado SMD-off engine intermediates to the corrected error model.

Run from the repository root with::

    uv run --frozen --extra analysis python analysis/counterfactual_join.py

The entry point reads every round-1b manifest before its case file, validates
the case-level join against the zero-based SAV row number embedded in
``case_id``, refits the committed model specifications, and writes both JSON
and Markdown deterministically. The counterfactual is a model-implied
association, not a causal estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Match analysis/run_all.py before importing NumPy or scikit-learn transitively.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from snap_qc_sim import LEVERS, QcCase, lever_error, simulate, summarize

if __package__:
    from . import hurdle_deviation_model, train_error_model
else:
    import hurdle_deviation_model
    import train_error_model


ANALYSIS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_ROOT = Path(
    "~/.cache/axiom-oracles/v2b/cert-probe/simulations/fy2024/us-co"
).expanduser()
DEFAULT_JSON_OUTPUT = ANALYSIS_DIR / "counterfactual_co_smd.json"
DEFAULT_DOCUMENT_OUTPUT = ANALYSIS_DIR / "COUNTERFACTUAL.md"
ACCOUNTING_SOURCE = (
    REPO_ROOT / "paper" / "snapshot" / "labs" / "results_by_state_corrected.json"
)

SCENARIOS = ("floor", "point", "ceiling")
FISCAL_YEAR = 2024
JURISDICTION = "CO"
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 202408
CONFIDENCE_LEVEL = 0.95
COST_SHARE_DRAWS = 100_000
COST_SHARE_SEED = 11
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Round1bInputs:
    """Validated manifests and case rows from the certified engine run."""

    manifests: dict[str, dict[str, Any]]
    cases: dict[str, list[dict[str, Any]]]
    paths: dict[str, Path]
    sha256: dict[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            if not isinstance(row, dict):
                raise TypeError(f"{path}:{line_number}: row must be an object")
            rows.append(row)
    return rows


def _require_columns(
    frame: pd.DataFrame, columns: Sequence[str], *, context: str
) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{context} is missing columns: {', '.join(missing)}")


def load_round1b_inputs(input_root: Path = DEFAULT_INPUT_ROOT) -> Round1bInputs:
    """Read manifests first, then validate and load all round-1b case files."""
    root = Path(input_root).expanduser().resolve()
    paths = {
        "baseline/manifest.json": root / "baseline" / "manifest.json",
        "smd-off/manifest.json": root / "smd-off" / "manifest.json",
        **{
            f"smd-off/{scenario}/manifest.json": (
                root / "smd-off" / scenario / "manifest.json"
            )
            for scenario in SCENARIOS
        },
        "baseline/cases.jsonl": root / "baseline" / "cases.jsonl",
        **{
            f"smd-off/{scenario}/cases.jsonl": (
                root / "smd-off" / scenario / "cases.jsonl"
            )
            for scenario in SCENARIOS
        },
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing round-1b inputs: {', '.join(missing)}")

    # The manifests are intentionally exhausted before opening any JSONL.
    manifest_names = [name for name in paths if name.endswith("manifest.json")]
    manifests = {name: _read_json(paths[name]) for name in manifest_names}

    case_names = [name for name in paths if name.endswith("cases.jsonl")]
    raw_cases = {name: _read_jsonl(paths[name]) for name in case_names}
    cases = {
        "baseline": raw_cases["baseline/cases.jsonl"],
        **{
            scenario: raw_cases[f"smd-off/{scenario}/cases.jsonl"]
            for scenario in SCENARIOS
        },
    }
    hashes = {name: _sha256(path) for name, path in paths.items()}

    for label in ("baseline", *SCENARIOS):
        manifest_name = (
            "baseline/manifest.json"
            if label == "baseline"
            else f"smd-off/{label}/manifest.json"
        )
        case_name = (
            "baseline/cases.jsonl"
            if label == "baseline"
            else f"smd-off/{label}/cases.jsonl"
        )
        manifest = manifests[manifest_name]
        declared = manifest.get("output_file", {})
        if declared.get("sha256") != hashes[case_name]:
            raise ValueError(f"{manifest_name} does not hash {case_name}")
        if declared.get("row_count") != len(cases[label]):
            raise ValueError(f"{manifest_name} row count does not match {case_name}")

    baseline_ids = [row.get("case_id") for row in cases["baseline"]]
    if len(baseline_ids) != len(set(baseline_ids)):
        raise ValueError("baseline case IDs are not unique")
    for scenario in SCENARIOS:
        scenario_ids = [row.get("case_id") for row in cases[scenario]]
        if scenario_ids != baseline_ids:
            raise ValueError(f"{scenario} case IDs/order differ from baseline")
    if len(baseline_ids) != 856:
        raise ValueError(f"expected 856 Colorado cases, found {len(baseline_ids)}")

    return Round1bInputs(manifests, cases, paths, hashes)


def _source_row_from_case_id(case_id: str) -> int:
    parts = case_id.split("-")
    if len(parts) != 3 or parts[0] != str(FISCAL_YEAR):
        raise ValueError(f"unexpected engine case ID: {case_id}")
    try:
        return int(parts[2])
    except ValueError as error:
        raise ValueError(f"case ID has nonnumeric SAV row: {case_id}") from error


def load_joined_colorado_cases(inputs: Round1bInputs) -> pd.DataFrame:
    """Join engine IDs to FY2024 SAV rows using the preserved raw row index."""
    raw = train_error_model.load_year(FISCAL_YEAR, include_source_row_index=True).loc[
        lambda frame: frame["state"].eq(JURISDICTION)
    ]
    raw = raw.copy()
    raw["case_id"] = (
        raw["year"].astype(int).astype(str)
        + "-"
        + raw["YRMONTH"].astype(int).astype(str)
        + "-"
        + raw["source_row_index"].astype(int).astype(str)
    )
    if raw["case_id"].duplicated().any():
        raise ValueError("constructed SAV case IDs are not unique")
    raw = raw.set_index("case_id", drop=False)

    case_ids = [str(row["case_id"]) for row in inputs.cases["baseline"]]
    missing = sorted(set(case_ids) - set(raw.index))
    extra = sorted(set(raw.index) - set(case_ids))
    if missing or extra:
        raise ValueError(
            f"engine/SAV case coverage mismatch: missing={missing}, extra={extra}"
        )
    raw = raw.loc[case_ids].copy()

    for case_id, row in zip(case_ids, inputs.cases["baseline"], strict=True):
        source_row = _source_row_from_case_id(case_id)
        sav = raw.loc[case_id]
        if source_row != int(sav["source_row_index"]):
            raise ValueError(f"{case_id}: SAV source row mismatch")
        if int(row["YRMONTH"]) != int(sav["YRMONTH"]):
            raise ValueError(f"{case_id}: YRMONTH mismatch")
        if not np.isclose(float(row["HWGT"]), float(sav["HWGT"]), atol=1e-6):
            raise ValueError(f"{case_id}: HWGT mismatch")
        expected = float(row["qc_expected"]["snap_regular_month_allotment"])
        if expected != float(sav["FSBEN"]):
            raise ValueError(f"{case_id}: FSBEN mismatch")
        source_facts = row["source_facts"]
        for field in ("FSMEDEXP", "FSMEDDED"):
            if float(source_facts[field]) != float(sav[field]):
                raise ValueError(f"{case_id}: {field} mismatch")

    return raw


def _engine_delta_frame(
    rows: Sequence[Mapping[str, Any]], index: pd.Index
) -> pd.DataFrame:
    records: list[dict[str, float]] = []
    case_ids: list[str] = []
    for row in rows:
        deltas = row["deltas_smd_off_minus_smd_on"]
        benefit_delta = float(row["benefit_change_smd_off_minus_smd_on"])
        if benefit_delta != float(deltas["snap_regular_month_allotment"]):
            raise ValueError(f"{row['case_id']}: inconsistent benefit delta")
        case_ids.append(str(row["case_id"]))
        records.append(
            {
                "benefit_delta": benefit_delta,
                "medical_deduction_delta": float(deltas["medical_deduction"]),
                "shelter_deduction_delta": float(
                    deltas["snap_excess_shelter_deduction"]
                ),
                "net_income_delta": float(deltas["snap_net_income"]),
            }
        )
    frame = pd.DataFrame.from_records(records, index=pd.Index(case_ids))
    if not frame.index.equals(index):
        raise ValueError("engine delta frame does not align to SAV case IDs")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("engine deltas must be finite")
    return frame


def apply_smd_off_features(
    raw: pd.DataFrame,
    baseline_features: pd.DataFrame,
    engine_deltas: pd.DataFrame,
) -> pd.DataFrame:
    """Apply the SMD-off documentation flip and engine-computable repricing.

    Counterfactual values use QC fields as their baseline plus the engine's
    SMD-off-minus-SMD-on delta. This isolates the policy change from unrelated
    absolute-level bridge discrepancies in the round-1b engine baseline.
    """
    if not (
        raw.index.equals(baseline_features.index)
        and raw.index.equals(engine_deltas.index)
    ):
        raise ValueError("raw, feature, and engine-delta rows must share an index")
    _require_columns(
        raw,
        [
            "FSBEN",
            "BENMAX",
            "MINIMUM_BEN",
            "FSMEDDED",
            "FSDEPDED",
            "FSCSDED",
            "FSSLTDED",
            "FSERNDED",
            "FSNETINC",
            "FSGRINC",
            "CERTHHSZ",
            "FSUSIZE",
        ],
        context="raw counterfactual rows",
    )
    _require_columns(
        baseline_features,
        [
            "medical_expense_above_floor",
            "elderly_or_disabled",
            "med_doc_required",
        ],
        context="baseline counterfactual features",
    )
    _require_columns(
        engine_deltas,
        [
            "benefit_delta",
            "medical_deduction_delta",
            "shelter_deduction_delta",
            "net_income_delta",
        ],
        context="engine counterfactual deltas",
    )
    if not baseline_features["med_doc_required"].eq(0).all():
        raise ValueError("Colorado SMD-on baseline must have med_doc_required == 0")

    result = baseline_features.copy()
    no_smd = pd.Series(False, index=result.index)
    result["med_doc_required"] = train_error_model.medical_documentation_required(
        result["medical_expense_above_floor"],
        result["elderly_or_disabled"],
        no_smd,
    )

    formula_benefit = pd.to_numeric(raw["FSBEN"], errors="coerce") + pd.to_numeric(
        engine_deltas["benefit_delta"], errors="coerce"
    )
    maximum_benefit = pd.to_numeric(raw["BENMAX"], errors="coerce")
    minimum_benefit = pd.to_numeric(raw["MINIMUM_BEN"], errors="coerce")
    result["formula_benefit"] = formula_benefit
    result["formula_benefit_missing"] = formula_benefit.isna().astype(int)
    result["benefit_position_missing"] = (
        formula_benefit.isna() | maximum_benefit.isna() | minimum_benefit.isna()
    ).astype(int)
    relative_to_maximum = formula_benefit / maximum_benefit.replace(0, np.nan)
    result["at_max"] = relative_to_maximum.ge(0.999).astype(int)
    result["at_min"] = formula_benefit.le(minimum_benefit + 0.5).astype(int)
    result["ben_rel_max"] = relative_to_maximum.clip(0, 1.5)

    medical_deduction = pd.to_numeric(raw["FSMEDDED"], errors="coerce") + (
        pd.to_numeric(engine_deltas["medical_deduction_delta"], errors="coerce")
    )
    shelter_deduction = pd.to_numeric(raw["FSSLTDED"], errors="coerce") + (
        pd.to_numeric(engine_deltas["shelter_deduction_delta"], errors="coerce")
    )
    deduction_components = pd.DataFrame(
        {
            "medical": medical_deduction,
            "dependent_care": pd.to_numeric(raw["FSDEPDED"], errors="coerce"),
            "child_support": pd.to_numeric(raw["FSCSDED"], errors="coerce"),
            "shelter": shelter_deduction,
        },
        index=raw.index,
    )
    result["deduction_components_missing"] = (
        deduction_components.isna().any(axis=1).astype(int)
    )
    result["deduction_count"] = deduction_components.fillna(0).gt(0).sum(axis=1)

    size = raw["CERTHHSZ"].combine_first(raw["FSUSIZE"])
    earned_deduction = pd.to_numeric(raw["FSERNDED"], errors="coerce")
    total_components = deduction_components.assign(earned=earned_deduction)
    result["deductions_missing"] = (
        total_components.isna().any(axis=1) | size.isna()
    ).astype(int)
    total_deduction = total_components.sum(axis=1, min_count=1)
    result["deductions_per_member"] = total_deduction / size.clip(lower=1)

    counterfactual_net_income = pd.to_numeric(
        raw["FSNETINC"], errors="coerce"
    ) + pd.to_numeric(engine_deltas["net_income_delta"], errors="coerce")
    gross_income = pd.to_numeric(raw["FSGRINC"], errors="coerce")
    result["net_share_undefined"] = (
        counterfactual_net_income.isna() | gross_income.isna() | gross_income.le(0)
    ).astype(int)
    result["net_share_of_gross"] = (
        counterfactual_net_income / gross_income.replace(0, np.nan)
    ).clip(0, 2)
    return result


def _weighted_mean(values: np.ndarray | pd.Series, weights: pd.Series) -> float:
    x = np.asarray(values, dtype=float)
    w = weights.to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not valid.any():
        raise ValueError("weighted mean has no finite positive-weight cases")
    return float(np.average(x[valid], weights=w[valid]))


def paired_weighted_bootstrap(
    values: Mapping[str, np.ndarray],
    weights: pd.Series,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[dict[str, dict[str, Any]], dict[str, np.ndarray]]:
    """Bootstrap paired case-level weighted means with a fixed fitted model."""
    if draws <= 0:
        raise ValueError("bootstrap draws must be positive")
    w = weights.to_numpy(dtype=float)
    if not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("bootstrap weights must be finite and positive")
    arrays = {name: np.asarray(value, dtype=float) for name, value in values.items()}
    if any(len(value) != len(w) for value in arrays.values()):
        raise ValueError("bootstrap values must match the case count")
    if any(not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("bootstrap values must be finite")

    rng = np.random.default_rng(seed)
    samples = {name: np.empty(draws, dtype=float) for name in arrays}
    chunk_size = min(1_000, draws)
    for start in range(0, draws, chunk_size):
        stop = min(start + chunk_size, draws)
        index = rng.integers(0, len(w), size=(stop - start, len(w)))
        sampled_weights = w[index]
        denominators = sampled_weights.sum(axis=1)
        for name, value in arrays.items():
            samples[name][start:stop] = (sampled_weights * value[index]).sum(
                axis=1
            ) / denominators

    alpha = (1 - CONFIDENCE_LEVEL) / 2
    summaries = {
        name: {
            "estimate": _weighted_mean(value, weights),
            "bootstrap_mean": float(sample.mean()),
            "standard_error": float(sample.std(ddof=1)),
            "confidence_interval": [
                float(np.quantile(sample, alpha)),
                float(np.quantile(sample, 1 - alpha)),
            ],
        }
        for (name, value), sample in zip(arrays.items(), samples.values(), strict=True)
    }
    return summaries, samples


def _expected_cost_for_level_shifts(
    baseline_rates: np.ndarray, issuance: float, shifts_pp: np.ndarray
) -> np.ndarray:
    """Price many level shifts against one empirical observed-bootstrap CDF."""
    rates = np.sort(np.asarray(baseline_rates, dtype=float))
    shifts = np.asarray(shifts_pp, dtype=float)
    n = len(rates)
    below_6 = np.searchsorted(rates, 6 - shifts, side="left")
    below_8 = np.searchsorted(rates, 8 - shifts, side="left")
    below_10 = np.searchsorted(rates, 10 - shifts, side="left")
    expected_share = (
        5 * (below_8 - below_6) + 10 * (below_10 - below_8) + 15 * (n - below_10)
    ) / n
    return expected_share / 100 * issuance


def _qc_cases(raw: pd.DataFrame) -> list[QcCase]:
    official = train_error_model.official_error_label(raw)
    cases: list[QcCase] = []
    for index, row in raw.iterrows():
        elements = frozenset(
            int(row[f"ELEMENT{slot}"])
            for slot in train_error_model.FINDING_SLOTS
            if pd.notna(row[f"ELEMENT{slot}"])
        )
        error = float(row["AMTERR"]) if int(official.loc[index]) else 0.0
        cases.append(
            QcCase(
                weight=float(row["HWGT"]),
                issuance=float(row["RAWBEN"]),
                error=error,
                elements=elements,
            )
        )
    return cases


def _accounting_bound(
    raw: pd.DataFrame,
    official_rate: float,
    issuance: float,
) -> tuple[dict[str, Any], np.ndarray, dict[str, Any]]:
    cases = _qc_cases(raw)
    baseline_rates = simulate(
        cases,
        official_rate,
        draws=COST_SHARE_DRAWS,
        rng=np.random.default_rng(COST_SHARE_SEED),
    )
    adoption_rates = simulate(
        cases,
        official_rate,
        suppressed=LEVERS["smd"],
        effectiveness=1.0,
        draws=COST_SHARE_DRAWS,
        rng=np.random.default_rng(COST_SHARE_SEED),
    )
    baseline = summarize(baseline_rates, issuance)
    adoption = summarize(adoption_rates, issuance)

    w = np.array([case.weight for case in cases])
    issued = np.array([case.issuance for case in cases])
    observed_error = np.array([case.error for case in cases])
    adoption_error = np.array(
        [lever_error(case.error, case.elements, LEVERS["smd"], 1.0) for case in cases]
    )
    observed_point = 100 * np.sum(w * observed_error) / np.sum(w * issued)
    adoption_point = 100 * np.sum(w * adoption_error) / np.sum(w * issued)
    adoption_shift = float(adoption_point - observed_point)
    reverse_shift = -adoption_shift
    reverse = summarize(baseline_rates + reverse_shift, issuance)

    accounting = {
        "method": (
            "v1 equal attribution across each case's unique finding elements; "
            "100% suppression of element 365"
        ),
        "medical_element": 365,
        "official_error_cases_with_medical_element": sum(
            case.error > 0 and 365 in case.elements for case in cases
        ),
        "weighted_attributed_error_dollars": float(
            np.sum(w * (observed_error - adoption_error))
        ),
        "smd_adoption": {
            "sample_payment_error_rate_delta_pp": adoption_shift,
            "expected_cost_share": adoption,
            "expected_cost_share_delta": (
                adoption["expected_cost_share"] - baseline["expected_cost_share"]
            ),
        },
        "direction_reversed_smd_off_level_reference": {
            "explanation": (
                "Mechanical sign reversal of the accounting sample-rate shift "
                "applied to the unchanged observed bootstrap; not an existing "
                "one-sided simulator lever output"
            ),
            "level_shift_pp": reverse_shift,
            "expected_cost_share": reverse,
            "expected_cost_share_delta": (
                reverse["expected_cost_share"] - baseline["expected_cost_share"]
            ),
        },
    }
    return accounting, baseline_rates, baseline


def _package_versions() -> dict[str, str]:
    names = ["numpy", "pandas", "pyreadstat", "scikit-learn", "scipy"]
    return {
        "python": sys.version.split()[0],
        **{name: importlib.metadata.version(name) for name in names},
    }


def _extract_adoption_contrasts(data: pd.DataFrame) -> dict[str, dict[str, float]]:
    result = train_error_model.medical_descriptive_contrasts(
        data, train_error_model.load_smd_amounts()
    )
    populations = result["populations"]
    return {
        state: {
            "claimant_conditioned_pp": float(
                populations["claimant_conditioned"][state]["descriptive_contrast_pp"]
            ),
            "stable_all_elderly_disabled_pp": float(
                populations["all_elderly_disabled"][state]["descriptive_contrast_pp"]
            ),
        }
        for state in ("AZ", "KY", "CA")
    }


def _scenario_fingerprints(inputs: Round1bInputs) -> dict[str, str]:
    return {
        scenario: str(
            inputs.manifests[f"smd-off/{scenario}/manifest.json"][
                "scenario_fingerprint"
            ]
        )
        for scenario in SCENARIOS
    }


def run_analysis(
    input_root: Path = DEFAULT_INPUT_ROOT,
    *,
    bootstrap_draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, Any]:
    """Run the deterministic end-to-end counterfactual analysis."""
    inputs = load_round1b_inputs(input_root)
    raw = load_joined_colorado_cases(inputs)
    registry = train_error_model.load_smd_registry()
    baseline_features = train_error_model.build_features(raw, registry[FISCAL_YEAR])
    if not baseline_features["med_doc_required"].eq(0).all():
        raise ValueError("Colorado SMD-on did not zero the documentation proxy")

    model_data = hurdle_deviation_model.assemble()
    primary_train = model_data.loc[
        model_data["year"].isin(train_error_model.YEARS_TRAIN)
    ]
    fy2024 = model_data.loc[model_data["year"].eq(FISCAL_YEAR)]
    burden_columns = (
        train_error_model.COVARIATES + train_error_model.BURDEN_INTERMEDIATES
    )
    full_columns = train_error_model.COVARIATES + train_error_model.INTERMEDIATES
    _, _, covariate_metrics = train_error_model.fit_score(
        primary_train,
        fy2024,
        train_error_model.COVARIATES,
        "counterfactual covariates",
    )
    _, _, burden_metrics = train_error_model.fit_score(
        primary_train,
        fy2024,
        burden_columns,
        "counterfactual + burden intermediates",
    )
    official_model, _, full_metrics = train_error_model.fit_score(
        primary_train,
        fy2024,
        full_columns,
        "counterfactual + burdens",
    )
    auc_lift = burden_metrics["roc_auc"] - covariate_metrics["roc_auc"]

    hurdle_features = hurdle_deviation_model._feature_columns(model_data)
    hurdle = hurdle_deviation_model.fit_hurdle(primary_train, hurdle_features)
    baseline_direct_probability = official_model.predict_proba(
        baseline_features[full_columns]
    )[:, 1]
    baseline_hurdle = hurdle_deviation_model.predict_hurdle(
        hurdle, baseline_features, hurdle_features
    )

    weights = baseline_features["w"]
    weight_total = float(weights.sum())
    issuance = float(
        np.sum(weights.to_numpy(dtype=float) * raw["RAWBEN"].to_numpy(dtype=float))
    )
    accounting_payload = _read_json(ACCOUNTING_SOURCE)
    source_co = accounting_payload[JURISDICTION]
    official_rate = float(source_co["official_rate"])
    if not np.isclose(issuance, float(source_co["issuance"]), atol=0.01):
        raise ValueError(
            "SAV issuance does not match the corrected accounting artifact"
        )

    scenario_work: dict[str, dict[str, Any]] = {}
    bootstrap_values: dict[str, np.ndarray] = {}
    for scenario in SCENARIOS:
        rows = inputs.cases[scenario]
        deltas = _engine_delta_frame(rows, raw.index)
        counterfactual_features = apply_smd_off_features(raw, baseline_features, deltas)
        direct_probability = official_model.predict_proba(
            counterfactual_features[full_columns]
        )[:, 1]
        predicted_hurdle = hurdle_deviation_model.predict_hurdle(
            hurdle, counterfactual_features, hurdle_features
        )
        direct_delta = direct_probability - baseline_direct_probability
        hurdle_crossing_delta = (
            predicted_hurdle["p1"].to_numpy() * predicted_hurdle["p2"].to_numpy()
            - baseline_hurdle["p1"].to_numpy() * baseline_hurdle["p2"].to_numpy()
        )
        error_dollar_delta = (
            predicted_hurdle["pred_err_dollars"].to_numpy()
            - baseline_hurdle["pred_err_dollars"].to_numpy()
        )
        bootstrap_values[f"{scenario}_direct_pp"] = 100 * direct_delta
        bootstrap_values[f"{scenario}_error_dollars"] = error_dollar_delta

        doc_flip = (
            counterfactual_features["med_doc_required"]
            - baseline_features["med_doc_required"]
        )
        engine_med_demo = pd.Series(
            [int(row["source_facts"]["MED_DED_DEMO"]) for row in rows],
            index=raw.index,
        )
        target = counterfactual_features["med_doc_required"].eq(1)
        if not engine_med_demo.eq(target.astype(int)).all():
            raise ValueError(f"{scenario}: doc-flip predicate differs from engine demo")

        benefit_delta = deltas["benefit_delta"].to_numpy(dtype=float)
        error_dollar_total = float(
            np.sum(weights.to_numpy(dtype=float) * error_dollar_delta)
        )
        scenario_work[scenario] = {
            "assumption_statement": str(rows[0]["assumption_statement"]),
            "engine_accounting": {
                "benefit_changed_cases": int(np.count_nonzero(benefit_delta)),
                "weighted_mean_benefit_delta_per_case_month": _weighted_mean(
                    benefit_delta, weights
                ),
                "weighted_benefit_delta_total": float(
                    np.sum(weights.to_numpy(dtype=float) * benefit_delta)
                ),
                "medical_deduction_changed_cases": int(
                    deltas["medical_deduction_delta"].ne(0).sum()
                ),
                "shelter_deduction_changed_cases": int(
                    deltas["shelter_deduction_delta"].ne(0).sum()
                ),
                "net_income_changed_cases": int(deltas["net_income_delta"].ne(0).sum()),
            },
            "feature_changes": {
                "med_doc_required_0_to_1_cases": int(doc_flip.eq(1).sum()),
                "med_doc_required_other_change_cases": int(
                    (~doc_flip.isin([0, 1])).sum()
                ),
                "formula_benefit_changed_cases": int(
                    deltas["benefit_delta"].ne(0).sum()
                ),
                "medical_deduction_changed_cases": int(
                    deltas["medical_deduction_delta"].ne(0).sum()
                ),
                "shelter_deduction_changed_cases": int(
                    deltas["shelter_deduction_delta"].ne(0).sum()
                ),
                "net_income_changed_cases": int(deltas["net_income_delta"].ne(0).sum()),
            },
            "direct_official_error_classifier": {
                "probability_kind": (
                    "raw HistGradientBoostingClassifier class probability; "
                    "the committed direct classifier has no calibrator"
                ),
                "baseline_weighted_expected_crossing_rate": _weighted_mean(
                    baseline_direct_probability, weights
                ),
                "counterfactual_weighted_expected_crossing_rate": _weighted_mean(
                    direct_probability, weights
                ),
                "weighted_delta_pp": 100 * _weighted_mean(direct_delta, weights),
            },
            "hurdle_expected_error_dollars": {
                "estimator": (
                    "separate committed calibrated p1 * p2 * predicted magnitude; "
                    "primary through-FY2023 unfactored model"
                ),
                "baseline_weighted_mean_per_case_month": _weighted_mean(
                    baseline_hurdle["pred_err_dollars"], weights
                ),
                "counterfactual_weighted_mean_per_case_month": _weighted_mean(
                    predicted_hurdle["pred_err_dollars"], weights
                ),
                "weighted_mean_delta_per_case_month": _weighted_mean(
                    error_dollar_delta, weights
                ),
                "weighted_total_delta": error_dollar_total,
                "payment_error_dollar_rate_delta_pp": (
                    100 * error_dollar_total / issuance
                ),
                "hurdle_crossing_probability_delta_pp": (
                    100 * _weighted_mean(hurdle_crossing_delta, weights)
                ),
            },
        }

    bootstrap, bootstrap_samples = paired_weighted_bootstrap(
        bootstrap_values,
        weights,
        draws=bootstrap_draws,
        seed=BOOTSTRAP_SEED,
    )
    accounting, baseline_rates, baseline_cost = _accounting_bound(
        raw, official_rate, issuance
    )
    baseline_expected_cost = float(baseline_cost["expected_cost_share"])

    scenarios: dict[str, Any] = {}
    alpha = (1 - CONFIDENCE_LEVEL) / 2
    for scenario in SCENARIOS:
        record = scenario_work[scenario]
        direct_uncertainty = bootstrap[f"{scenario}_direct_pp"]
        dollar_uncertainty = bootstrap[f"{scenario}_error_dollars"]
        direct_delta_pp = float(
            record["direct_official_error_classifier"]["weighted_delta_pp"]
        )
        shifted_rates = baseline_rates + direct_delta_pp
        shifted_summary = summarize(shifted_rates, issuance)
        cost_samples = _expected_cost_for_level_shifts(
            baseline_rates,
            issuance,
            bootstrap_samples[f"{scenario}_direct_pp"],
        )
        cost_delta_samples = cost_samples - baseline_expected_cost

        dollar_ci = dollar_uncertainty["confidence_interval"]
        record["direct_official_error_classifier"]["uncertainty"] = direct_uncertainty
        record["hurdle_expected_error_dollars"]["uncertainty"] = {
            **dollar_uncertainty,
            "weighted_total_confidence_interval": [
                float(dollar_ci[0] * weight_total),
                float(dollar_ci[1] * weight_total),
            ],
            "payment_error_dollar_rate_delta_pp_confidence_interval": [
                float(100 * dollar_ci[0] * weight_total / issuance),
                float(100 * dollar_ci[1] * weight_total / issuance),
            ],
        }
        record["fy2028_cost_share_translation"] = {
            "shifted_official_level_pct": official_rate + direct_delta_pp,
            "observed_bootstrap_summary": shifted_summary,
            "expected_cost_share_delta": (
                shifted_summary["expected_cost_share"] - baseline_expected_cost
            ),
            "conditional_expected_cost_share_delta_bootstrap_mean": float(
                cost_delta_samples.mean()
            ),
            "conditional_expected_cost_share_delta_confidence_interval": [
                float(np.quantile(cost_delta_samples, alpha)),
                float(np.quantile(cost_delta_samples, 1 - alpha)),
            ],
        }
        scenarios[scenario] = record

    target_mask = baseline_features["medical_expense_above_floor"].eq(1) & (
        baseline_features["elderly_or_disabled"].eq(1)
    )
    result: dict[str, Any] = {
        "schema": "snap_qc_sim.counterfactual_co_smd.v1",
        "schema_version": 1,
        "generated_by": "analysis/counterfactual_join.py",
        "jurisdiction": JURISDICTION,
        "fiscal_year": FISCAL_YEAR,
        "counterfactual": "Colorado standard medical deduction off",
        "delta_direction": "SMD-off minus SMD-on",
        "case_universe": {
            "filter": "CASE == 1",
            "cases": len(raw),
            "weighted_population": weight_total,
            "issuance": issuance,
        },
        "feature_construction": {
            "documentation_definition": (
                "FSMEDEXP > 35 and elderly_or_disabled and SMD does not apply"
            ),
            "documentation_flip_cases": int(target_mask.sum()),
            "documentation_flip_weight": float(weights.loc[target_mask].sum()),
            "documentation_flip_weight_share": float(
                weights.loc[target_mask].sum() / weight_total
            ),
            "engine_delta_mapping": {
                "benefit": (
                    "FSBEN + engine benefit delta -> formula_benefit and "
                    "benefit-position features"
                ),
                "medical_and_shelter_deductions": (
                    "FSMEDDED/FSSLTDED + engine deltas -> deduction_count and "
                    "deductions_per_member"
                ),
                "net_income": (
                    "FSNETINC + engine net-income delta -> net_share_of_gross"
                ),
            },
            "baseline_anchor_reason": (
                "Use QC baselines plus engine deltas to avoid importing 11 unrelated "
                "absolute benefit divergences and one unrelated net-income divergence"
            ),
        },
        "model_diagnostics": {
            "direct_classifier_covariates_roc_auc": covariate_metrics["roc_auc"],
            "direct_classifier_with_intermediates_roc_auc": full_metrics["roc_auc"],
            "burden_intermediate_roc_auc_lift": auc_lift,
            "burden_intermediate_roc_auc_lift_rounded_3": round(auc_lift, 3),
            "descriptive_smd_adoption_contrasts_pp": _extract_adoption_contrasts(
                model_data
            ),
        },
        "uncertainty": {
            "method": (
                "paired nonparametric i.i.d. bootstrap of Colorado FY2024 QC cases; "
                "sample rows with replacement, retain HWGT inside each weighted "
                "mean, and use percentile intervals"
            ),
            "draws": bootstrap_draws,
            "seed": BOOTSTRAP_SEED,
            "confidence_level": CONFIDENCE_LEVEL,
            "conditional_on_fitted_models": True,
            "omitted_uncertainty": (
                "training-fit, model-specification, causal-identification, censored-"
                "expense imputation, official re-review, and actual stratified/monthly "
                "QC sampling-design uncertainty"
            ),
        },
        "fy2028_cost_share": {
            "official_fy2024_rate_pct": official_rate,
            "fy2024_issuance": issuance,
            "interpretation": (
                "FY2028 statutory tiers applied to FY2024 issuance; illustration, "
                "not a FY2028 forecast"
            ),
            "observed_mode_bootstrap": {
                "method": (
                    "snap_qc_sim.simulate observed mode, official-rate centered; "
                    "model scenarios add the direct crossing-rate delta as a level shift"
                ),
                "seed": COST_SHARE_SEED,
                "draws": COST_SHARE_DRAWS,
                "baseline": baseline_cost,
            },
            "accounting_bound_smd": accounting,
        },
        "scenarios": scenarios,
        "interpretation": {
            "causal": False,
            "headline": (
                "The SMD-off deltas are small, uncertainty-dominated model-implied "
                "associations, not causal effects. Near-zero results and the gap from "
                "the accounting bound are findings."
            ),
            "counterintuitive_sign": (
                "The fitted models imply lower error under SMD-off even though the "
                "documentation proxy rises. Gradient-boosted trees impose neither "
                "causal nor monotonic structure, so this sign is not evidence that "
                "documentation requirements reduce errors."
            ),
            "cost_share_bridge": (
                "The direct crossing rate is a weighted share of cases, whereas the "
                "official payment error rate is error dollars divided by issuance. "
                "Adding one to the other is the requested mechanical level-shift "
                "translation, not an identity between like-denominator rates."
            ),
        },
        "provenance": {
            "round_1b_root": str(Path(input_root).expanduser().resolve()),
            "round_1b_input_sha256": inputs.sha256,
            "round_1b_scenario_fingerprints": _scenario_fingerprints(inputs),
            "engine_pins": inputs.manifests["baseline/manifest.json"]["pins"],
            "nominal_engine_period": inputs.manifests["baseline/manifest.json"][
                "nominal_engine_period"
            ],
            "model_pipeline": hurdle_deviation_model._provenance(),
            "package_versions": _package_versions(),
            "implementation_sha256": {
                "analysis/counterfactual_join.py": _sha256(Path(__file__)),
                "analysis/train_error_model.py": _sha256(
                    ANALYSIS_DIR / "train_error_model.py"
                ),
                "analysis/hurdle_deviation_model.py": _sha256(
                    ANALYSIS_DIR / "hurdle_deviation_model.py"
                ),
                "snap_qc_sim/simulate.py": _sha256(
                    REPO_ROOT / "snap_qc_sim" / "simulate.py"
                ),
                str(ACCOUNTING_SOURCE.relative_to(REPO_ROOT)): _sha256(
                    ACCOUNTING_SOURCE
                ),
            },
            "determinism": {
                "thread_environment": {
                    name: os.environ[name]
                    for name in (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "VECLIB_MAXIMUM_THREADS",
                        "NUMEXPR_NUM_THREADS",
                    )
                },
                "serialization": (
                    "UTF-8; LF; terminal newline; stable insertion order; no timestamp"
                ),
            },
        },
    }
    validate_artifact(result)
    return result


def _require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{context} must be an object")
    return value


def validate_artifact(payload: Mapping[str, Any]) -> None:
    """Validate the committed counterfactual artifact's public schema."""
    required = {
        "schema",
        "schema_version",
        "jurisdiction",
        "fiscal_year",
        "feature_construction",
        "model_diagnostics",
        "uncertainty",
        "fy2028_cost_share",
        "scenarios",
        "interpretation",
        "provenance",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"counterfactual artifact is missing keys: {missing}")
    if payload["schema"] != "snap_qc_sim.counterfactual_co_smd.v1":
        raise ValueError("unexpected counterfactual schema")
    if payload["schema_version"] != 1:
        raise ValueError("unexpected counterfactual schema version")
    if payload["jurisdiction"] != JURISDICTION or payload["fiscal_year"] != 2024:
        raise ValueError("counterfactual artifact has the wrong jurisdiction/year")

    scenarios = _require_mapping(payload["scenarios"], context="scenarios")
    if tuple(scenarios) != SCENARIOS:
        raise ValueError("counterfactual scenarios must be floor, point, ceiling")
    for scenario in SCENARIOS:
        record = _require_mapping(scenarios[scenario], context=scenario)
        for key in (
            "engine_accounting",
            "feature_changes",
            "direct_official_error_classifier",
            "hurdle_expected_error_dollars",
            "fy2028_cost_share_translation",
        ):
            if key not in record:
                raise ValueError(f"{scenario} is missing {key}")
        direct = _require_mapping(
            record["direct_official_error_classifier"], context=f"{scenario} direct"
        )
        if "uncertainty" not in direct or "weighted_delta_pp" not in direct:
            raise ValueError(f"{scenario} direct result is incomplete")

    interpretation = _require_mapping(
        payload["interpretation"], context="interpretation"
    )
    if interpretation.get("causal") is not False:
        raise ValueError("artifact must explicitly state that results are not causal")
    uncertainty = _require_mapping(payload["uncertainty"], context="uncertainty")
    if uncertainty.get("conditional_on_fitted_models") is not True:
        raise ValueError("artifact must label fixed-fit conditional uncertainty")

    provenance = _require_mapping(payload["provenance"], context="provenance")
    hashes = _require_mapping(
        provenance.get("round_1b_input_sha256"), context="round-1b hashes"
    )
    if len(hashes) != 9 or any(
        not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value)
        for value in hashes.values()
    ):
        raise ValueError("artifact must hash all nine round-1b inputs")


def serialize_json(payload: Mapping[str, Any]) -> bytes:
    """Return the canonical checked-in JSON bytes."""
    validate_artifact(payload)
    return (
        json.dumps(payload, indent=2, allow_nan=False, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _signed(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


def _money(value: float, digits: int = 2) -> str:
    sign = "−" if value < 0 else "+" if value > 0 else ""
    return f"{sign}${abs(value):,.{digits}f}"


def _millions(value: float) -> str:
    return _money(value / 1_000_000, 3) + "M"


def _interval(values: Sequence[float], formatter: Any) -> str:
    return f"[{formatter(float(values[0]))}, {formatter(float(values[1]))}]"


def render_document(payload: Mapping[str, Any]) -> str:
    """Render the generated FINDINGS-style counterfactual Markdown."""
    validate_artifact(payload)
    feature = payload["feature_construction"]
    diagnostics = payload["model_diagnostics"]
    cost = payload["fy2028_cost_share"]
    accounting = cost["accounting_bound_smd"]
    reverse = accounting["direction_reversed_smd_off_level_reference"]
    adoption = accounting["smd_adoption"]
    scenarios = payload["scenarios"]

    lines = [
        "<!-- Generated by analysis/counterfactual_join.py; do not edit manually. -->",
        "",
        "# Colorado SMD-off counterfactual join",
        "",
        (
            "The corrected error models imply small decreases—not increases—in "
            "Colorado's official-error crossing score when the standard medical "
            "deduction is turned off. These are uncertainty-dominated model-implied "
            "associations, not causal effects. The counterintuitive sign and the gap "
            "from the accounting bound are the findings."
        ),
        "",
        "## Findings",
        "",
        (
            "All three scenarios flip `med_doc_required` from 0 to 1 for exactly "
            f"{int(feature['documentation_flip_cases'])} of 856 cases "
            f"({100 * float(feature['documentation_flip_weight_share']):.2f}% of "
            "Colorado QC weight). Floor, point, and ceiling then apply their own "
            "engine deltas to the medical and shelter deductions, net income, and "
            "formula benefit."
        ),
        "",
        (
            "| Scenario | Engine benefit Δ per case-month | Direct crossing Δ "
            "(95% conditional interval) | Hurdle expected-error-dollar Δ per "
            "case-month (95% conditional interval) | FY2028-rule expected "
            "cost-share Δ (95% conditional interval) |"
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for scenario in SCENARIOS:
        record = scenarios[scenario]
        engine = record["engine_accounting"]
        direct = record["direct_official_error_classifier"]
        direct_ci = direct["uncertainty"]["confidence_interval"]
        hurdle = record["hurdle_expected_error_dollars"]
        hurdle_ci = hurdle["uncertainty"]["confidence_interval"]
        translated = record["fy2028_cost_share_translation"]
        cost_ci = translated[
            "conditional_expected_cost_share_delta_confidence_interval"
        ]
        lines.append(
            f"| {scenario.capitalize()} | "
            f"{_money(engine['weighted_mean_benefit_delta_per_case_month'])} | "
            f"{_signed(direct['weighted_delta_pp'])}pp "
            f"{_interval(direct_ci, lambda x: _signed(x) + 'pp')} | "
            f"{_money(hurdle['weighted_mean_delta_per_case_month'])} "
            f"{_interval(hurdle_ci, _money)} | "
            f"{_millions(translated['expected_cost_share_delta'])} "
            f"{_interval(cost_ci, _millions)} |"
        )

    lines.extend(
        [
            "",
            (
                "The model-implied cost changes are compared with a mechanical "
                "SMD-off-direction accounting reference of "
                f"{_signed(reverse['level_shift_pp'])}pp and "
                f"{_millions(reverse['expected_cost_share_delta'])}. The reference "
                "reverses the sign of the v1 SMD-suppression rate shift while keeping "
                "the observed bootstrap unchanged; it is not an existing one-sided "
                "lever output."
            ),
            "",
            "## Accounting-bound comparison",
            "",
            "| Quantity | Rate shift | Expected FY2028-rule cost-share change |",
            "|---|---:|---:|",
            (
                "| v1 SMD adoption / 100% element-365 suppression | "
                f"{_signed(adoption['sample_payment_error_rate_delta_pp'])}pp | "
                f"{_millions(adoption['expected_cost_share_delta'])} |"
            ),
            (
                "| Direction-reversed SMD-off level reference | "
                f"{_signed(reverse['level_shift_pp'])}pp | "
                f"{_millions(reverse['expected_cost_share_delta'])} |"
            ),
            "",
            (
                "The v1 bound attributes each official-error case equally across its "
                "unique finding elements. Six Colorado official-error cases carry "
                "medical element 365. The adoption lever changes both the bootstrap "
                "level and its case-level error distribution; the reversed reference "
                "changes only the level, so the two dollar effects are not exact "
                "opposites near a tier boundary."
            ),
            "",
            "## Interpretation boundary",
            "",
            (
                "The burden-intermediate specification carries "
                f"{float(diagnostics['burden_intermediate_roc_auc_lift']):+.4f} "
                "ROC-AUC discrimination, which rounds to +0.006. That small "
                "predictive difference does not identify the effect of documentation "
                "rules. The direct classifier is uncalibrated; the hurdle-dollar "
                "estimate uses its own separately calibrated probability stages and "
                "magnitude model."
            ),
            "",
            (
                "The negative SMD-off estimates do not show that documentation "
                "requirements reduce errors. Gradient-boosted trees impose neither "
                "causal nor monotonic structure, and correlated state, household, and "
                "benefit-position patterns can determine the sign. Floor and point "
                "also need not rank monotonically."
            ),
            "",
            (
                "The descriptive SMD-adoption contrasts provide the calibration "
                "reference for how little the observed data support large effects:"
            ),
            "",
            "| State | Claimant-conditioned contrast | Stable all-E/D contrast |",
            "|---|---:|---:|",
        ]
    )
    contrasts = diagnostics["descriptive_smd_adoption_contrasts_pp"]
    for state in ("AZ", "KY", "CA"):
        cell = contrasts[state]
        lines.append(
            f"| {state} | {_signed(cell['claimant_conditioned_pp'], 2)}pp | "
            f"{_signed(cell['stable_all_elderly_disabled_pp'], 2)}pp |"
        )

    lines.extend(
        [
            "",
            (
                "These adoption contrasts and the counterfactual predictions are "
                "descriptive/model-implied associations, not causal estimates."
            ),
            "",
            "## Uncertainty and cost-share translation",
            "",
            (
                f"The conditional intervals use {int(payload['uncertainty']['draws']):,} "
                "paired i.i.d. case bootstrap draws (seed "
                f"{int(payload['uncertainty']['seed'])}). Each draw resamples the 856 "
                "Colorado QC cases with replacement and retains `HWGT` inside the "
                "weighted ratio. The intervals hold the fitted models and engine "
                "inputs fixed. They omit training-fit, specification, causal, "
                "censoring-imputation, official re-review, and actual QC design "
                "uncertainty, so they understate total uncertainty."
            ),
            "",
            (
                f"The tier translation uses {int(cost['observed_mode_bootstrap']['draws']):,} "
                "observed-mode draws at seed "
                f"{int(cost['observed_mode_bootstrap']['seed'])}, the official "
                f"{float(cost['official_fy2024_rate_pct']):.2f}% level, and FY2024 "
                f"issuance of ${float(cost['fy2024_issuance']):,.0f}. It applies the "
                "FY2028 tiers as an illustration, not a FY2028 forecast."
            ),
            "",
            (
                "The direct crossing rate is a weighted share of cases, while the "
                "official payment error rate divides error dollars by issuance. The "
                "requested `official rate + Δ` step is therefore a mechanical "
                "level-shift bridge, not a like-denominator identity. The JSON also "
                "reports the hurdle model's dollar-rate equivalents, but the tier "
                "translation follows the requested direct crossing delta."
            ),
            "",
            "## Provenance",
            "",
            (
                "The script hashes all nine round-1b inputs before fitting. The "
                "round-1b manifests pin engine `"
                f"{payload['provenance']['engine_pins']['engine']['commit'][:12]}`, "
                "RuleSpec `"
                f"{payload['provenance']['engine_pins']['rulespec']['commit'][:12]}`, "
                "and harness `"
                f"{payload['provenance']['engine_pins']['harness']['commit'][:12]}`. "
                "The nominal engine period is `"
                f"{payload['provenance']['nominal_engine_period']}` with the FY2024 "
                "overlay."
            ),
            "",
            "| Round-1b input | SHA-256 |",
            "|---|---|",
        ]
    )
    for name, digest in payload["provenance"]["round_1b_input_sha256"].items():
        lines.append(f"| `{name}` | `{digest}` |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    payload: Mapping[str, Any], json_output: Path, document_output: Path
) -> tuple[str, str]:
    """Write JSON and Markdown and return their SHA-256 digests."""
    json_bytes = serialize_json(payload)
    document_bytes = render_document(payload).encode("utf-8")
    json_output.parent.mkdir(parents=True, exist_ok=True)
    document_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_bytes(json_bytes)
    document_output.write_bytes(document_bytes)
    return hashlib.sha256(json_bytes).hexdigest(), hashlib.sha256(
        document_bytes
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--document-output", type=Path, default=DEFAULT_DOCUMENT_OUTPUT)
    args = parser.parse_args()

    payload = run_analysis(args.input_root)
    json_hash, document_hash = write_outputs(
        payload, args.json_output, args.document_output
    )
    print("scenario  crossing delta (pp)  expected cost-share delta")
    for scenario in SCENARIOS:
        record = payload["scenarios"][scenario]
        crossing = record["direct_official_error_classifier"]["weighted_delta_pp"]
        cost_delta = record["fy2028_cost_share_translation"][
            "expected_cost_share_delta"
        ]
        print(f"{scenario:<8} {crossing:+.6f}             ${cost_delta:+,.2f}")
    print(f"wrote {args.json_output} sha256={json_hash}")
    print(f"wrote {args.document_output} sha256={document_hash}")


if __name__ == "__main__":
    main()
