"""
Trains and persists the login-risk and bot-detection models.

Run directly to (re)train::

    python -m auth.train

Each model is written to ``auth/models/`` alongside a JSON model card holding
the metrics, the pinned feature order and the training configuration. The
serving code in ``models.py`` asserts the feature order in the card against
``features.py`` at load time, so a schema change that would silently corrupt
scores fails loudly at startup instead.

On evaluation honesty
---------------------
Both models train on synthetic data (see ``datasets.py``), so the reported
numbers describe how well each model recovers its generator - not field
accuracy against a real adversary. Three things are done anyway, because they
are what make the score *usable* rather than merely high:

* **Held-out split.** Metrics come from data the model never saw.

* **Probability calibration.** The gate compares a probability against a
  threshold, so the probability has to mean something. Gradient boosting is
  systematically over-confident out of the box, so the classifier is wrapped in
  isotonic calibration fitted on its own inner split, and the calibration error
  is reported.

* **Threshold chosen against a cost model, not accuracy.** These two errors are
  not equally bad. Blocking a legitimate trader from their own account is a
  worse outcome than asking an attacker for a second factor, so the operating
  point is chosen to hold false positives low rather than to maximise accuracy.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .datasets import generate_bot_dataset, generate_login_dataset
from .features import BOT_FEATURES, LOGIN_FEATURES

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

LOGIN_MODEL_PATH = os.path.join(MODEL_DIR, "login_risk.joblib")
LOGIN_CARD_PATH = os.path.join(MODEL_DIR, "login_risk.card.json")
BOT_MODEL_PATH = os.path.join(MODEL_DIR, "bot_detector.joblib")
BOT_CARD_PATH = os.path.join(MODEL_DIR, "bot_detector.card.json")

RANDOM_STATE = 20260814


# ==============================================================================
# METRICS
# ==============================================================================


def _expected_calibration_error(y_true: np.ndarray, prob: np.ndarray, bins: int = 12) -> float:
    """Mean gap between predicted confidence and observed frequency.

    A model with ECE near 0 means "0.8" genuinely happens about 80% of the
    time, which is the property a probability threshold depends on.
    """
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (prob > lo) & (prob <= hi) if i > 0 else (prob >= lo) & (prob <= hi)
        if not mask.any():
            continue
        total += mask.mean() * abs(y_true[mask].mean() - prob[mask].mean())
    return float(total)


def _threshold_for_max_fpr(y_true: np.ndarray, prob: np.ndarray, max_fpr: float) -> float:
    """Lowest threshold whose false-positive rate stays within *max_fpr*.

    Lower thresholds catch more attacks, so we take the most sensitive setting
    that still respects the false-positive budget.
    """
    best = 0.99
    for t in np.linspace(0.02, 0.98, 97):
        pred = (prob >= t).astype(int)
        neg = y_true == 0
        if not neg.any():
            continue
        fpr = float((pred[neg] == 1).mean())
        if fpr <= max_fpr:
            best = float(t)
            break
    return best


def _metrics_at(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> Dict[str, float]:
    pred = (prob >= threshold).astype(int)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "threshold": round(float(threshold), 4),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
        "accuracy": round((tp + tn) / len(y_true), 4),
    }


# ==============================================================================
# TRAINING
# ==============================================================================


def _fit(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    feature_names: List[str],
    max_fpr: float,
    groups: Sequence[str] | None = None,
) -> Tuple[object, Dict]:
    """Fit a calibrated gradient-boosting classifier and evaluate it.

    When *groups* names the generating scenario per sample, the report includes
    a per-scenario error breakdown. An aggregate AUC hides whether the residual
    error sits in the cases that are ambiguous by construction (fine) or in the
    ones that should be obvious (a bug).
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    from sklearn.model_selection import train_test_split

    Xa = np.asarray(X, dtype=float)
    ya = np.asarray(y, dtype=int)
    ga = np.asarray(groups) if groups is not None else np.array([""] * len(ya))

    X_train, X_test, y_train, y_test, _, g_test = train_test_split(
        Xa, ya, ga, test_size=0.25, random_state=RANDOM_STATE, stratify=ya
    )

    base = HistGradientBoostingClassifier(
        max_iter=280,
        learning_rate=0.06,
        max_depth=6,
        min_samples_leaf=24,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=RANDOM_STATE,
    )

    # Isotonic calibration on inner CV folds. Boosted trees push probabilities
    # toward 0 and 1; without this the risk score would be uninformative
    # anywhere except the extremes, and a threshold would be meaningless.
    model = CalibratedClassifierCV(base, method="isotonic", cv=4)
    model.fit(X_train, y_train)

    prob = model.predict_proba(X_test)[:, 1]

    roc = float(roc_auc_score(y_test, prob))
    pr = float(average_precision_score(y_test, prob))
    brier = float(brier_score_loss(y_test, prob))
    ece = _expected_calibration_error(y_test, prob)

    threshold = _threshold_for_max_fpr(y_test, prob, max_fpr)

    # Permutation importance on the held-out split: how much held-out ROC-AUC
    # degrades when each feature is shuffled. Unlike tree split counts this
    # reflects genuine predictive contribution and is comparable across
    # correlated features.
    perm = permutation_importance(
        model, X_test, y_test, n_repeats=8, random_state=RANDOM_STATE, scoring="roc_auc"
    )
    importance = sorted(
        ({"feature": n, "importance": round(float(m), 5)}
         for n, m in zip(feature_names, perm.importances_mean)),
        key=lambda d: d["importance"],
        reverse=True,
    )

    report = {
        "n_total": int(len(ya)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "positive_rate": round(float(ya.mean()), 4),
        "roc_auc": round(roc, 4),
        "pr_auc": round(pr, 4),
        "brier_score": round(brier, 4),
        "expected_calibration_error": round(ece, 4),
        "operating_point": _metrics_at(y_test, prob, threshold),
        "sweep": [_metrics_at(y_test, prob, t) for t in (0.3, 0.5, 0.7, 0.9)],
        "feature_importance": importance,
    }

    if groups is not None:
        pred = (prob >= threshold).astype(int)
        by_scenario = {}
        for name in sorted(set(g_test)):
            if name.endswith("_mislabelled"):
                continue  # deliberately flipped; error there is the point
            mask = g_test == name
            if not mask.any():
                continue
            wrong = int((pred[mask] != y_test[mask]).sum())
            by_scenario[name] = {
                "n": int(mask.sum()),
                "errors": wrong,
                "error_rate": round(wrong / int(mask.sum()), 4),
            }
        report["by_scenario"] = by_scenario

    return model, report


def train_login_model(n_accounts: int = 2600, verbose: bool = True) -> Dict:
    """Train the suspicious-login model and write it to ``auth/models/``."""
    import joblib

    os.makedirs(MODEL_DIR, exist_ok=True)
    X, y, scenarios = generate_login_dataset(n_accounts=n_accounts, seed=RANDOM_STATE)

    # A legitimate user locked out of their brokerage account is a worse
    # outcome than an attacker being asked for a second factor, so the
    # false-positive budget here is tight. Anything above the threshold is
    # challenged, not blocked.
    model, report = _fit(X, y, LOGIN_FEATURES, max_fpr=0.05, groups=scenarios)
    report["model"] = "CalibratedClassifierCV(HistGradientBoostingClassifier, isotonic)"
    report["features"] = LOGIN_FEATURES
    report["trained_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["training_data"] = "synthetic (auth/datasets.generate_login_dataset)"
    report["caveat"] = (
        "Trained on simulated accounts. Metrics measure recovery of the "
        "generator's process, not field accuracy against a live adversary. "
        "Retrain on auth/store.py login events once real data accumulates."
    )

    joblib.dump({"model": model, "features": LOGIN_FEATURES}, LOGIN_MODEL_PATH)
    with open(LOGIN_CARD_PATH, "w") as fh:
        json.dump(report, fh, indent=2)

    if verbose:
        _print_report("LOGIN RISK", report)
    return report


def train_bot_model(n: int = 9000, verbose: bool = True) -> Dict:
    """Train the bot-detection model and write it to ``auth/models/``."""
    import joblib

    os.makedirs(MODEL_DIR, exist_ok=True)
    X, y = generate_bot_dataset(n=n, seed=RANDOM_STATE)

    # Bot detection can afford to be a little more aggressive than login risk:
    # a false positive costs one extra challenge, not a lockout.
    model, report = _fit(X, y, BOT_FEATURES, max_fpr=0.02)
    report["model"] = "CalibratedClassifierCV(HistGradientBoostingClassifier, isotonic)"
    report["features"] = BOT_FEATURES
    report["trained_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["training_data"] = "synthetic (auth/datasets.generate_bot_dataset)"
    report["caveat"] = (
        "Trained on simulated telemetry across three automation tiers. The "
        "stealth tier is intentionally hard and partly unseparable; residual "
        "error there is expected and keeps the metrics honest."
    )

    joblib.dump({"model": model, "features": BOT_FEATURES}, BOT_MODEL_PATH)
    with open(BOT_CARD_PATH, "w") as fh:
        json.dump(report, fh, indent=2)

    if verbose:
        _print_report("BOT DETECTION", report)
    return report


def _print_report(title: str, report: Dict) -> None:
    op = report["operating_point"]
    print(f"\n{'=' * 68}")
    print(f"  {title}")
    print("=" * 68)
    print(f"  samples          {report['n_train']} train / {report['n_test']} test"
          f"  (positive rate {report['positive_rate']:.1%})")
    print(f"  ROC-AUC          {report['roc_auc']:.4f}")
    print(f"  PR-AUC           {report['pr_auc']:.4f}")
    print(f"  Brier score      {report['brier_score']:.4f}   (lower is better)")
    print(f"  Calibration err  {report['expected_calibration_error']:.4f}   (lower is better)")
    print(f"\n  Operating point @ threshold {op['threshold']}")
    print(f"    precision {op['precision']:.3f}   recall {op['recall']:.3f}"
          f"   F1 {op['f1']:.3f}   FPR {op['false_positive_rate']:.3f}")
    print(f"    TP {op['true_positives']}  FP {op['false_positives']}"
          f"  TN {op['true_negatives']}  FN {op['false_negatives']}")
    print("\n  Threshold sweep")
    print(f"    {'thresh':>7} {'prec':>7} {'recall':>7} {'FPR':>7}")
    for row in report["sweep"]:
        print(f"    {row['threshold']:>7} {row['precision']:>7.3f}"
              f" {row['recall']:>7.3f} {row['false_positive_rate']:>7.3f}")
    print("\n  Top features by permutation importance (held-out ROC-AUC drop)")
    for row in report["feature_importance"][:8]:
        bar = "#" * max(1, int(row["importance"] * 260))
        print(f"    {row['feature']:<26} {row['importance']:>8.5f}  {bar}")
    if report.get("by_scenario"):
        print("  Held-out error rate by scenario")
        for name, row in sorted(report["by_scenario"].items(),
                                key=lambda kv: -kv[1]["error_rate"]):
            bar = "#" * int(row["error_rate"] * 40)
            print(f"    {name:<32} {row['errors']:>3}/{row['n']:<4}"
                  f" {row['error_rate']:>6.1%}  {bar}")
    print()


def main() -> None:
    print("Training login risk + bot detection models...")
    train_login_model()
    train_bot_model()
    print(f"Models written to {MODEL_DIR}")


if __name__ == "__main__":
    main()
