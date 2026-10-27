"""Train and evaluate the category classifier; evaluate the priority rules.

    python -m app.ai.train            (run from backend/)

1. Loads the SYNTHETIC dataset app/ai/data/complaints_synthetic.csv.
2. Stratified 80/20 train/test split with a fixed seed (split_dataset()).
3. Fits the TF-IDF + logistic regression pipeline on the training split only and
   evaluates it on the held-out test split.
4. Harder check: a scenario-disjoint split (no hand-written scenario appears in both
   train and test), to show how much the random split flatters the model.
5. Evaluates the rules-based priority baseline on the same held-out test split.
6. Saves app/ai/artifacts/category_model.joblib (the model trained in step 3, so the
   shipped model is exactly the one the reported test metrics describe) and writes
   docs/ai_evaluation.md. Every number in that file is computed here.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from app.ai import classifier
from app.ai.priority import LEVELS, RULES_VERSION, predict_priority
from app.core.config import BACKEND_DIR

SEED = 42
TEST_SIZE = 0.2
DATASET_PATH = BACKEND_DIR / "app" / "ai" / "data" / "complaints_synthetic.csv"
REPORT_PATH = BACKEND_DIR.parent / "docs" / "ai_evaluation.md"


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def split_dataset(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The fixed, stratified train/test split. Tests reuse it as a regression guard."""
    train, test = train_test_split(data, test_size=TEST_SIZE, random_state=SEED, stratify=data["category_slug"])
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report_table(y_true, y_pred, labels: list[str]) -> tuple[str, dict]:
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    lines = ["| Class | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"]
    for label in labels:
        r = report[label]
        lines.append(f"| {label} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1-score']:.3f} | {int(r['support'])} |")
    for avg in ("macro avg", "weighted avg"):
        r = report[avg]
        lines.append(f"| **{avg}** | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1-score']:.3f} | {int(r['support'])} |")
    return "\n".join(lines), report


def _confusion_table(y_true, y_pred, labels: list[str], short: dict[str, str] | None = None) -> str:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    short = short or {label: label for label in labels}
    header = "| true \\ predicted | " + " | ".join(short[label] for label in labels) + " |"
    lines = [header, "|---|" + "---:|" * len(labels)]
    for label, row in zip(labels, matrix):
        lines.append(f"| {label} | " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def main() -> None:
    data = load_dataset()
    dataset_hash = _sha256(DATASET_PATH)
    train, test = split_dataset(data)
    labels = sorted(data["category_slug"].unique())
    now = datetime.now(UTC)
    version = f"tfidf-logreg-{now:%Y%m%d}-{dataset_hash[:8]}"

    # --- Category classifier: random stratified split ----------------------------------
    pipeline = classifier.build_pipeline(SEED)
    pipeline.fit(train["text"], train["category_slug"])
    predicted = pipeline.predict(test["text"])
    category_table, category_report = _report_table(test["category_slug"], predicted, labels)
    accuracy = accuracy_score(test["category_slug"], predicted)
    short = {label: f"{i + 1}" for i, label in enumerate(labels)}
    legend = ", ".join(f"{i + 1} = {label}" for i, label in enumerate(labels))
    category_cm = _confusion_table(test["category_slug"], predicted, labels, short)
    majority = test["category_slug"].value_counts(normalize=True).iloc[0]

    # Examples the model got wrong (useful for the viva discussion).
    wrong = test.assign(predicted=predicted)[test["category_slug"] != predicted].head(8)

    # --- Harder check: scenario-disjoint split ------------------------------------------
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    g_train_idx, g_test_idx = next(splitter.split(data["text"], data["category_slug"], groups=data["scenario_id"]))
    g_train, g_test = data.iloc[g_train_idx], data.iloc[g_test_idx]
    g_pipeline = classifier.build_pipeline(SEED)
    g_pipeline.fit(g_train["text"], g_train["category_slug"])
    g_pred = g_pipeline.predict(g_test["text"])
    g_accuracy = accuracy_score(g_test["category_slug"], g_pred)
    g_macro = f1_score(g_test["category_slug"], g_pred, average="macro", zero_division=0)
    g_weighted = f1_score(g_test["category_slug"], g_pred, average="weighted", zero_division=0)

    # --- Priority rules on the same held-out test split ----------------------------------
    rule_pred = [predict_priority(text, slug).level for text, slug in zip(test["text"], test["category_slug"])]
    priority_table, priority_report = _report_table(test["priority"], rule_pred, LEVELS)
    priority_accuracy = accuracy_score(test["priority"], rule_pred)
    distance = np.abs(
        np.array([LEVELS.index(p) for p in test["priority"]]) - np.array([LEVELS.index(p) for p in rule_pred])
    )
    within_one = float(np.mean(distance <= 1))
    priority_cm = _confusion_table(test["priority"], rule_pred, LEVELS)
    priority_majority = test["priority"].value_counts(normalize=True).iloc[0]
    emergency_flags = [predict_priority(t, s).possible_emergency for t, s in zip(test["text"], test["category_slug"])]
    is_critical = test["priority"].to_numpy() == "critical"
    flagged = np.array(emergency_flags)
    emergency_recall = float(flagged[is_critical].mean()) if is_critical.any() else float("nan")
    emergency_false_flags = int((flagged & ~is_critical).sum())

    # --- Save model -----------------------------------------------------------------
    artifacts = classifier.artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "version": version,
            "trained_at": now.isoformat(timespec="seconds"),
            "dataset_sha256": dataset_hash,
            "sklearn_version": sklearn.__version__,
            "train_size": len(train),
            "test_size": len(test),
            "test_accuracy": round(float(accuracy), 4),
            "test_macro_f1": round(float(category_report["macro avg"]["f1-score"]), 4),
        },
        classifier.model_path(),
        compress=3,
    )
    classifier.reset_cache()

    # --- Report ---------------------------------------------------------------------
    wrong_rows = "\n".join(
        f"| {r.category_slug} | {r.predicted} | {r.text[:110].replace('|', '/')}{'...' if len(r.text) > 110 else ''} |"
        for r in wrong.itertuples()
    ) or "| - | - | (none) |"
    category_counts = data["category_slug"].value_counts().sort_index()
    priority_counts = data["priority"].value_counts().reindex(LEVELS, fill_value=0)

    report = f"""# AI evaluation report (generated)

> **Generated by `python -m app.ai.train` on {now:%Y-%m-%d %H:%M} UTC. Do not edit by hand**; re-run the
> command to refresh it. All numbers below were computed by that script.
>
> **The data is SYNTHETIC** (template-generated, see [ai_dataset.md](ai_dataset.md)). Test examples come from
> the same templates as the training examples, so these scores **overestimate real-world performance**.
> They show that the pipeline works and act as a regression guard; they are not evidence of accuracy on
> real citizen complaints. A real evaluation needs a labelled sample of real complaints.

## Setup

| Item | Value |
|---|---|
| Model version | `{version}` |
| Dataset | `backend/app/ai/data/complaints_synthetic.csv` (SHA-256 `{dataset_hash[:16]}...`) |
| Dataset size | {len(data)} rows, {len(labels)} categories |
| Split | stratified by category, {int((1 - TEST_SIZE) * 100)}/{int(TEST_SIZE * 100)}, seed {SEED} |
| Train / test size | {len(train)} / {len(test)} |
| Model | TF-IDF word 1-2 grams + char_wb 2-5 grams, logistic regression (C=5, balanced class weights) |
| scikit-learn | {sklearn.__version__} |
| Priority rules | `{RULES_VERSION}` (no training; evaluated on the same test split) |

Rows per category: {", ".join(f"{k} {v}" for k, v in category_counts.items())}.

Priority labels in the whole dataset: {", ".join(f"{k} {v}" for k, v in priority_counts.items())}.

## 1. Category classifier (held-out test split)

Accuracy: **{accuracy:.3f}** (majority-class baseline: {majority:.3f}).
Macro F1: **{category_report["macro avg"]["f1-score"]:.3f}**, weighted F1: **{category_report["weighted avg"]["f1-score"]:.3f}**.

A (near-)perfect score on this split is an artefact of template-generated data: test rows reuse the
subjects and sentence patterns seen in training. It is **not** an accuracy claim. Section 2 gives a
more honest estimate.

{category_table}

### Confusion matrix

Columns use numbers: {legend}.

{category_cm}

### Misclassified test examples (first {len(wrong)})

| True | Predicted | Text |
|---|---|---|
{wrong_rows}

## 2. Harder check: unseen scenarios

The random split above lets the test set share hand-written scenarios (sentence templates) with the
training set. Here the split is grouped by `scenario_id` (StratifiedGroupKFold, 5 folds, first fold,
seed {SEED}), so every test scenario is new to the model. Train {len(g_train)} / test {len(g_test)} rows.

| Metric | Value |
|---|---:|
| Accuracy | {g_accuracy:.3f} |
| Macro F1 | {g_macro:.3f} |
| Weighted F1 | {g_weighted:.3f} |

This is closer to (but still more optimistic than) what to expect on real complaints, which use
vocabulary and situations no template covers.

## 3. Priority rules baseline (held-out test split)

The rules use the complaint's true category plus keyword rules (see `backend/app/ai/priority.py`).
Labels were assigned by the dataset generator from author-defined criteria. Both the rules and the labels
were written by the same author from similar criteria, so agreement here is optimistic.

Accuracy: **{priority_accuracy:.3f}** (majority-class baseline: {priority_majority:.3f}).
Within one level: **{within_one:.3f}**.
Macro F1: **{priority_report["macro avg"]["f1-score"]:.3f}**, weighted F1: **{priority_report["weighted avg"]["f1-score"]:.3f}**.

{priority_table}

### Confusion matrix

{priority_cm}

### Emergency keyword flag

Share of test rows labelled `critical` that the emergency keyword rules flag (recall): **{emergency_recall:.3f}**.
Rows flagged although not labelled `critical`: **{emergency_false_flags}** of {int((~is_critical).sum())}.
The flag is a prompt to call 112, never a verified emergency.

## 4. Sentiment / urgency

The lexicon-based sentiment module (`backend/app/ai/sentiment.py`) is **not evaluated**: the dataset has no
sentiment labels, and no figure is claimed for it.

## Retraining

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m app.ai.data.generate_dataset   # only if the generator changed
.\\.venv\\Scripts\\python.exe -m app.ai.train
```
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"model {version}: test accuracy {accuracy:.3f}, macro F1 {category_report['macro avg']['f1-score']:.3f}")
    print(f"scenario-disjoint: accuracy {g_accuracy:.3f}, macro F1 {g_macro:.3f}")
    print(f"priority rules: accuracy {priority_accuracy:.3f}, within one level {within_one:.3f}")
    print(f"saved {classifier.model_path()} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
