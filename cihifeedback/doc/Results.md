# Results: proposed mapping rules

Statistics for the two step-4 output files, from the run against ICD-11
MMS release 2026-01 (October 2026). See `Method.md` for how the relations
and rules are produced and `mappingRulesSpecification.md` for the rule
definitions.

Terms used below:

- **Manual** relation: given by the CIHI reviewers (column M).
  **Inferred**: assigned by the rules of the `determine-*` documents plus
  the medical-knowledge check.
- **T1U**: Foundation entity of CIHI's suggested code. **T2U**: a more
  specific Foundation entity found below T1U. **T3U**: an existing
  Foundation entity equivalent to the source. **T4U**: a proposed new
  Foundation entity defined by the post-coordination.
- **Below the shoreline**: a Foundation entity that is not a category in
  MMS 2026-01 (MMS folds it into a broader category).

## Stem codes — `rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx`

**Entries: 337. With a rule: 325.** No rule for 12: 8 Related, 3 X.8
sources, 1 action not "Update map".

### Relation of the suggested code to the source (column U)

| Relation | Total | Manual | Inferred |
|---|---|---|---|
| Equivalent | 157 | 121 | 36 |
| Broader (target broader than source) | 134 | 89 | 45 |
| Narrower | 38 | 27 | 11 |
| Related | 8 | — | 8 |

### Rules proposed

| Relation | Rule | Manual | Inferred | Total |
|---|---|---|---|---|
| Equivalent | `S ≡ T1U` | 120 | 36 | 156 |
| Narrower | `S ⊃ T1U` | 27 | 11 | 38 |
| Broader | `S ≡ T2U` (more specific entity below T1U) | 15 | 12 | 27 |
| Broader | `S ⊂ T2U` | 58 | 28 | 86 |
| Broader | `S ⊂ T1U` (nothing better found below) | 15 | 3 | 18 |
| **All** | **≡ 183, ⊃ 38, ⊂ 104** | | | **325** |

### Matches below T1U (T2U) and the shoreline

113 Broader rows have a T2U match; 30 of them are below the shoreline.

| Relation of T2U to the source | Below shoreline | Above shoreline |
|---|---|---|
| Equivalent → `S ≡ T2U` | 26 | 1 |
| Broader → `S ⊂ T2U` | 4 | 82 |

Nearly every equivalent match is a Foundation-only entity that MMS folds
into a broader category, for example:

- G21.3 *Postencephalitic parkinsonism* ≡ Foundation "Postencephalitic
  parkinsonism" (in MMS under 8A00.22);
- I21.2 / I21.3 *Acute transmural myocardial infarction of other /
  unspecified sites* ≡ their own Foundation entities (under BA41.0);
- L03.3 *Cellulitis of trunk* ≡ "Cellulitis of trunk, unspecified"
  (under 1B70.Z).

The broader matches are almost all MMS categories. All below-shoreline
matches are direct search hits; none was reached by climbing to a parent.

**Confidence of the 325 rules:** high 190, medium 109, low 26.

## Post-coordinations — `rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx`

**Entries: 300. With a rule: 84.**

### Relation of the post-coordination to the source (column U)

| Relation | Total | Manual | Inferred |
|---|---|---|---|
| Equivalent | 150 | 99 | 51 |
| Broader | 54 | 28 | 26 |
| Narrower | 80 | 52 | 28 |
| Related | 16 | — | 16 |

### Rules proposed

All 84 rules are equivalences (`≡`); no `⊂` or `⊃` rules are proposed
for post-coordinations.

| Rule | Equivalent | Broader | Narrower | Related | Total |
|---|---|---|---|---|---|
| `S ≡ T3U` (existing Foundation entity) | 8 | 1 | 2 | 1 | 12 |
| `S ≡ T4U` (proposed new Foundation entity) | 72 | — | — | — | 72 |

- **Proposed new Foundation entities: 72**, all with distinct logical
  definitions; MMS rejects 35 of those combinations.
- **Existing entities (T3U):** all 12 are below the shoreline, e.g.
  *Dysthyroid exophthalmos*, which MMS folds into 9A20.00.
- **No rule: 216** — 148 contain a Y code; 63 are not equivalent (Broader,
  Narrower or Related, with no existing entity found); 4 have an action
  other than "Update map"; 1 is an X.8 source.

**Confidence of the 84 rules:** high 45, medium 30, low 9.

## Observation

For Broader stem-code suggestions, the search below T1U found a more
precise below-shoreline Foundation entity in 26 cases. The proposed rule
for these is an exact equivalence (`≡`) that MMS itself cannot express,
which makes them the most informative rules to send to WHO.
