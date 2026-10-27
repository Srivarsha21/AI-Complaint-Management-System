# AI dataset and NLP pipeline (module 5)

## The dataset is synthetic

`backend/app/ai/data/complaints_synthetic.csv` is **machine-generated** by
`backend/app/ai/data/generate_dataset.py` from templates written by the project author. It contains
**no real complaints, people, phone numbers or addresses**. It exists because no labelled corpus of
Hyderabad civic complaints was available to the project.

Consequences that must be stated whenever results are shown:

- Every metric in [ai_evaluation.md](ai_evaluation.md) is measured on synthetic data and
  **overestimates real-world performance**.
- The random-split test score is close to perfect because test rows reuse the same subjects and sentence
  patterns as the training rows. The "unseen scenarios" score in the same report is a more honest
  estimate, and real performance is expected to be lower still.
- Before any real deployment, the model should be re-trained and evaluated on a labelled sample of real
  complaints (e.g. complaints submitted through this system, labelled by staff).

## Columns

| Column | Meaning |
|---|---|
| `text` | Subject + ". " + description, exactly how the API builds the model input (`complaint_text()`) |
| `category_slug` | One of the 12 seeded category slugs (migration `07d419e71fad`) |
| `priority` | `low`, `medium`, `high` or `critical`, assigned by the criteria below |
| `scenario_id` | Which hand-written scenario produced the row (used for the grouped evaluation) |

## Generation method

Run `python -m app.ai.data.generate_dataset` from `backend/` (fixed seed `20261010`, deterministic output).

1. For each of the 12 categories the author wrote 12-14 **scenarios**. A scenario is one kind of problem
   (e.g. "open manhole", "dog bite", "low water pressure") with 2 subject variants, 2 description
   variants and a base severity.
2. Each row picks a scenario and fills `{where}` with a random landmark ("near the bus stop",
   "behind the temple") and one of 60 Hyderabad localities (Ameerpet, Kukatpally, Charminar, ...).
3. Optional parts are added at random: an opener ("Respected sir/madam,"), a duration
   ("since 3 days", "for the last 2 months"), a vulnerable-people sentence, a scale sentence and a
   closer ("Kindly do the needful.", "Pls resolve asap.").
4. Variation: ~15% short-form rows (no extras), ~15% with 1-3 typos (swapped, dropped or doubled
   letters), ~10% lowercased without punctuation. Indian-English phrasing is used throughout
   ("since 3 days", "do the needful", "current is going", "nala", "UGD", "cheruvu").
5. Exact duplicate texts are discarded, so no text appears in both the train and test split.
6. 200 rows per category, 2,400 rows in total.

### Borderline cases and how they are labelled

Some scenarios deliberately mention vocabulary of another category. The label is the **primary problem
the citizen wants fixed**:

| Example | Label | Rule |
|---|---|---|
| Garbage being burnt, smoke enters houses | pollution | burning/smoke -> pollution |
| Drainage water mixing into the drinking-water pipeline | water-supply | contamination of supply -> water-supply |
| Stagnant drain breeding mosquitoes, asks for fogging | public-health | mosquito control request -> public-health |
| Tree branch fallen on a power line | electricity | hazard to power lines -> electricity |
| Exposed wires at a street-light pole | street-lights | street-light infrastructure -> street-lights |
| Plastic waste choking a drain, asks to clear the garbage | garbage-sanitation | asks for garbage removal |
| Building constructed over a nala | encroachment | unauthorised construction |
| Cattle tied on the footpath | stray-animals | animals are the problem |
| Lights inside a park not working | parks-trees | park maintenance |
| Thank-you messages, certificates, tax, traffic signals, fraud calls | other | negative examples that are not civic-infrastructure faults |

## Priority labelling criteria

Applied by the generator (not by a model):

1. **Base severity per scenario** (author's judgement):
   - `critical`: immediate danger to life or limb - live/fallen wire, electric shock, open manhole,
     sparking transformer, fire, road/building collapse, people trapped or stranded, mass illness
     from supply water.
   - `high`: health or safety risk, or a serious service failure - sewage entering homes, no water for
     days, contaminated water, dog bites, fallen trees, leaning poles, dengue cases.
   - `medium`: ordinary service failure affecting a street or colony - garbage not lifted, street light
     off, potholes, low pressure.
   - `low`: minor, cosmetic, administrative, or a request for something new.
2. **Modifiers** (never above `high`; only a critical scenario produces `critical`):
   vulnerable people mentioned +1, large scale mentioned +1, a week or longer and still `low` -> `medium`.
3. **Simulated annotator noise**: ~4% of labels are moved one level up or down at random.

Resulting distribution: see the "Setup" section of [ai_evaluation.md](ai_evaluation.md).

The priority **rules** in `backend/app/ai/priority.py` follow similar ideas but use their own keyword
lists, not the generator's scenario tags. Because the same author wrote both, their agreement is
optimistic and is not a validation of the rules on real complaints.

## Pipeline overview

| Step | File | Method |
|---|---|---|
| Preprocessing | `app/ai/preprocessing.py` | remove URLs, emails, phone numbers (privacy); lowercase; expand shorthand ("pls", "asap"); strip punctuation; drop a small stopword list but keep negations |
| Category | `app/ai/classifier.py` | TF-IDF word 1-2 grams + char_wb 2-5 grams, logistic regression with probability outputs |
| Priority | `app/ai/priority.py` | category base level + hazard / risk / vulnerable / scale / duration / urgency rules, each producing a human-readable factor |
| Emergency flag | `app/ai/priority.py`, `frontend/src/utils/emergency.ts` | keyword rules only; the frontend shows the 112 banner instantly while typing |
| Sentiment / urgency | `app/ai/sentiment.py` | hand-written lexicon, negation and intensifier handling |
| Duplicates | `app/ai/duplicates.py`, `app/repositories/ai_repository.py` | TF-IDF cosine similarity within the same category, not closed, last 30 days; haversine distance filter/boost when both have coordinates |
| Department | `app/services/ai_service.py` | predicted slug -> active DB category -> its department |

## Limitations

- **Synthetic data** (see above). Real complaints are longer, messier, often mix Telugu/Hindi and English,
  and describe situations no template covers.
- **English only.** Telugu or Hindi text (or transliterated Telugu) is not understood by the classifier,
  the sentiment lexicon or the keyword rules.
- **Keyword rules are brittle.** Paraphrases ("the cable is lying on the road and buzzing") can miss the
  emergency flag; innocent uses ("fire station road") can trigger it. The 112 banner is a precaution, not a
  diagnosis, and the static 112 notice is always shown on the form.
- **Sentiment is not validated.** There are no sentiment labels, so no accuracy is claimed. Complaints are
  nearly always negative, so the label carries little information; sarcasm is not detected.
- **Duplicate detection** uses word overlap: two reports of the same pothole written very differently
  may not match, and two different problems on the same street with similar wording may match. It never
  rejects a complaint; it only informs the citizen and staff.
- **Priority is a prediction.** Staff can override it; the UI labels it "AI-predicted" until they do.

## Retraining

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.ai.data.generate_dataset   # regenerate data (only if the generator changed)
.\.venv\Scripts\python.exe -m app.ai.train                    # trains, evaluates, writes artifacts + docs/ai_evaluation.md
```
