# Specification: proposed Foundation mapping rules

This document specifies how proposed ICD-10 → ICD-11 Foundation mapping
rules are derived from CIHI's corrected maps. It is implemented by step 4
of the pipeline, `bin/generateMappingRelationsAndRules.py`: stage 2 for
suggestions that are a single stem code, stage 3 for post-coordinated
suggestions. `Method.md` describes the implementation and its results.

An earlier version of this specification was derived from
`originalMappingRulesGenerationPrompt.txt`; see *History* at the end.

## Notation

| Symbol | Meaning |
|---|---|
| S | ICD-10 source code (feedback column G) |
| T1 | CIHI's suggested ICD-11 MMS code or post-coordination (column K) |
| T1U | Foundation entity of T1 (column P); for a post-coordination, its Foundation expression |
| T2U | A Foundation entity below T1U that matches S more closely |
| T3U | An existing Foundation entity, under T1's stem, equivalent to S |
| T4U | A proposed new Foundation entity whose logical definition is the post-coordination T1 |
| `S ≡ X` | S is equivalent to X |
| `S ⊂ X` | X is broader than S (S is a subtype of X) |
| `S ⊃ X` | X is narrower than S |

Relations are those of `determine-stemcode-semantic-relationships.md`
(stem codes) and `determine-semantic-relationships.md` (post-coordinations):
Equivalent, Broader (target broader than source), Narrower, Related.

## Input

The step-4 stage-1 results, not the raw CIHI workbook: the
still-actionable feedback rows (after removing those already fixed in the
2026 release) that have a suggested code, split by kind of code in step 3.

- **Stem codes:** `rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`,
  with T1U (column P) and the completed relation of S to T1U (column U).
- **Post-coordinations:** `rowsWithSuggestedCode-postcoordinated.xlsx`;
  T1U and the relation are assigned in the same stage as the rules.
- **Not covered:** suggestions that are a single "other specified" code
  ending in Y (`rowsWithSuggestedCode-Ytargets.xlsx`).

The relation used is the **completed relation (column U)**: CIHI's own
relation (column M) where present; otherwise the rules of the relevant
`determine-*` document followed by a medical-knowledge check.

## Exclusions — no rule is proposed when

1. Action for WHO (column R) does not contain "Update WHO map" and does
   not start with "Update map";
2. S has the form `X.8` (an ICD-10 "other specified" residual, whose
   meaning depends on its siblings);
3. T1 contains a code ending in Y (post-coordinations only; single Y
   codes are excluded by the input);
4. T1 cannot be resolved to a Foundation entity.

Each excluded row records the reason.

## Rules for a single stem code (T1 = one MMS code)

| Relation of S to T1U | Rule |
|---|---|
| Equivalent | `S ≡ T1U` |
| Narrower | `S ⊃ T1U` |
| Related | No rule (left for review) |
| Broader | Look for T2U below T1U, as follows |

**Broader.** T1U is broader than S, so a more specific Foundation entity
may fit S:

1. Candidate T2U: the MMS `autocode` match for S's title if it is a
   descendant of T1U; otherwise the best Foundation search hit for S's
   title within T1U's subtree. No descendants or no hit → `S ⊂ T1U`.
2. Compare S with T2U using the same rules, with three guards for
   candidates below T1U:
   - a candidate that adds content words S lacks (e.g. "congenital",
     "noninfectious") is not Broader than S;
   - if S names alternatives ("A or B"), a candidate naming only one of
     them is Narrower, not Broader;
   - "Other specified" / "Certain specified" candidates are sibling
     residuals, never containers of S.
3. T2U Equivalent → `S ≡ T2U`; T2U Broader → `S ⊂ T2U`.
4. Otherwise climb from T2U through its Foundation parents, within T1U's
   subtree, to the most specific ancestor that is Broader than or
   Equivalent to S, and propose `S ⊂` or `S ≡` that ancestor. Reaching
   T1U gives `S ⊂ T1U`.

## Rules for a post-coordination (T1 contains `&` or `/`)

1. **Describe T1** with the MMS `describe` endpoint to obtain its readable
   meaning, its Foundation expression and its stem's Foundation entity.
   If MMS rejects the combination (an axis value not allowed for the
   stem), assemble the meaning and Foundation expression code by code
   and record the rejection; this does not by itself prevent a rule.
2. **Relation of S to T1**, with two conventions:
   - ICD-10 "A and B" means A and/or B, whereas the cluster `A/B`
     requires both — usually Narrower;
   - a dagger title "X in … diseases classified elsewhere" is a cluster
     of the manifestation and the disease — usually Equivalent.
3. **Rule:**
   - an existing Foundation entity T3U under T1's stem that is
     equivalent to S (Foundation search for S's title, same guards as
     above) → `S ≡ T3U`, whatever the relation of S to T1;
   - otherwise, if S is Equivalent to T1 → `S ≡ T4U`, a new Foundation
     entity whose logical definition is T1's Foundation expression,
     written `URI(title)&URI(title)/…`;
   - otherwise no rule (T1 is not equivalent to S).

## Medical-knowledge checks

Automatic judgments are reviewed clinically. Corrections are recorded
with a reason, keyed by (S, T1) for relations and by (S, candidate URI)
for T2U/T3U candidates, and override the automatic result. Two examples:
"Paraesthesia of skin" is not equivalent to "Anaesthesia of skin"
despite a WHO synonym; "Traumatic amputation of forearm" is broader than
"Traumatic amputation at elbow level", although WHO lists the latter as a
synonym.

## Confidence

Every row is graded high, medium or low, with a rationale. The grade
starts from how the relation was obtained (CIHI reviewers or identical
titles: high; other rules or the medical-knowledge check: medium; weak
word overlap: low) and is adjusted for how the rule's target was found
(see `Method.md`, *Confidence*). Whether MMS accepts a post-coordination
does not affect the grade.

## Output

Per row: the relation and its reasoning; the T2U, T3U or T4U used, if
any; the proposed rule (`S ≡ X`, `S ⊂ X` or `S ⊃ X`) or the reason for
none; and the confidence with its rationale. Column layouts are given in
`Method.md`, step 4.

## History

An earlier version of this specification was derived from
`originalMappingRulesGenerationPrompt.txt` and implemented by
`bin/legacy/generateMappingRulesFromSource.py` (output
`legacy/ProposedMappingRules.xlsx/.csv`, not part of the pipeline). It
differed from the current specification in that it:

- read the CIHI review workbook directly, choosing T1 from the Conflict
  Resolution team decision ("CIHI map correct" → CIHI's code; "Neither
  correct" → the review team's code), instead of the still-actionable
  feedback produced by steps 1–3;
- took the relation from CIHI's E/B/N equivalence column, or computed it
  by rule, without the medical-knowledge checks;
- proposed `S ≡ T3U` or `S ≡ T4U` for every post-coordination, without
  assessing whether the post-coordination is equivalent to S;
- had no guards on descendant matches, no record of MMS validity, and no
  confidence grading.
