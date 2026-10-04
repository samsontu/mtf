# Determining Semantic Relationships Between ICD-10 and ICD-11 Codes

This document defines the rules and process used to assign a semantic
relationship between an ICD-10 source code and an ICD-11 target
(Foundation entity or post-coordinated expression). The output is one
of four labels:

- **Equivalent** — source and target name the same clinical concept.
- **Broader** — the target's scope is wider than the source's.
- **Narrower** — the target's scope is narrower than the source's.
- **Related** — same domain, but the two name materially different
  clinical concepts.

The rules apply equally to single-stem ICD-11 mappings and to
post-coordinated expressions (with `&` extensions or `/` clusters).

## Inputs

| Field | Where it comes from |
|---|---|
| Source code | ICD-10 code (e.g., `K74.5`) |
| Source title | The ICD-10 code's official title, taken literally from the row (no chapter/block context unless it appears in the title itself) |
| Target | Either a Foundation entity (URI + title) or a post-coordinated expression assembled from MMS codes |
| Target synonyms | From the WHO ICD-API for the Foundation entity |
| Target definition / exclusions | From the WHO ICD-API (used for medical sanity-check, not for the mechanical rules) |

## Normalization step

Before any comparison, normalize titles by stripping residual markers
on both source and target:

1. Strip a trailing residual marker: `", unspecified"`, `" NOS"`,
   `" not specified"`, `" not otherwise specified"`.
2. Strip a leading qualifier word: `"Unspecified "` at the start of
   the title.
3. Lower-case for comparison; keep punctuation neutral.

Example: `"Anal fissure, unspecified"` → `"Anal fissure"`;
`"Unspecified abortion, complete or unspecified, without complication"`
→ `"abortion, complete or unspecified, without complication"`.

`"X, unspecified"` and `"Unspecified X"` are treated as `"X"`.

## Rule order

The rules are checked in priority order; the first matching rule
decides the relationship. Rule 0 short-circuits when the medical
content is identical; later rules handle structural qualifiers,
synonyms, and umbrella scopes.

### Rule 0 — exact match after normalization

If, after normalization, the source and target titles are identical
strings, the relationship is **Equivalent**.

### Rule 1 — dagger residual on source

If the source title contains the dagger-style residual phrase
`"in other [...] classified elsewhere"` and the target does not, the
relationship is **Broader**. ICD-10 dagger codes are narrow secondary
manifestations; their ICD-11 mappings are typically the general
parent.

Example: `H03.1` *Involvement of eyelid in other infectious diseases
classified elsewhere* → `Infectious disorders of eyelid` is **Broader**.

### Rule 2 — source starts with "Other" (residual)

`"Other X"` is by convention a residual subset of `"X"` that excludes
named subtypes. Therefore the target (any title that doesn't begin
with `"Other"`) is **Broader** than the source.

Example: `M71.5` *Other bursitis, not elsewhere classified* →
`Bursitis` is **Broader**.

### Rule 3 — source has "not elsewhere classified" residual

Analogous to rule 2. Target is **Broader**.

### Rule 4 — target title signals umbrella scope

If the target title contains `"Certain specified"`,
`"Other specified"`, `"Other and unspecified"`, or
`"Other or unspecified"`, it is an umbrella category that covers
several specified entities, of which the source is one. The
relationship is **Broader**, regardless of any synonym match.

Example: `K74.5` *Biliary cirrhosis, unspecified* →
`Certain specified fibrosis or cirrhosis of liver` is **Broader**.

### Rule 5 — content-word set comparison

Extract content words from both normalized titles (drop English
function words and ICD framing words like *of, or, and, in, the,
behaviour, specified, unspecified, NOS, involvement, elsewhere,
classified, not*).

- **5a.** Same content-word set → **Equivalent**. Catches rephrasings
  and word-order changes (`"Neoplasm of uncertain or unknown behaviour:
  Breast"` ≡ `"Neoplasms of uncertain behaviour of breast"`).
- **5b.** Source content words ⊂ target content words and the target
  adds at least one qualifier → **Narrower**. The target is a more
  specific subtype.
- **5c.** Target content words ⊂ source content words → **Broader**.
  The source has a qualifier the target lacks.

### Rule 6 — synonym match (with caveats)

If the normalized source title matches any **synonym** of the target
Foundation entity (case-insensitive, residual markers stripped):

- **6a.** If rule 4 already decided Broader (umbrella target), keep
  Broader — a synonym in an umbrella entry is more like an inclusion
  and does not promote to Equivalent.
- **6b.** If rule 5b already decided Narrower (target adds qualifier),
  keep Narrower — a synonym in a more-specific entity reflects coding
  convention only, not scope equivalence.
- **6c.** Otherwise classify as **Equivalent**. The target is the
  intended ICD-11 coding home for the source concept.

Crucial caveat: only the target's `synonym` list counts — `inclusion`
entries are not used, because inclusions may be narrower terms grouped
under the target rather than equivalent labels.

Example (synonym → Equivalent): `G24.5` *Blepharospasm* →
`Movement disorders of eyelid` is **Equivalent** because the target
lists `blepharospasm NOS` as a synonym.

Example (synonym blocked by 5b → Narrower): `G47.3` *Sleep apnoea* →
`Obstructive sleep apnoea` is **Narrower** despite the synonym
`sleep apnoea NOS`, because the target's title carries the extra
qualifier `obstructive`.

### Rule 7 — partial-overlap fallback

If none of the above match, fall back on content-word overlap:

- Substantial overlap (common words ≥ smaller-set size) → **Equivalent**.
- Some overlap but each side carries its own distinguishing words →
  **Related**.
- No overlap → **Related**.

## Medical-knowledge sanity check

After the rule engine assigns a relationship, an **independent
medical-knowledge check** is applied:

1. Read the source title, target title, target definition (if
   available), and the relationship.
2. Ask: does the assigned relationship reflect actual clinical
   semantics?

The check most commonly fires on **rule 6c (synonym-equivalent)
cases**, when the WHO Foundation has consolidated multiple clinically
distinct conditions under a single entity name. If the source and
target name clinically distinct phenomena, downgrade
**Equivalent → Related**.

Example: `R20.2` *Paraesthesia of skin* → `Anaesthesia of skin`.
Rule 6c marks Equivalent because paraesthesia appears in the target's
synonym list, but **paraesthesia (abnormal sensation) and anaesthesia
(loss of sensation) are clinically distinct phenomena** with different
mechanisms and different ICD-10 codes. The medical check demotes the
classification to **Related**.

Other forms of medical sanity-check:

- Word-stem or morphological equivalence not captured by the rules
  (e.g., `"Osteopathy after poliomyelitis"` ≡
  `"Postpoliomyelitic osteopathy"`) — promote to Equivalent.
- Anatomical synonymy (e.g., `"lower limb"` ≡ `"leg"` in injury
  classifications) — usually promote to Equivalent or adjust scope.
- Eponym vs descriptor pairs (e.g., `"Tietze [chondrocostal junction
  syndrome]"` ≡ `"Costochondritis"`) — promote to Equivalent.
- True parent/child relationships missed by content-word set
  comparison (e.g., `"Degeneration of nervous system due to alcohol"`
  vs `"Brain degeneration in alcoholism"`: brain is part of nervous
  system → target Narrower).
- Broader categories where the source is a specific instance not
  detected by the rules (e.g., `"Nonorganic dyspareunia"` →
  `"Sexual pain disorders"`: target is broader category → Broader).

## Post-coordinated expressions

A post-coordinated expression in ICD-11 MMS is a combination of:

- a stem code (e.g., `BA41.0`)
- one or more extension codes joined by `&` (e.g., `&XA3RM8`)
- or one or more additional stem codes joined by `/` (a cluster)

The relationship between the ICD-10 source and a post-coordinated
expression is determined by comparing the source title to the assembled
post-coord meaning:

1. Build a human-readable expression in the form
   `StemCode(MMS title)&ExtensionCode(extension title)&…` or
   `StemCode(title)/StemCode(title)`. Stem and extension titles come
   from the ICD-API:
   - Stem code title → `/icd/release/11/{release}/mms/codeinfo/{code}`
     returns the stem MMS URI; fetch that URI for the
     MMS-linearization title (this is the title that matters for
     post-coord, not the foundation title).
   - Extension code (`Xnnnn…`) title → same `codeinfo` lookup; fetch
     the resulting URI for the title.
2. Compare the source title to the assembled meaning, applying the
   normal scope rules:
   - If the assembled meaning exactly captures the source concept →
     **Equivalent**.
   - If the assembled meaning is more specific (e.g., the stem adds
     "Chronic" via extension where source covers chronic-or-unspecified)
     → **Narrower**.
   - If the assembled meaning is broader (e.g., the stem alone names a
     larger category) → **Broader**.

In practice, well-formed post-coordinated mappings are designed to
reconstruct the ICD-10 concept faithfully, so **Equivalent** is the
typical outcome. The exceptions are mostly cases where the extension
forces a sub-scope the ICD-10 code does not require.

## Worked examples

### Title equality (Rule 0)

- `Pyoderma` → `Pyoderma`: **Equivalent**.

### Residual stripping (normalization + Rule 5a)

- `Anal fissure, unspecified` → `Anal fissure`: **Equivalent** after
  stripping `", unspecified"`.

### "Other X" → "X" (Rule 2)

- `Other bursitis, not elsewhere classified` → `Bursitis`: **Broader**.

### Dagger residual (Rule 1)

- `Hydrocephalus in other diseases classified elsewhere` →
  `Hydrocephalus`: **Broader**.

### Umbrella target (Rule 4)

- `Biliary cirrhosis, unspecified` →
  `Certain specified fibrosis or cirrhosis of liver`: **Broader**.

### Synonym promotes Broader to Equivalent (Rule 6c)

- `Blepharospasm` → `Movement disorders of eyelid` (synonym
  `blepharospasm NOS`): **Equivalent**.

### Synonym blocked by Narrower (Rule 6b)

- `Sleep apnoea` → `Obstructive sleep apnoea` (synonym
  `sleep apnoea NOS`): **Narrower** — target's title adds
  `obstructive`.

### Medical-knowledge override

- `Paraesthesia of skin` → `Anaesthesia of skin` (synonym
  `Paraesthesia of skin`): the rule engine returns Equivalent, but
  the medical check downgrades to **Related** because paraesthesia and
  anaesthesia are clinically distinct phenomena.

### Post-coordinated expression

- ICD-10 `D40.1` *Neoplasm of uncertain or unknown behaviour: Testis*
  → post-coord `2F77&XA4947`
  = `2F77(Neoplasms of uncertain behaviour of male genital organs)`
    `&XA4947(Testis)`: **Equivalent** — the extension code pins the
  stem to the testis specifically, reconstructing the ICD-10 concept.

- ICD-10 `K26.5` *Duodenal ulcer: chronic or unspecified with
  perforation* → post-coord `DA63.Y&XT8W`
  = `DA63.Y(Other specified duodenal ulcer)&XT8W(Chronic)`:
  **Narrower** — the extension forces the chronic case; the ICD-10
  code includes both chronic and unspecified-duration perforated
  ulcers.

## Output

For every row of the matching file, two columns are written:

- **Column U** *Foundation IRI Relation to ICD10 code* — the
  relationship label (Equivalent / Broader / Narrower / Related).
- **Column V** *Reasoning* — a short justification referencing the
  rule(s) used and any sanity-check considerations.
