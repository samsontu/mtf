# CIHI → WHO Mapping Feedback

End-to-end pipeline, from CIHI reviewer validation to the feedback that is
still actionable after the WHO 2026 release, plus mapping relations and
proposed Foundation mapping rules for the suggested corrections that are
single stem codes or post-coordinations. See `Method.md` for the full algorithm.

Folder layout: pipeline scripts in `bin/`, documentation in `doc/`, data
files (inputs and outputs) in the `cihifeedback/` folder itself. Run all
commands from `cihifeedback/`.

- `bin/icdapi_credentials.json` — WHO ICD-API client id and secret, read by
  every script that calls the API. Keep it private (it is readable only by
  its owner); do not share or commit it.
- `bin/legacy/` and `legacy/` — earlier scripts and their outputs that are
  not part of the pipeline (e.g. `generateMappingRulesFromSource.py` and
  `ProposedMappingRules.*`, superseded by step 4).

## Pipeline

```bash
# 1. Build the populated WHO feedback template + triage outputs.
#    Asks you to confirm the latest ICD-11 MMS release for the code check
#    (or pass --release <id>; --no-api skips the check).
python3 bin/generateFeedbackFromCIHIvalidation.py

# 2. Cross-reference CIHI's suggested codes against the 2026 release.
python3 bin/findSuggestionsFixedIn2026.py

# 3. Remove the 2026-fixed entries from the feedback workbook, and split
#    the rows with a suggested code by kind of code.
python3 bin/generateUnfixedFeedbackAndSplits.py

# 4. Stem-code rows: stage 1 adds mapping relations, stage 2 proposes
#    Foundation mapping rules; post-coordinated rows: stage 3 does both
#    (asks you to confirm the ICD-11 release, or pass --release <id>;
#    --stage 1|2|3 runs one stage).
python3 bin/generateMappingRelationsAndRules.py
```

## Inputs

- **`AllBatches_ForSamson_V1clean.xlsx`** — CIHI reviewer validation workbook (sheet `Sheet3`); two adjacent rows per map under review. Used by step 1.
- **`WHO_Mapping Feedback Template_V2.0.xlsx`** — the WHO feedback template to populate (step 1).
- **`2026_10To11MapToOneCategory.xlsx`** — WHO's 2026 ICD-10 → ICD-11 mapping release (step 2).
- **WHO ICD-API** — used by step 1 to check suggested codes and by step 4 to find Foundation entities, descendant matches and to describe post-coordinations; helpers in `bin/icdapi.py`, credentials read from `bin/icdapi_credentials.json`.

## Outputs

From step 1 (`bin/generateFeedbackFromCIHIvalidation.py`):
- **`WHO_Mapping_Feedback_CIHI_AllBatches.xlsx`** — populated WHO template; one row per qualifying source pair.
- **`feedbackHeldForReview.xlsx`** — pairs that need manual attention (A–G mismatch between reviewer rows, no case matched, a suggested code that is not a valid ICD-11 code or code cluster, or one containing a code not in the chosen ICD-11 MMS release).

From step 2 (`bin/findSuggestionsFixedIn2026.py`):
- **`CIHISuggestedCodesFixedIn2026Release.xlsx`** — feedback rows whose CIHI-suggested code matches the 2026 release for the same ICD-10.

From step 3 (`bin/generateUnfixedFeedbackAndSplits.py`):
- **`WHO_Mapping_Feedback_CIHI_Unfixed2026_AllBatches.xlsx`** — the main feedback file minus the 2026-fixed rows; this is the actionable feedback to submit to WHO.
- **`rowsMissingSuggestedCode.xlsx`** — Unfixed rows whose Suggested/Corrected Mapped Code (column K) is empty.
- **`rowsWithSuggestedCode.xlsx`** — Unfixed rows whose Suggested/Corrected Mapped Code (column K) has a value.
- **`rowsWithSuggestedCode-postcoordinated.xlsx`** — rows whose suggested code (K) is a post-coordinated expression.
- **`rowsWithSuggestedCode-Ytargets.xlsx`** — rows whose K is a single "other specified" code ending in Y.
- **`rowsWithSuggestedCode-stemCode.xlsx`** — rows whose K is any other single stem code (input to step 4).

From step 4 (`bin/generateMappingRelationsAndRules.py`):
- **`rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`** — the stem-code rows with the Foundation entity (P), mapping relation (U) and reasoning (V) from stage 1, and the descendant match (W–Y), proposed mapping rule (Z), rule notes (AA) and confidence with rationale (AB–AC) from stage 2.
  Both `-relationsAndRules` files start with a README sheet describing every column.
- **`rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx`** — the post-coordinated rows with title (L), Foundation expression (P), relation (U), reasoning incl. MMS validity (V), existing or new Foundation entity (W–Y), proposed mapping rule (Z), rule notes (AA) and confidence with rationale (AB–AC), from stage 3.

## Docs (`doc/`)

- **`Results.md`** — statistics for the step-4 mapping relations and rules (MMS 2026-01).
- **`Method.md`** — algorithm, case definitions, per-case column mapping, the 2026 cross-reference logic, and the stem-code relation and mapping-rule step.
- **`cihifeedback-prompts.md`** — original prompts for steps 1–3.
- **`addStemCodeRelationPrompt.txt`** — original specification for step 4, stage 1.
- **`mappingRulesSpecification.md`** — specification of the proposed mapping rules (step 4, stages 2 and 3).
- **`originalMappingRulesGenerationPrompt.txt`** — the original prompt from which an earlier version of that specification was derived (implemented by the superseded `bin/legacy/generateMappingRulesFromSource.py`).
- **`determine-semantic-relationships.md`** — rules including post-coordinated expressions (step 4, stage 3).
- **`determine-stemcode-semantic-relationships.md`** — rules for assigning Equivalent / Broader / Narrower / Related in step 4.
