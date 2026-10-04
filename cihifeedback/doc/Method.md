# Method: From CIHI Validation to Post-2026 Actionable Feedback

This document describes the four-step pipeline that turns CIHI's
reviewer validation workbook into the WHO Mapping Feedback Template,
cross-references it against the WHO 2026 release, isolates the
feedback that is still actionable, and, for the suggested corrections
that are single stem codes or post-coordinations, assigns a mapping
relation and proposes a Foundation mapping rule.

Run all commands from the `cihifeedback/` folder. Scripts live in
`bin/`; data files (inputs and outputs) live in `cihifeedback/`;
documentation lives in `doc/`.

## Pipeline overview

```bash
# 1. Populate the WHO feedback template + triage outputs.
#    Prompts to confirm the most recent ICD-11 MMS release for the
#    suggested-code check; pass --release <id> to skip the prompt, or
#    --no-api to skip the API check.
python3 bin/generateFeedbackFromCIHIvalidation.py

# 2. Cross-reference CIHI's suggested codes against the 2026 release.
python3 bin/findSuggestionsFixedIn2026.py

# 3. Remove the 2026-fixed entries from the feedback workbook,
#    split the unfixed feedback by whether K is populated, and split
#    the rows with K by kind of suggested code.
python3 bin/generateUnfixedFeedbackAndSplits.py

# 4. Stem-code rows: stage 1 assigns mapping relations, stage 2
#    proposes Foundation mapping rules. Post-coordinated rows: stage 3
#    does both. (WHO ICD-API; confirms the release like step 1, or pass
#    --release <id>; --stage 1|2|3 runs one stage.)
python3 bin/generateMappingRelationsAndRules.py
```

Each script is idempotent — re-running regenerates the corresponding
outputs from scratch. Step 2 depends on step 1; step 3 depends on
steps 1 and 2; step 4 depends on step 3.

The WHO ICD-API helpers used by steps 1 and 4 are in `bin/icdapi.py`
(credentials are read from `bin/icdapi_credentials.json`).

---

# Step 1 — Populating the WHO Mapping Feedback Template

This step is implemented by `bin/generateFeedbackFromCIHIvalidation.py` and
transforms the CIHI reviewer validation workbook into the WHO Mapping
Feedback Template format.

## Inputs

- **Source.** `AllBatches_ForSamson_V1clean.xlsx`, sheet `Sheet3`.
  Each map is reviewed by two reviewers, recorded on two consecutive rows
  (reviewer 1, reviewer 2). Row 1 is the header.
- **Template.** `WHO_Mapping Feedback Template_V2.0.xlsx`, sheet
  `Feedback Template`. Columns A–T define the output schema. The template's
  README and List (dropdown) sheets are preserved unchanged.

## Outputs

- **`WHO_Mapping_Feedback_CIHI_AllBatches.xlsx`** — a copy of the template
  with one row per qualifying pair appended to the `Feedback Template`
  sheet (the example row 2 is cleared and re-used as a style template).
- **`feedbackHeldForReview.xlsx`** — pairs flagged for manual attention: A–G
  mismatch, no case matched, an invalid suggested code (algorithm
  step 4), or a suggested code not in the MMS release (algorithm step 5). If no pair is flagged, the file is overwritten with a
  one-line "No rows need review" marker.

(The `rowsMissingSuggestedCode.xlsx` / `rowsWithSuggestedCode.xlsx`
split is now produced at the end of step 3, against the post-2026
Unfixed workbook — see step 3 below.)

## Static fields (every emitted target row)

| Target column | Value |
|---|---|
| A Organization/Affiliation | `CIHI` |
| B Date | `2025-07-04` |
| C Name | `Sharon Baker` |
| D Contact Details | `whofic.mtf@gmail.com` |
| E Version of WHO Mapping Table | `2022 10To11MapToOneCategory` |
| F Map direction | `Forward (ICD-10 to ICD-11)` |

## Source column reference

| Letter | Header | Used as |
|---|---|---|
| A | WHO_icd10Code | Target G + pair check |
| B | WHO_icd10Title | Target H + pair check + case a title filter |
| C | ICD-10 link | pair check |
| D | Updated WHO_icd11Code | Target I + pair check |
| E | Updated WHO_icd11Title | Target J + pair check |
| F | ICD-11 link | pair check |
| G | Relation | pair check |
| H | Reviewer choice | case classification |
| I | Agree? | case c gate (`agree` / `Disagree`) |
| J | Reviewer | sanity (`1` / `2`) |
| K | Reviewer ICD-11 coding if neither correct | case c target K |
| L | Comment and Explanation | case b/c target N |
| M | Conflict Resolution team decision | case classification |
| N | Review team ICD-11 coding if neither correct | case d target K |
| O | Comments | case b/d/e target N |
| P | Actions for WHO | case b/d/e target R |
| Q | Comments from Eva | case a/b classification + case b/e target N |
| R | CIHI ICD-11 code | case b target K |
| S | CIHI ICD-11 stem code title | (informational) |
| T | Reason for No Match to WHO map | case b target Q |
| W | Additional CIHI Info — Equivalence (E/B/N) | case b target M |

## Algorithm

For every adjacent pair of source rows (`(2,3), (4,5), …`):

1. **Verify pair integrity.** Columns A–G must be identical between the
   two rows. If any of A–G differs, log the pair in
   `feedbackHeldForReview.xlsx` with reason `A-G mismatch in: <columns>` and
   continue.

2. **Classify the pair** using the rules below in priority order
   `a > b > c > d > e` (first match wins). All string comparisons are
   case-insensitive on H, I, M; substring matches on Q lower-case the
   value first.

   | Case | Condition | Action |
   |---|---|---|
   | **a** | both H == `"WHO 2024 map correct"` **OR** both M == `"WHO 2024 map correct"` **OR** Q on either row contains `"WHO map correct"` **OR** both M contain `"D37-D48"` (case-insensitive substring) **OR** both P contain `"D37-D48"` (case-insensitive substring) **OR** B (`WHO_icd10Title`) contains `"Neoplasm of uncertain or unknown behaviour"` (case-insensitive substring) | **skip** — no target row |
   | **b** | both H == `"CIHI map correct"` **OR** both M == `"CIHI map correct"` **OR** Q on either row contains **both** `"CIHI"` **and** `"correct"` (substring, case-insensitive) | emit row, CIHI's code |
   | **c** | both H == `"Neither correct"` **AND** both I == `"agree"` | emit row, reviewers' code |
   | **d** | both M == `"Neither correct"` | emit row, conflict-resolution team's code |
   | **e** | each M is `"Review"` or `"Review with Eva"` | emit row, blank suggested code |

   Anything that matches none of a–e is logged in
   `feedbackHeldForReview.xlsx` with reason `no case matched`.

3. **Emit the target row** (when applicable) using the common fields:

   | Target | Value |
   |---|---|
   | A–F | Static fields (above) |
   | G | source A (`WHO_icd10Code`) |
   | H | source B (`WHO_icd10Title`) |
   | I | source D (`Updated WHO_icd11Code`) |
   | J | source E (`Updated WHO_icd11Title`) |

   Then apply the per-case mapping below. Columns left unset are blank.

4. **Validate the suggested code (target K).** If K is non-empty and is
   not a syntactically valid ICD-11 code or post-coordination, the pair
   is **not emitted**; it is logged in `feedbackHeldForReview.xlsx` with reason
   `case <x>: invalid suggested code (<detail>)` and the offending value
   in the `Suggested code` column. Valid syntax is
   `stem[&ext…][/stem[&ext…]…]`, where
   - a stem code is 4 characters not starting with X (character 2 a
     letter, character 3 a digit) with an optional `.x`/`.xx` suffix,
     e.g. `1C8G.Z`, `8A03.1Y`, `MG30.04`;
   - an extension code is `X` followed by 3–5 characters, e.g. `XT9C`,
     `XA0D34`;
   - `&` must be followed by an extension code and `/` by a stem code;
   - whitespace around separators and non-breaking spaces are ignored;
     any other text (titles, notes, "vs", ICD-10 codes) is invalid.

   Empty K values are not flagged (they go to
   `rowsMissingSuggestedCode.xlsx` in step 3).

5. **Check that the suggested codes exist (WHO ICD-API).** At start-up
   the script asks the ICD-API for the most recent ICD-11 MMS release
   and asks the user to confirm it (or type another release id);
   `--release <id>` skips the prompt and `--no-api` skips this step.
   Each distinct component code of every emitted K is looked up with
   the `codeinfo` endpoint of that release. Pairs with any code that
   does not exist (e.g. `BP02`, or `1D02.1`, which was removed in
   2026-01) are **not emitted**; they are logged in
   `feedbackHeldForReview.xlsx` with reason
   `case <x>: suggested code not in ICD-11 MMS <release> (<codes>)`.
   Credentials are read from `bin/icdapi_credentials.json`.

### Case b — CIHI map correct

| Target | Source |
|---|---|
| K Suggested/Corrected Mapped Code | source R (`CIHI ICD-11 code`) |
| L Suggested/Corrected Mapped Code Title | blank |
| M Corrected Code Mapping Relation | source W mapped via `E→Equivalent / B→Broader / N→Narrower` (other values, including "Relationship not assessed", → blank) |
| N Comment | concatenate (newline-joined, deduped, empties skipped):<br>1. source O (deduped if both rows match)<br>2. source L from row 1<br>3. source L from row 2<br>4. **If L(r1) ≠ L(r2):** source Q(r1) and Q(r2) (Eva's notes) |
| Q Additional Comments | source T (`Reason for No Match to WHO map`) |
| R Action for WHO | source P (`Actions for WHO`); but if that value is `"Review with Eva"` then emit `"update WHO map"` instead |

### Case c — Neither correct, reviewers agree

| Target | Source |
|---|---|
| K | source K (`Reviewer ICD-11 coding if neither correct`) |
| N | concatenate source L of both rows |
| R | static `"Update map"` |

### Case d — Conflict-resolution team's coding

| Target | Source |
|---|---|
| K | source N (`Review team ICD-11 coding if neither correct`) |
| N | source O (`Comments`) |
| R | source P (`Actions for WHO`) |

### Case e — Review with Eva

| Target | Source |
|---|---|
| K | blank |
| N | concatenate source O(r1), Q(r1), Q(r2) — newline-joined, deduped |
| R | source P (`Actions for WHO`) |

## Quality controls

- Pair integrity check on columns A–G catches any reviewer rows that
  have been misaligned.
- Cases are mutually exclusive in the resolved priority order; first
  match wins.
- Case-insensitive comparisons absorb upper/lower variants present in
  the data (e.g., `CIHI map correct` vs `CIHI Map correct`).
- Suggested codes (target K) that are not valid ICD-11 code syntax, or
  that contain codes missing from the chosen MMS release, are held back
  rather than sent to WHO.
- All flagged pairs (A–G mismatches, unmatched cases, invalid suggested
  codes) are written to `feedbackHeldForReview.xlsx` with reason, ICD-10 code,
  suggested code, and the H/I/M/Q values of both rows so the source can
  be corrected and the script re-run.

---

# Step 2 — Cross-referencing against the 2026 WHO release

This step is implemented by `bin/findSuggestionsFixedIn2026.py` and identifies
the CIHI suggestions that the 2026 release already implements.

## Inputs

- **`WHO_Mapping_Feedback_CIHI_AllBatches.xlsx`** — from step 1; the
  populated WHO template.
- **`2026_10To11MapToOneCategory.xlsx`** — the WHO 2026 release of the
  ICD-10 → ICD-11 mapping. Sheet `10To11MapToOneCategory`. Key columns:
  `C icd10Code`, `J icd11Code`, `L icd11Title`.

## Output

- **`CIHISuggestedCodesFixedIn2026Release.xlsx`** — every feedback row
  whose CIHI-suggested code matches the 2026 release's icd11Code for
  the same ICD-10. The 2026 icd11Code and icd11Title are appended as
  two cross-reference columns at the right.

## Algorithm

1. Build an in-memory lookup from the 2026 file:
   `icd10Code (col C) → (icd11Code (col J), icd11Title (col L))`.
2. For each row in the `Feedback Template` sheet of the step-1
   workbook:
   - Skip rows where column **K (Suggested/Corrected Mapped Code)** is
     empty (case-e rows and case b/c/d rows with no source code).
   - Otherwise read the ICD-10 code from column **G**.
   - If the suggested code (whitespace-trimmed) equals the 2026
     release's icd11Code for that ICD-10, write the row plus the two
     cross-reference columns to the output.

Strings are compared with whitespace trimmed; case is preserved.

---

# Step 3 — Producing the post-2026 feedback file

This step is implemented by `bin/generateUnfixedFeedbackAndSplits.py` and isolates the
feedback that is still actionable after the 2026 release.

## Inputs

- **`WHO_Mapping_Feedback_CIHI_AllBatches.xlsx`** — from step 1; the
  populated WHO template.
- **`CIHISuggestedCodesFixedIn2026Release.xlsx`** — from step 2; the
  rows whose suggested code matches the 2026 release.

## Outputs

- **`WHO_Mapping_Feedback_CIHI_Unfixed2026_AllBatches.xlsx`** — a copy
  of the step-1 workbook with the matched rows removed. README and
  List sheets and the template's formatting are preserved. This is the
  actionable feedback to submit to WHO.
- **`rowsMissingSuggestedCode.xlsx`** — every Unfixed row whose column
  K (Suggested/Corrected Mapped Code) is empty.
- **`rowsWithSuggestedCode.xlsx`** — every Unfixed row whose column K
  has a value. Complementary to `rowsMissingSuggestedCode.xlsx`.
- **`rowsWithSuggestedCode-postcoordinated.xlsx`** — rows of
  `rowsWithSuggestedCode.xlsx` whose K is a post-coordinated
  expression (contains `&` or `/`).
- **`rowsWithSuggestedCode-Ytargets.xlsx`** — remaining rows whose K is
  a single code ending in `Y` (an "other specified" residual, e.g.
  `1D61.Y`, `8B9Y`).
- **`rowsWithSuggestedCode-stemCode.xlsx`** — remaining rows whose K is
  a single stem code. Input to step 4.

## Algorithm

1. Build the removal set: for each row in the step-2 output, take the
   `(ICD-10 = col G, suggested code = col K)` pair, trimmed.
2. Open the step-1 workbook; iterate the `Feedback Template` sheet.
   Skip any data row whose `(col G, col K)` pair is in the removal
   set.
3. Clear the original data rows in place, then re-write the kept rows
   starting at row 2, re-applying the example row's formatting.
4. Save as the new Unfixed workbook.
5. Partition the kept rows by whether column K is empty, and write the
   two derived workbooks. Both use the WHO template column layout
   (header from row 1 of the template).
6. Partition the rows with K by kind of suggested code, first match
   wins: post-coordinated → Y target → stem code, and write the three
   derived workbooks in the same layout. The script stops if any row
   fits none of the categories, so every row is accounted for.

---

# Step 4 — Mapping relations and mapping rules

This step is implemented by `bin/generateMappingRelationsAndRules.py` in three
stages. Stages 1 and 2 handle the stem-code suggestions and write
`rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`; stage 3 handles the
post-coordinated suggestions and writes
`rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx`. By default all
stages run; `--stage 1`, `2` or `3` runs one (stage 2 reads the existing
stage-1 output).

Both output files open on a **README** sheet, written by stages 2 and 3,
that describes the file and gives the meaning and possible values of
every column (A–AC); the data are on the second sheet.

Suggestions whose code is an "other specified" Y code
(`rowsWithSuggestedCode-Ytargets.xlsx`) are not processed.

## Input

- **`rowsWithSuggestedCode-stemCode.xlsx`** — from step 3 (stages 1–2).
- **`rowsWithSuggestedCode-postcoordinated.xlsx`** — from step 3 (stage 3).
- WHO ICD-API, for the release the user confirms (most recent by
  default; `--release <id>` skips the prompt). The MMS `autocode`
  endpoint is used where the release supports it; otherwise the
  Foundation search is used (see stage 2).

## Output

**`rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`** (stages 1–2) — the
stem-code rows with column P filled and these added columns:

| Column | Header | Stage | Content |
|---|---|---|---|
| P | Suggested/Corrected Mapped Foundation Entity | 1 | Foundation URI of K (T1U), filled where empty |
| U | Completed Code Mapping Relation | 1 | Equivalent / Broader / Narrower / Related |
| V | Reasoning | 1 | `Manual`, or the rule applied and the target's Foundation title |
| W | Descendant match (T2U) | 2 | For Broader rows: the Foundation entity below T1U used in the rule |
| X | Descendant match title | 2 | Title of W |
| Y | Descendant match relation | 2 | Relation of the source to W |
| Z | Proposed mapping rule | 2 | `S ≡ URI`, `S ⊃ URI` or `S ⊂ URI` (S = ICD-10 code) |
| AA | Rule notes | 2 | How W was found, or why there is no rule |
| AB | Confidence | 2 | high / medium / low (see *Confidence* below) |
| AC | Confidence rationale | 2 | The reasons for the grade |

## Stage 1 — Foundation entities and relations

Specification: `addStemCodeRelationPrompt.txt`; rules:
`determine-stemcode-semantic-relationships.md`.

1. **Copy** `rowsWithSuggestedCode-stemCode.xlsx` to
   `rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`.
2. **Foundation entity (column P).** Where P is empty, look up K with
   the `codeinfo` endpoint, fetch its MMS entity and take its `source`
   (the Foundation URI). Residual categories (`.Z`, `…/unspecified`)
   have no `source`; they are mapped to the Foundation entity of their
   parent (the same numeric id).
3. **Relation (columns U, V).**
   - Column M (Corrected Code Mapping Relation) present → U = M,
     V = `Manual`.
   - Column M empty → apply rules 0–7 of
     `determine-stemcode-semantic-relationships.md` to the source title
     (column H) and the Foundation title and synonyms of P. V records
     the rule and the target title.
   - Then apply the medical-knowledge check from the same document. Its
     results are kept in the `MEDICAL_CHECK` table in the script,
     keyed by (ICD-10 code, suggested code), with a reason for each.
     V then reads `Medical-knowledge check: <reason> (rules gave …)`.

## Stage 2 — Proposed mapping rules

Specification: `mappingRulesSpecification.md`, *Rules for a single stem
code*. S = column G (ICD-10 code), T1 = column K, T1U = column P,
relation = column U.

1. **No rule** (reason in AA) when:
   - Action for WHO (column R) does not contain "Update WHO map" or
     start with "Update map";
   - S has the form `X.8` (an ICD-10 "other" residual);
   - there is no Foundation entity; or
   - the relation is Related (left for review).
2. **Equivalent** → `S ≡ T1U`. **Narrower** (target narrower than
   source) → `S ⊃ T1U`.
3. **Broader** → look for a better target T2U among T1U's Foundation
   descendants:
   - Candidate: the MMS `autocode` match for the source title, if it is
     a descendant of T1U; otherwise the best hit of a Foundation search
     for the source title restricted to T1U's subtree. If T1U has no
     descendants or nothing is found → `S ⊂ T1U`.
   - Compare the source with T2U by the stage-1 rules, with three
     guards for candidates below T1U: a candidate that adds content
     words the source lacks is not Broader (rules 1–4 would otherwise
     make it so, e.g. "congenital hydrocephalus" for "hydrocephalus in
     other diseases"); a source naming alternatives ("A or B") is not
     Broader-matched by a candidate naming only one; and "Other
     specified" / "Certain specified" candidates are sibling residuals,
     not containers. Known misjudgements are corrected by the
     `CANDIDATE_CHECK` table in the script (medical-knowledge check).
   - T2U Equivalent → `S ≡ T2U`; T2U Broader → `S ⊂ T2U`.
   - Otherwise climb from T2U through its Foundation parents (within
     T1U's subtree) to the most specific ancestor that is Broader or
     Equivalent, and propose `S ⊂` or `S ≡` that ancestor. Reaching
     T1U gives `S ⊂ T1U`, as stage 1 already found T1U Broader.

Result with MMS 2026-01: 325 rules for 337 rows (183 ≡, 38 ⊃, 104 ⊂);
12 rows without a rule (1 action not "Update map", 3 X.8 sources,
8 Related).

## Stage 3 — Post-coordinated suggestions

Rules: the post-coordinated section of `determine-semantic-relationships.md`;
mapping rules: `mappingRulesSpecification.md`, *Rules for a
post-coordination*.

**Output: `rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx`** — the
post-coordinated rows with these columns filled or added:

| Column | Header | Content |
|---|---|---|
| L | Suggested/Corrected Mapped Code Title | Readable meaning of K (MMS `describe` label), filled where empty |
| P | Suggested/Corrected Mapped Foundation Entity | Foundation expression of K, e.g. `…/477388501 & …/453411773`, filled where empty |
| U | Completed Code Mapping Relation | Equivalent / Broader / Narrower / Related |
| V | Reasoning | `Manual`, the rule, or the medical-knowledge check; plus `Not a valid MMS post-coordination: <reason>` where MMS rejects K |
| W | Precoordinated equivalent (T3U) | Existing Foundation entity equivalent to the source |
| X | T3U title | Title of W |
| Y | New Foundation entity (T4U) definition | `URI(title)&URI(title)/…` |
| Z | Proposed mapping rule | `S ≡ T3U` or `S ≡ T4U[new entity: …]` |
| AA | Rule notes | Why there is or is not a rule |
| AB | Confidence | high / medium / low (see *Confidence* below) |
| AC | Confidence rationale | The reasons for the grade |

1. **Copy** `rowsWithSuggestedCode-postcoordinated.xlsx` to the output
   file. Whitespace around `&` and `/` in K is removed.
2. **Describe K.** The MMS `describe` endpoint returns the readable label,
   the Foundation expression and the stem's Foundation entity. MMS also
   checks the combination against the stem's allowed post-coordination
   axes: when it rejects K (e.g. *"the entity 1A72.1 does not exist in
   any valueset for …"*), the label and Foundation expression are
   assembled code by code and the rejection is recorded in V. With
   2026-01, 155 distinct expressions (169 rows) are not valid MMS
   post-coordinations.
3. **Relation (U, V).** Column M present → `Manual`. Otherwise the
   rules are applied to the source title and the label, followed by
   the medical-knowledge check in the `POSTCOORD_CHECK` table. Two
   conventions drive most judgments:
   - an ICD-10 title "A and B" means A and/or B, whereas an ICD-11
     cluster `A/B` requires both → usually **Narrower**;
   - a dagger title "X in … diseases classified elsewhere" is a cluster
     of the manifestation and the disease → usually **Equivalent**.
4. **Rule (W–AA).** No rule for the stage-2 exclusions (action not
   "Update map", X.8 source) or when the expression contains a code
   ending in Y. Otherwise:
   - search the stem's Foundation subtree for the source title; an
     existing entity that is equivalent to the source (same guards and
     `CANDIDATE_CHECK` table as stage 2) gives `S ≡ T3U`, whatever U is;
   - otherwise, if U is Equivalent, propose a new Foundation entity
     T4U defined by the post-coordination: `S ≡ T4U[new entity: …]`
     (flagged for review when MMS rejected the combination);
   - otherwise no rule (the post-coordination is not equivalent to the
     source).

Result with MMS 2026-01, 300 rows: Equivalent 150, Narrower 80,
Broader 54, Related 16 (179 manual, 121 assessed, of which the
medical-knowledge check changed 96). Rules: 84 (12 `≡` existing
entity, 72 `≡` new entity); no rule 216 (148 contain a Y code, 63 not
equivalent, 4 action not "Update map", 1 X.8 source).

## Confidence

Stages 2 and 3 grade each row in columns AB–AC. The grade refers to the
proposed mapping rule, or, when there is no rule, to the relation in
column U. It starts from how the relation was obtained and is then
adjusted for how the rule's target was found.

**Relation basis**

| Relation obtained from | Grade |
|---|---|
| CIHI reviewers (column M, `Manual`) | high |
| Rule 0 or 5a: titles the same after normalization | high |
| Other mechanical rules (1–6) on titles and synonyms | medium |
| Medical-knowledge check (one reviewer's judgment, not yet confirmed) | medium |
| Rule 7: titles share few words | low |

**Adjustments for the rule**

| Situation | Effect |
|---|---|
| Stage 2: target is a descendant (T2U) with the same title or content words as the source | unchanged |
| Stage 2: target is a descendant found by search and judged mechanically or by the medical-knowledge check | at most medium |
| Stage 2: target is an ancestor reached after the best search match was rejected | one grade lower |
| Stage 3: target is an existing Foundation entity (T3U) with the same title or content words as the source | high |
| Stage 3: existing Foundation entity matched by synonym or partial wording | medium |
| Stage 3: new entity from a CIHI "A and B" cluster `A/B` (except titles that say "both", I13 and N92.0) — ICD-10 "and" usually means either or both | low |

Results with MMS 2026-01: stem codes high 192, medium 114, low 31;
post-coordinations high 175, medium 107, low 18.

Whether MMS accepts a post-coordination does not affect the grade; it is
reported separately in column V.
