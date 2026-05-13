from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "pressure_bar",
    "temperature_c",
    "flow_nm3h",
    "tank_level_pct",
    "electrolyzer_current_a",
    "valve_state",
    "compressor_state",
    "network_latency_ms",
    "packet_rate_pps",
    "command_rate_per_min",
]

SCORING = {
    "accuracy": "accuracy",
    "precision": "precision",
    "recall": "recall",
    "f1": "f1",
    "roc_auc": "roc_auc",
    "average_precision": "average_precision",
}


def score_binary(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray | None = None) -> Dict[str, float]:
    metrics: Dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        metrics["average_precision"] = float(average_precision_score(y_true, y_prob))
    return metrics


def supervised_models(random_state: int = 42) -> Dict[str, Pipeline]:
    numeric_transformer = Pipeline(steps=[("scaler", StandardScaler())])
    preprocess = ColumnTransformer(transformers=[("num", numeric_transformer, FEATURES)])

    return {
        "logistic_regression": Pipeline(
            steps=[
                ("preprocess", preprocess),
                (
                    "model",
                    LogisticRegression(max_iter=2500, class_weight="balanced", random_state=random_state),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("preprocess", "passthrough"),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=220,
                        max_depth=None,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def evaluate_cross_validation(X: pd.DataFrame, y: np.ndarray, output_dir: Path, random_state: int) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=random_state)
    for name, pipeline in supervised_models(random_state=random_state).items():
        cv_result = cross_validate(pipeline, X, y, cv=cv, scoring=SCORING, n_jobs=1, error_score="raise")
        row: dict[str, float | str] = {"model": name}
        for metric_name in SCORING:
            values = cv_result[f"test_{metric_name}"]
            row[f"{metric_name}_mean"] = float(np.mean(values))
            row[f"{metric_name}_std"] = float(np.std(values, ddof=1))
        rows.append(row)
    cv_df = pd.DataFrame(rows).sort_values(by="f1_mean", ascending=False)
    cv_df.to_csv(output_dir / "cross_validation_metrics.csv", index=False)
    return cv_df


def build_per_attack_recall(test_df: pd.DataFrame, y_pred: np.ndarray, output_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    observed_types = sorted(test_df.loc[test_df["attack_label"] == 1, "attack_type"].unique())
    for attack_type in observed_types:
        mask = test_df["attack_type"].to_numpy() == attack_type
        total = int(mask.sum())
        detected = int(y_pred[mask].sum())
        rows.append(
            {
                "attack_type": attack_type,
                "attack_instances": total,
                "detected_instances": detected,
                "recall": float(detected / total) if total else float("nan"),
            }
        )
    out = pd.DataFrame(rows).sort_values(by="recall", ascending=True)
    out.to_csv(output_dir / "per_attack_recall.csv", index=False)
    return out


def save_feature_importance(best_pipeline: Pipeline, X_test: pd.DataFrame, y_test: np.ndarray, output_dir: Path, random_state: int) -> pd.DataFrame:
    perm = permutation_importance(
        best_pipeline,
        X_test,
        y_test,
        scoring="f1",
        n_repeats=6,
        random_state=random_state,
        n_jobs=1,
    )
    imp_df = pd.DataFrame(
        {
            "feature": FEATURES,
            "importance_mean": perm.importances_mean,
            "importance_std": perm.importances_std,
        }
    ).sort_values(by="importance_mean", ascending=False)
    imp_df.to_csv(output_dir / "feature_importance.csv", index=False)

    fig = plt.figure(figsize=(8.0, 5.6))
    plot_df = imp_df.sort_values(by="importance_mean", ascending=True)
    plt.barh(plot_df["feature"], plot_df["importance_mean"], xerr=plot_df["importance_std"])
    plt.xlabel("Mean decrease in F1 after permutation")
    plt.ylabel("Feature")
    plt.title("Permutation Feature Importance - Best Supervised Model")
    plt.tight_layout()
    fig.savefig(output_dir / "feature_importance.png", dpi=180)
    plt.close(fig)
    return imp_df


def save_attack_timeline(df: pd.DataFrame, output_dir: Path) -> None:
    fig = plt.figure(figsize=(9.0, 3.8))
    plt.plot(df["timestamp_index"], df["attack_label"])
    plt.ylim(-0.08, 1.08)
    plt.xlabel("Synthetic time index")
    plt.ylabel("Attack label")
    plt.title("Injected Attack Windows in the Synthetic Dataset")
    plt.tight_layout()
    fig.savefig(output_dir / "attack_timeline.png", dpi=180)
    plt.close(fig)


def train_and_evaluate(df: pd.DataFrame, output_dir: Path, random_state: int = 42) -> Dict[str, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    X = df[FEATURES].copy()
    y = df["attack_label"].astype(int).to_numpy()

    # Preserve rows for per-attack-type error analysis after splitting.
    train_df, test_df = train_test_split(df, test_size=0.30, stratify=y, random_state=random_state)
    X_train = train_df[FEATURES].copy()
    X_test = test_df[FEATURES].copy()
    y_train = train_df["attack_label"].astype(int).to_numpy()
    y_test = test_df["attack_label"].astype(int).to_numpy()

    results: Dict[str, Dict[str, float]] = {}
    best_name: str | None = None
    best_f1 = -1.0
    best_pred: np.ndarray | None = None
    best_prob: np.ndarray | None = None
    best_pipeline: Pipeline | None = None

    for name, pipeline in supervised_models(random_state=random_state).items():
        pipeline.fit(X_train, y_train)
        pred = pipeline.predict(X_test)
        prob = pipeline.predict_proba(X_test)[:, 1]
        metrics = score_binary(y_test, pred, prob)
        results[name] = metrics
        if metrics["f1"] > best_f1:
            best_name = name
            best_f1 = metrics["f1"]
            best_pred = pred
            best_prob = prob
            best_pipeline = pipeline

    # Unsupervised model trained on normal-only observations.
    X_train_normal = X_train[y_train == 0]
    iso = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "model",
                IsolationForest(
                    n_estimators=220,
                    contamination=float(y.mean()),
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    iso.fit(X_train_normal)
    iso_raw = iso.predict(X_test)  # -1 anomaly, +1 normal
    iso_pred = (iso_raw == -1).astype(int)
    results["isolation_forest"] = score_binary(y_test, iso_pred, None)

    # Cross-validation supports a stronger estimate than one split alone.
    cv_df = evaluate_cross_validation(X, y, output_dir, random_state=random_state)

    # Save reports and plots for the best supervised model.
    assert best_name is not None and best_pred is not None and best_prob is not None and best_pipeline is not None
    report = classification_report(y_test, best_pred, target_names=["normal", "attack"], zero_division=0)
    (output_dir / "classification_report.txt").write_text(report, encoding="utf-8")

    fig = plt.figure(figsize=(7, 5))
    ConfusionMatrixDisplay.from_predictions(y_test, best_pred, display_labels=["normal", "attack"], ax=plt.gca())
    plt.title(f"Confusion Matrix - {best_name.replace('_', ' ').title()}")
    plt.tight_layout()
    fig.savefig(output_dir / "confusion_matrix.png", dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(7, 5))
    RocCurveDisplay.from_predictions(y_test, best_prob, ax=plt.gca())
    plt.title(f"ROC Curve - {best_name.replace('_', ' ').title()}")
    plt.tight_layout()
    fig.savefig(output_dir / "roc_curve.png", dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(7, 5))
    PrecisionRecallDisplay.from_predictions(y_test, best_prob, ax=plt.gca())
    plt.title(f"Precision-Recall Curve - {best_name.replace('_', ' ').title()}")
    plt.tight_layout()
    fig.savefig(output_dir / "precision_recall_curve.png", dpi=180)
    plt.close(fig)

    per_attack_df = build_per_attack_recall(test_df, best_pred, output_dir)
    importance_df = save_feature_importance(best_pipeline, X_test, y_test, output_dir, random_state=random_state)
    save_attack_timeline(df, output_dir)

    comparison = pd.DataFrame(results).T.sort_values(by="f1", ascending=False)
    comparison.to_csv(output_dir / "model_metrics.csv", index=True)

    payload = {
        "dataset_rows": int(len(df)),
        "attack_prevalence": float(y.mean()),
        "attack_type_counts": {str(k): int(v) for k, v in df["attack_type"].value_counts().items()},
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "best_supervised_model": best_name,
        "results": results,
        "cross_validation_best_model": str(cv_df.iloc[0]["model"]),
        "per_attack_recall": per_attack_df.to_dict(orient="records"),
        "top_features_by_permutation_f1": importance_df.head(5).to_dict(orient="records"),
    }
    (output_dir / "model_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Train cyber anomaly detection models for the hydrogen ICS synthetic dataset.")
    parser.add_argument("--input", type=Path, default=Path("data/hydrogen_ics_synthetic.csv"), help="Input CSV dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Directory for evaluation artefacts.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Dataset not found: {args.input}")
    df = pd.read_csv(args.input)
    required = set(FEATURES + ["attack_label", "attack_type", "timestamp_index"])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Input dataset is missing required columns: {missing}")

    results = train_and_evaluate(df, args.output_dir, random_state=args.seed)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
