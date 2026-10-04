#!/usr/bin/env python3
"""
Step 4: mapping relations and proposed Foundation mapping rules for the
suggested codes split out in step 3.
  Stages 1-2: single stem codes  rowsWithSuggestedCode-stemCode.xlsx
                                 -> rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx
  Stage 3:    post-coordinations rowsWithSuggestedCode-postcoordinated.xlsx
                                 -> rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx

Stage 1 - Foundation entities and relations
  Specification: doc/addStemCodeRelationPrompt.txt
  Rules:         doc/determine-stemcode-semantic-relationships.md
  1. Copy rowsWithSuggestedCode-stemCode.xlsx to the output file.
  2. Fill column P (Suggested/Corrected Mapped Foundation Entity), where
     empty, with the Foundation URI of K (WHO ICD-API).
  3. Add column U "Completed Code Mapping Relation" and V "Reasoning":
     column M present -> U = M, V = "Manual"; otherwise rules 0-7 on the
     source title (H) vs the Foundation title and synonyms of P, then the
     medical-knowledge check in MEDICAL_CHECK.

Stage 2 - proposed mapping rules
  Specification: doc/mappingRulesSpecification.md, "Rules for a single stem
  code" (S = G, T1 = K, T1U = P, relation = U).
  1. No rule when Action for WHO (R) is not "Update (WHO) map", or S is an
     X.8 residual, or there is no Foundation entity.
  2. Equivalent -> S ≡ T1U;  Narrower -> S ⊃ T1U.
  3. Broader -> find the best match T2U among T1U's Foundation descendants
     (MMS autocode, falling back to a Foundation search within T1U's
     subtree) and compare S with T2U by the same rules:
       Equivalent -> S ≡ T2U;  Broader -> S ⊂ T2U;
       otherwise climb from T2U to the most specific ancestor (within the
       T1U subtree) that is Broader or Equivalent, and use it.
     No match in the subtree -> S ⊂ T1U.
  4. Related -> no rule (for review).
  Adds columns W-AA: Descendant match (T2U), its title, its relation,
  Proposed mapping rule, Rule notes; and AB-AC: Confidence (high / medium /
  low) and Confidence rationale (see grade_stem()).

Stage 3 - post-coordinated suggestions
  Rules: doc/determine-semantic-relationships.md (post-coordinated section);
  mapping rules: doc/mappingRulesSpecification.md, "Rules for a
  post-coordination".
  1. Copy rowsWithSuggestedCode-postcoordinated.xlsx to the output file.
  2. MMS describe of K fills L (title) and P (Foundation expression). If MMS
     rejects the combination, the expression is assembled code by code and
     the API's reason is added to V ("Not a valid MMS post-coordination").
  3. U, V: column M present -> Manual; otherwise rules 0-7 on the source
     title vs the describe label, then the medical-knowledge check in
     POSTCOORD_CHECK.
  4. Rule (W-AA): same exclusions as stage 2, plus expressions containing a
     code ending in Y. An existing Foundation entity under the stem that is
     equivalent to the source (T3U, by Foundation search) -> S ≡ T3U;
     otherwise, if U is Equivalent -> S ≡ T4U[new entity defined by the
     post-coordination]; otherwise no rule.
  5. Confidence and rationale (AB-AC), see grade_pc().

Usage
-----
  python3 bin/generateMappingRelationsAndRules.py                  # confirm latest release
  python3 bin/generateMappingRelationsAndRules.py --release 2026-01
  python3 bin/generateMappingRelationsAndRules.py --stage 2         # rules only, from the
                                                             # existing stage-1 output
  python3 bin/generateMappingRelationsAndRules.py --stage 3         # post-coordinated rows only
"""

import argparse
import re
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from datetime import date
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

import icdapi  # bin/icdapi.py: WHO ICD-API helpers

WORKDIR = Path(__file__).resolve().parent.parent  # cihifeedback/ (data files)
SRC     = WORKDIR / "rowsWithSuggestedCode-stemCode.xlsx"   # from step 3
OUT_REL = WORKDIR / "rowsWithSuggestedCode-stemCode-relationsAndRules.xlsx"
SRC_PC  = WORKDIR / "rowsWithSuggestedCode-postcoordinated.xlsx"   # from step 3
OUT_PC  = WORKDIR / "rowsWithSuggestedCode-postcoordinated-relationsAndRules.xlsx"

# Column numbers (1-based) in the WHO feedback template layout
COL_H, COL_K, COL_L, COL_M, COL_P = 8, 11, 12, 13, 16
COL_R, COL_U, COL_V = 18, 21, 22
COL_T2U, COL_T2T, COL_T2R, COL_RULE, COL_NOTE = 23, 24, 25, 26, 27
COL_CONF, COL_CONF_WHY = 28, 29

ap = argparse.ArgumentParser(description="Step 4: stem-code mapping relations")
ap.add_argument("--release", help="ICD-11 MMS release id (e.g. 2026-01); skips the prompt")
ap.add_argument("--stage", choices=["1", "2", "3", "all"], default="all",
                help="run one stage, or all (default)")
args = ap.parse_args()


def clean(v):
    return unicodedata.normalize("NFKC", str(v or "")).strip()


# ------------------------------------------------------------------
# Rules from determine-stemcode-semantic-relationships.md
# ------------------------------------------------------------------
STOP = {"of", "or", "and", "in", "the", "behaviour", "behavior", "specified",
        "unspecified", "nos", "involvement", "elsewhere", "classified", "not"}
UMBRELLA = r"certain specified|other specified|other and unspecified|other or unspecified"


def norm(t):
    t = unicodedata.normalize("NFKC", t or "").strip()
    t = re.sub(r",?\s*(unspecified|NOS|not specified|not otherwise specified)\s*$", "", t, flags=re.I)
    t = re.sub(r"^unspecified\s+", "", t, flags=re.I)
    return t.lower().strip(" ,.")


def words(t):
    return {w for w in re.findall(r"[a-z0-9]+", t) if w not in STOP}


def relationship(src_title, tgt_title, synonyms):
    """Return (relation, reasoning) by rules 0-7, first match wins."""
    s, t = norm(src_title), norm(tgt_title)
    if not t:
        return "", "No Foundation title found for the suggested code"
    if s == t:
        return "Equivalent", "Rule 0: titles identical after normalization"
    dagger = r"in other .*classified elsewhere"
    if re.search(dagger, s) and not re.search(dagger, t):
        return "Broader", "Rule 1: source is a dagger residual ('in other ... classified elsewhere')"
    if s.startswith("other "):
        return "Broader", "Rule 2: source is an 'Other X' residual, target is X"
    if "not elsewhere classified" in (src_title or "").lower():
        return "Broader", "Rule 3: source is a 'not elsewhere classified' residual"
    if re.search(UMBRELLA, t):
        return "Broader", "Rule 4: target title is an umbrella category"
    ws, wt = words(s), words(t)
    if ws and ws == wt:
        return "Equivalent", "Rule 5a: same content words"
    rule5 = None
    if ws and ws < wt:
        extra = ", ".join(sorted(wt - ws))
        rule5 = ("Narrower", f"Rule 5b: target adds qualifier ({extra})")
    elif wt and wt < ws:
        extra = ", ".join(sorted(ws - wt))
        rule5 = ("Broader", f"Rule 5c: source adds qualifier ({extra})")
    syn = next((x for x in synonyms if norm(x) == s), None)
    if syn:
        if rule5 and rule5[0] == "Narrower":
            return "Narrower", f"Rule 6b: source matches target synonym '{syn}', but {rule5[1][9:]}"
        return "Equivalent", f"Rule 6c: source matches target synonym '{syn}'"
    if rule5:
        return rule5
    common = ws & wt
    if common and len(common) >= min(len(ws), len(wt)):
        return "Equivalent", "Rule 7: substantial content-word overlap"
    return "Related", "Rule 7: partial or no content-word overlap"


# Medical-knowledge check (determine-stemcode-semantic-relationships.md):
# rows where the rules' result does not reflect clinical meaning, keyed by
# (ICD-10 code, suggested code) -> (relation, reason).
MEDICAL_CHECK = {
    # Same concept, different wording or modern terminology -> Equivalent
    ("D50.0", "3A00.01"): ("Equivalent", "chronic posthaemorrhagic anaemia is iron deficiency anaemia secondary to chronic blood loss"),
    ("F12.5", "6C41.6"): ("Equivalent", "cannabinoid psychotic disorder = cannabis-induced psychotic disorder"),
    ("F64.9", "HA6Z"): ("Equivalent", "gender incongruence is the ICD-11 term for gender identity disorder"),
    ("L50.1", "EB00.Z"): ("Equivalent", "idiopathic urticaria = spontaneous urticaria"),
    ("M35.0", "4A43.2Z"): ("Equivalent", "sicca syndrome [Sjögren] is Sjögren syndrome"),
    ("M53.9", "FB1Z"): ("Equivalent", "dorsopathy = condition of the spine"),
    ("M67.9", "FB4Z"): ("Equivalent", "same concept; 'and' vs 'or', singular vs plural"),
    ("M79.9", "FB6Z"): ("Equivalent", "same concept; singular vs plural"),
    ("M89.0", "MG30.04"): ("Equivalent", "algoneurodystrophy is an older name for complex regional pain syndrome"),
    ("N39.9", "GC2Z"): ("Equivalent", "disorder of urinary system = disease of urinary system"),
    ("O65.4", "JB05.4"): ("Equivalent", "same title; fetopelvic vs foetopelvic spelling"),
    ("O75.9", "JB0Z"): ("Equivalent", "same concept; 'and' vs 'or', singular vs plural"),
    ("Q20.5", "LA85.0Z"): ("Equivalent", "same concept; singular vs plural"),
    ("H32.0", "9B65.1"): ("Equivalent", "chorioretinal inflammation due to infection is infectious posterior uveitis"),
    # Target is a parent category of the source -> Broader
    ("D82.8", "4B4Z"): ("Broader", "target is the whole immune-system chapter"),
    ("F64.0", "HA6Z"): ("Broader", "transsexualism corresponds to gender incongruence of adolescence or adulthood; target also covers childhood"),
    ("F95.1", "8A05.0Z"): ("Broader", "chronic motor or vocal tic disorder is one kind of primary tic disorder"),
    ("H44.5", "9C2Z"): ("Broader", "degenerated globe is one disorder of the eyeball"),
    ("I78.9", "BE2Z"): ("Broader", "target is the whole circulatory-system chapter"),
    ("L03.3", "1B70.Z"): ("Broader", "cellulitis of trunk is one site of bacterial cellulitis"),
    ("L85.9", "ME66.1"): ("Broader", "epidermal thickening is one change in skin texture"),
    ("M00.0", "FA10.0"): ("Broader", "staphylococcal arthritis is one bacterial joint infection"),
    ("M00.1", "FA10.0"): ("Broader", "pneumococcal arthritis is one bacterial joint infection"),
    ("M42.9", "FB82.1"): ("Broader", "target is osteochondrosis at any site, not only the spine"),
    ("N73.2", "GA05.Z"): ("Broader", "parametritis and pelvic cellulitis are female pelvic inflammatory diseases"),
    ("T82.7", "NE83.1"): ("Broader", "target covers infection from any device, implant or graft"),
    ("Z46.2", "QB3Z"): ("Broader", "target covers fitting of any device"),
    ("F51.2", "7A6Z"): ("Broader", "target covers circadian sleep-wake disorders of any cause, not only nonorganic"),
    ("Q33.4", "LA74.Z"): ("Broader", "congenital bronchiectasis is one developmental anomaly of the bronchi"),
    ("I13.9", "BA00.Z"): ("Broader", "hypertensive heart and renal disease is coded under essential hypertension, which covers more"),
    ("M60.9", "FB3Z"): ("Broader", "myositis is one disorder of muscle"),
    ("S14.6", "NA4Z"): ("Broader", "source is an 'other and unspecified' residual of nerve injuries of neck"),
    ("T13.4", "ND55"): ("Broader", "target covers other injuries of leg, including blood-vessel injury"),
    ("T86.0", "NE84"): ("Broader", "bone-marrow transplant rejection is one transplant failure or rejection"),
    ("V79.6", "PA05"): ("Broader", "target covers any transport event injuring a bus occupant"),
    ("M89.9", "FC0Z"): ("Broader", "target is the whole musculoskeletal chapter"),
    ("Q51.9", "LB4Z"): ("Broader", "uterus and cervix are part of the female genital system"),
    ("H75.0", "AB11.3"): ("Broader", "source is a dagger residual (mastoiditis in diseases classified elsewhere)"),
    ("T96", "NE6Z"): ("Broader", "sequelae of drug poisoning are one kind of harmful effect of substances"),
    ("W49", "PB6Z"): ("Broader", "target covers any unintentional cause"),
    ("M66.4", "FB41.2"): ("Broader", "source is an 'other tendons' residual of spontaneous tendon rupture"),
    # Target covers only part of the source -> Narrower
    ("C78.6", "2D90"): ("Narrower", "target covers retroperitoneum only; source also covers peritoneum"),
    ("F15.3", "6C46.4"): ("Narrower", "target excludes caffeine withdrawal, which the source includes"),
    ("F19.1", "6C4F.1Z"): ("Narrower", "target covers multiple specified substances only; source also covers other psychoactive substances"),
    ("L08.9", "1B7Z"): ("Narrower", "target covers pyogenic bacterial infection only; source covers any local skin infection"),
    ("S93.1", "ND14.2Z"): ("Narrower", "target excludes the great toe"),
    ("T21.7", "ND92.3"): ("Narrower", "target excludes perineum and genitalia, which ICD-10 T21 includes"),
    ("W22", "PA82"): ("Narrower", "target covers striking a stationary object only; source also covers being struck by objects"),
    ("V86.9", "PA1D"): ("Narrower", "target covers all-terrain vehicles only; source also covers other off-road vehicles"),
    ("S61.9", "NC52.1Z"): ("Narrower", "target covers 'other parts' only; source covers any part of wrist and hand"),
    # Clinically distinct -> Related
    ("F19.6", "6D72.12"): ("Related", "multiple-drug amnesic syndrome vs amnestic disorder due to one other specified substance"),
    ("Y83.1", "PK9C.2"): ("Related", "source is a surgical procedure as cause; target is a device category"),
    ("P05.0", "KA21.2Z"): ("Related", "light for gestational age (weight for age) differs from low birth weight (absolute weight)"),
}


def set_header(ws, col, name, width):
    """Header cell styled like column T's header."""
    cell = ws.cell(1, col, name)
    cell._style = ws.cell(1, 20)._style
    ws.column_dimensions[cell.column_letter].width = width


# ------------------------------------------------------------------
# Stage 1: Foundation entities and relations
# ------------------------------------------------------------------
def stage1(sess, release):
    shutil.copyfile(SRC, OUT_REL)
    wb = load_workbook(OUT_REL)
    ws = data_sheet(wb)
    rows = [r for r in range(2, ws.max_row + 1) if ws.cell(r, COL_K).value is not None]
    codes = sorted({clean(ws.cell(r, COL_K).value) for r in rows})
    with ThreadPoolExecutor(12) as ex:
        fnd = dict(zip(codes, ex.map(lambda c: icdapi.foundation_of(sess, release, c), codes)))

    set_header(ws, COL_U, "Completed Code Mapping Relation", 30)
    set_header(ws, COL_V, "Reasoning", 70)

    n_manual = n_rules = n_med = n_nofnd = 0
    for r in rows:
        g = clean(ws.cell(r, 7).value)
        k = clean(ws.cell(r, COL_K).value)
        uri, title, syns = fnd[k]
        if not ws.cell(r, COL_P).value and uri:
            ws.cell(r, COL_P, uri)
        if not uri:
            n_nofnd += 1
        m = ws.cell(r, COL_M).value
        if m not in (None, ""):
            rel, why = str(m).strip(), "Manual"
            n_manual += 1
        else:
            rel, why = relationship(ws.cell(r, COL_H).value, title, syns)
            why = f"{why}. Target: '{title}'" if title else why
            if (g, k) in MEDICAL_CHECK:
                new, reason = MEDICAL_CHECK[(g, k)]
                why = f"Medical-knowledge check: {reason} (rules gave {rel or 'none'}: {why})"
                rel = new
                n_med += 1
            n_rules += 1
        ws.cell(r, COL_U, rel)
        ws.cell(r, COL_V, why)

    wb.save(OUT_REL)
    print(f"Stage 1: wrote {len(rows)} rows -> {OUT_REL}")
    print(f"  Manual (column M): {n_manual}; by rules: {n_rules} "
          f"(medical-knowledge check changed {n_med}); no Foundation entity: {n_nofnd}")


# ------------------------------------------------------------------
# Stage 2: proposed mapping rules
# ------------------------------------------------------------------
def rel_to_candidate(s_title, ent):
    """Relation of the source to a candidate Foundation entity (T2U or an
    ancestor), by the same rules plus two guards that matter when searching
    below T1U:
      - Rules 1-3 (source is a residual) and 5c make any target Broader. A
        candidate that adds content words the source lacks (e.g.
        'congenital', 'noninfectious') is not Broader; it is Related.
      - A source naming alternatives ('A or B') is not Broader-matched by a
        candidate that names only one of them (rule 5c); it is Narrower.
      - 'Other specified' / 'Certain specified' candidates are sibling
        residuals, not containers of the source; they are Related."""
    rel, why = relationship(s_title, ent["title"], ent["synonyms"])
    if re.match(r"(other|certain) specified", norm(ent["title"])) \
            and not norm(s_title).startswith("other"):
        return "Related"  # a sibling residual, not a container of the source
    if rel != "Broader":
        return rel
    src_w = words(norm(s_title)) - {"other"}
    added = words(norm(ent["title"])) - src_w - {"other", "diseases", "disease",
                                                  "disorders", "disorder", "conditions"}
    if why.startswith(("Rule 1", "Rule 2", "Rule 3", "Rule 4")) and added:
        return "Related"
    if why.startswith("Rule 5c") and re.search(r"\bor\b", norm(s_title)):
        return "Narrower"
    return rel


# Medical-knowledge check of candidate Foundation entities found by search
# (stage 2 descendant matches T2U, stage 3 existing entities T3U):
# (ICD-10 code, candidate URI) -> (relation, reason). Overrides
# rel_to_candidate() for that candidate.
CANDIDATE_CHECK = {
    ("G44.0", "http://id.who.int/icd/entity/760621151"):
        ("Equivalent", "cluster headache syndrome is cluster headache"),
    ("I41.2", "http://id.who.int/icd/entity/990536354"):
        ("Narrower", "parasitic myocarditis excludes the infectious, non-parasitic cases"),
    ("L50.0", "http://id.who.int/icd/entity/1358947933"):
        ("Narrower", "target is acute IgE-mediated urticaria only"),
    ("S58.0", "http://id.who.int/icd/entity/619727205"):
        ("Broader", "amputation of forearm includes, but is not limited to, the elbow level"),
}


def find_t2(sess, release, s_title, t1u, subtree):
    """Best match for the source among T1U's descendants: (uri, how) or (None, why)."""
    ac = icdapi.autocode(sess, release, s_title)
    acu = (ac.get("foundationURI") or "")
    acu = re.sub(r"/(unspecified|other)$", "", acu)
    if acu in subtree and acu != t1u:
        return acu, f"T2 via autocode (score {ac.get('matchScore')})"
    for uri, _ in icdapi.subtree_search(sess, s_title, t1u):
        if uri in subtree and uri != t1u:
            return uri, "T2 via Foundation search in T1U subtree"
    return None, "no match among T1U's descendants"


def propose_rule(sess, release, s, s_title, t1u, pred, action):
    """Return (T2U, T2U title, T2U relation, rule, notes) for one row."""
    a = (action or "").strip().lower()
    if not ("update who map" in a or a.startswith("update map")):
        return "", "", "", "", f"No rule: Action for WHO is '{action}', not 'Update (WHO) map'"
    if re.fullmatch(r"[A-Z]\d\d\.8", s):
        return "", "", "", "", "No rule: ICD-10 source is an X.8 'other' residual"
    if not t1u:
        return "", "", "", "", "No rule: no Foundation entity for the suggested code"
    if pred == "Equivalent":
        return "", "", "", f"{s} ≡ {t1u}", ""
    if pred == "Narrower":
        return "", "", "", f"{s} ⊃ {t1u}", ""
    if pred != "Broader":
        return "", "", "", "", f"No rule: relation is '{pred}'; review"

    t1 = icdapi.foundation_entity(sess, t1u)
    subtree = set(t1["descendant"])
    if not subtree:
        return "", "", "", f"{s} ⊂ {t1u}", "T1U has no descendants"
    t2u, how = find_t2(sess, release, s_title, t1u, subtree)
    if not t2u:
        return "", "", "", f"{s} ⊂ {t1u}", how
    t2 = icdapi.foundation_entity(sess, t2u)
    p2 = rel_to_candidate(s_title, t2)
    if (s, t2u) in CANDIDATE_CHECK:
        p2, reason = CANDIDATE_CHECK[(s, t2u)]
        how += f"; medical-knowledge check: {reason}"
    if p2 == "Equivalent":
        return t2u, t2["title"], p2, f"{s} ≡ {t2u}", how
    if p2 == "Broader":
        return t2u, t2["title"], p2, f"{s} ⊂ {t2u}", how
    # Climb from T2U to the most specific ancestor in the T1U subtree that is
    # Broader than (or Equivalent to) the source.
    within = subtree | {t1u}
    cur = t2u
    for _ in range(12):
        parents = icdapi.foundation_entity(sess, cur)["parent"]
        nxt = next((p for p in parents if p in within), None)
        if not nxt:
            break
        anc = icdapi.foundation_entity(sess, nxt)
        # Back at T1U: stage 1 already decided T1U is Broader than the source.
        pa = "Broader" if nxt == t1u else rel_to_candidate(s_title, anc)
        if pa in ("Broader", "Equivalent"):
            sym = "≡" if pa == "Equivalent" else "⊂"
            return (nxt, anc["title"], pa, f"{s} {sym} {nxt}",
                    f"{how}; T2 ({t2['title']}) was {p2 or 'unresolved'}, "
                    "reset to the most specific broader ancestor")
        cur = nxt
    return "", "", "", f"{s} ⊂ {t1u}", f"{how}; no broader ancestor below T1U"


# ------------------------------------------------------------------
# Confidence grading (stages 2 and 3)
# ------------------------------------------------------------------
LEVELS = ["low", "medium", "high"]


def relation_basis(why):
    """Confidence in the relation (column U) from its reasoning (column V)."""
    if why.startswith("Manual"):
        return "high", "relation assigned by CIHI reviewers (column M)"
    if why.startswith(("Rule 0", "Rule 5a")):
        return "high", "source and target titles are the same after normalization"
    if why.startswith("Medical-knowledge check"):
        return "medium", "relation set by the medical-knowledge check (one reviewer's judgment, not yet confirmed)"
    if why.startswith("Rule 7"):
        return "low", "titles share few words; relation is a weak mechanical guess"
    if why.startswith("Rule"):
        return "medium", f"relation from a mechanical rule ({why.split(':')[0]}) on titles and synonyms"
    return "low", "relation could not be assessed"


def same_title(a, b):
    """Titles identical after normalization, or with the same content words."""
    return norm(a) == norm(b) or (words(norm(a)) and words(norm(a)) == words(norm(b)))


def sentence(parts):
    text = "; ".join(parts)
    return text[:1].upper() + text[1:]


def lower(level, steps=1):
    return LEVELS[max(0, LEVELS.index(level) - steps)]


def cap(level, ceiling):
    return LEVELS[min(LEVELS.index(level), LEVELS.index(ceiling))]


def grade_stem(s_title, why, t2u, t2title, t2rel, rule, notes):
    """Confidence in a stage-2 row: the rule if there is one, else the relation."""
    level, reason = relation_basis(why)
    parts = [reason]
    if not rule:
        parts.insert(0, "no rule proposed; grade refers to the relation")
    elif t2u:
        if "reset to the most specific broader ancestor" in notes:
            level = lower(level)
            parts.append("rule target is an ancestor reached after the best search match was rejected")
        elif t2rel == "Equivalent" and same_title(s_title, t2title):
            parts.append(f"descendant '{t2title}' has the same title as the source")
        elif "medical-knowledge check" in notes:
            level = cap(level, "medium")
            parts.append(f"rule target '{t2title}' found by search; judged {t2rel} by the medical-knowledge check")
        else:
            level = cap(level, "medium")
            parts.append(f"rule target '{t2title}' found by search and judged {t2rel} mechanically")
    elif "⊂" in rule and ("no match" in notes or "no descendants" in notes):
        parts.append("no more specific Foundation entity below the target")
    return level, sentence(parts)


# ICD-10 'A and B' titles where the cluster's 'both' reading is intended.
AND_MEANS_BOTH = {"I13", "N92.0"}


def grade_pc(g, s_title, k, why, t3, t3title, t4, rule, notes):
    """Confidence in a stage-3 row: the rule if there is one, else the relation."""
    level, reason = relation_basis(why)
    parts = [reason]
    if not rule:
        parts.insert(0, "no rule proposed; grade refers to the relation")
    elif t3:
        if same_title(s_title, t3title):
            level, parts = "high", [f"existing Foundation entity '{t3title}' has the same title as the source"]
        else:
            level, parts = "medium", [f"existing Foundation entity '{t3title}' judged equivalent by synonym or word match"]
    else:
        if "/" in k and re.search(r"\band\b", s_title, re.I) \
                and not re.search(r"\bboth\b", s_title, re.I) and g not in AND_MEANS_BOTH \
                and why.startswith("Manual"):
            level = "low"
            parts.append("ICD-10 'and' usually means either or both, but the cluster requires both, "
                         "so the new entity may be narrower than the source")
    return level, sentence(parts)



# ------------------------------------------------------------------
# README sheet
# ------------------------------------------------------------------
def data_sheet(wb):
    """The data sheet: the first sheet that is not the README."""
    return next(ws for ws in wb.worksheets if ws.title != "README")


# Columns A-V are common to both output files: (header, meaning, values).
README_COMMON = [
    ("Organization/Affiliation", "Organization giving the feedback.", "CIHI"),
    ("Date", "Date of CIHI's feedback.", "2025-07-04"),
    ("Name", "Contact person for the feedback.", "Sharon Baker"),
    ("Contact Details", "Contact address for the feedback.", "whofic.mtf@gmail.com"),
    ("Version of WHO Mapping Table", "WHO map that CIHI reviewed.", "2022 10To11MapToOneCategory"),
    ("Map direction", "Direction of the reviewed map.", "Forward (ICD-10 to ICD-11)"),
    ("WHO ICD-10 / ICD-11 Code", "ICD-10 source code (S in the rules).", "An ICD-10 code, e.g. A84.9"),
    ("WHO ICD-10 / ICD-11 Code Title", "Title of the ICD-10 source code.", "Text"),
    ("WHO Mapped ICD-10/ ICD-11 Code", "ICD-11 MMS code that the WHO 2022 map assigns to the source.", "An ICD-11 MMS code"),
    ("WHO Mapped ICD-10 / ICD-11 Title", "Title of the WHO-mapped code.", "Text"),
    None,  # K: file-specific
    None,  # L: file-specific
    ("Corrected Code Mapping Relation",
     "CIHI's relation of the suggested code (K) to the source, from CIHI's E/B/N assessment.",
     "Equivalent; Broader (target broader than source); Narrower (target narrower than source); "
     "empty = not assessed by CIHI"),
    ("Comment", "Comments of the CIHI reviewers and conflict-resolution team.", "Free text, or empty"),
    ("WHO Mapped Foundation Entity", "Foundation entity of the WHO-mapped code.", "Empty (not filled)"),
    None,  # P: file-specific
    ("Additional Comments", "CIHI's reason why its map differs from WHO's.",
     "NoMatch_2022CodingTool Guides to CIHI chosen map; NoMatch_2023CodingTool Guides to CIHI chosen map; "
     "NoMatch_Residual Y versus Z; NoMatch_Validator decision; NoMatch_1:many stem code map possible (...); "
     "NoMatch_WHO maps to category level; NoMatch_No WHO map available; or empty"),
    ("Action for WHO", "Action CIHI asks WHO to take. Only rows containing 'Update WHO map' or starting with "
     "'Update map' get a mapping rule.",
     "Mostly 'Update WHO map', sometimes with 'Add index term.', 'Review indexing.', 'Add postcoordination.' "
     "or 'See comment.'; occasionally other text (e.g. 'Review modelling.')"),
    ("Details", "Details of the requested action.", "Empty (not filled)"),
    ("Status", "Status of the feedback, for WHO to fill in.", "Empty"),
    ("Completed Code Mapping Relation",
     "Relation of the suggested code (K) to the ICD-10 source: CIHI's relation (M) where present, "
     "otherwise inferred.",
     "Equivalent (same concept); Broader (target broader than source); Narrower (target narrower than "
     "source); Related (overlapping or different concepts)"),
    None,  # V: file-specific
]

README_STEM = {
    "K": ("Suggested/Corrected Mapped ICD-10 /ICD-11 Code",
          "CIHI's suggested ICD-11 code (T1 in the rules).",
          "A single ICD-11 MMS stem code not ending in Y, e.g. 1C8G.Z"),
    "L": ("Suggested/Corrected Mapped ICD-10 / ICD-11 Code Title", "Title of the suggested code.",
          "Empty (not filled for stem codes)"),
    "P": ("Suggested/Corrected Mapped Foundation Entity",
          "Foundation entity of the suggested code (T1U). Residual categories (.Z) are mapped to the "
          "Foundation entity of their parent.",
          "A Foundation URI, e.g. http://id.who.int/icd/entity/835129952"),
    "V": ("Reasoning", "How the relation in U was obtained.",
          "'Manual' (copied from M); 'Rule n: ... Target: <Foundation title>' (rules of "
          "determine-stemcode-semantic-relationships.md); or 'Medical-knowledge check: <reason> (rules gave ...)'"),
    "W": ("Descendant match (T2U)",
          "For Broader rows: the Foundation entity below T1U used as the rule target, i.e. a closer match to "
          "the source or the most specific broader ancestor of one.",
          "A Foundation URI, or empty (rule uses T1U, or no rule)"),
    "X": ("Descendant match title", "Title of the descendant match.", "Text, or empty"),
    "Y": ("Descendant match relation", "Relation of the descendant match to the source.",
          "Equivalent; Broader; or empty"),
    "Z": ("Proposed mapping rule",
          "Proposed Foundation mapping rule for the ICD-10 source S. ≡: S is equivalent to the entity; "
          "⊂: the entity is broader than S; ⊃: the entity is narrower than S.",
          "'S ≡ URI', 'S ⊂ URI' or 'S ⊃ URI'; empty = no rule"),
    "AA": ("Rule notes", "How the rule target was found, or why there is no rule.",
           "e.g. 'T2 via Foundation search in T1U subtree'; '...reset to the most specific broader ancestor'; "
           "'no match among T1U's descendants'; 'T1U has no descendants'; 'No rule: Action for WHO is ...'; "
           "'No rule: ICD-10 source is an X.8 'other' residual'; 'No rule: relation is 'Related'; review'"),
}

README_PC = {
    "K": ("Suggested/Corrected Mapped ICD-10 /ICD-11 Code",
          "CIHI's suggested post-coordinated ICD-11 expression (T1 in the rules).",
          "MMS codes joined by & (extension code) and / (cluster), e.g. 2E92.4Z&XA2G13, 1C41/1G40"),
    "L": ("Suggested/Corrected Mapped ICD-10 / ICD-11 Code Title",
          "Readable meaning of the expression, from the MMS 'describe' service (or assembled code by code "
          "when MMS rejects the combination).",
          "Text, e.g. 'Benign neoplasm of the large intestine, unspecified [Descending colon]'"),
    "P": ("Suggested/Corrected Mapped Foundation Entity",
          "Foundation expression of the post-coordination.",
          "Foundation URIs joined by ' & ' and ' / '"),
    "V": ("Reasoning", "How the relation in U was obtained, and whether MMS accepts the expression.",
          "'Manual' (copied from M); 'Rule n: ... Target: <label>'; or 'Medical-knowledge check: <reason> "
          "(rules gave ...)'; any of these may end with 'Not a valid MMS post-coordination: <MMS reason>'"),
    "W": ("Precoordinated equivalent (T3U)",
          "An existing Foundation entity, under the expression's stem, equivalent to the source.",
          "A Foundation URI, or empty"),
    "X": ("T3U title", "Title of T3U.", "Text, or empty"),
    "Y": ("New Foundation entity (T4U) definition",
          "Logical definition of a proposed new Foundation entity equivalent to the source, built from the "
          "post-coordination.",
          "'URI(title)&URI(title)/...', or empty"),
    "Z": ("Proposed mapping rule",
          "Proposed Foundation mapping rule for the ICD-10 source S. Only equivalence rules are proposed for "
          "post-coordinations.",
          "'S ≡ URI' (existing entity T3U) or 'S ≡ T4U[new entity: ...]'; empty = no rule"),
    "AA": ("Rule notes", "Why there is or is not a rule.",
           "'Existing Foundation entity under the stem is equivalent to the source'; 'No equivalent Foundation "
           "entity; propose a new one defined by the post-coordination' (may add '; review: the "
           "post-coordination is not valid in MMS'); 'No rule: the post-coordination contains a code ending "
           "in Y'; 'No rule: the post-coordination is <relation> relative to the source; review'; "
           "'No rule: Action for WHO is ...'; 'No rule: ICD-10 source is an X.8 ...'"),
}

README_CONFIDENCE = {
    "AB": ("Confidence", "Confidence in the proposed rule, or in the relation when there is no rule.",
           "high; medium; low"),
    "AC": ("Confidence rationale", "Reasons for the confidence grade (see doc/Method.md, Confidence).",
           "Text"),
}


def add_readme(wb, title, summary, specific, release):
    """(Re)create a README sheet, first in the workbook, describing every column."""
    from openpyxl.utils import get_column_letter
    if "README" in wb.sheetnames:
        del wb["README"]
    ws = wb.create_sheet("README", 0)
    data = data_sheet(wb)
    n = sum(1 for r in range(2, data.max_row + 1) if data.cell(r, COL_K).value is not None)
    lines = [title, ""] + summary + [
        "",
        f"Rows: {n} (sheet '{data.title}'). Generated {date.today().isoformat()} by "
        f"bin/generateMappingRelationsAndRules.py using ICD-11 MMS {release}.",
        "Columns A-T follow the WHO Mapping Feedback Template; columns U-AC are added by step 4. "
        "See doc/Method.md and doc/mappingRulesSpecification.md.",
        "",
    ]
    for i, text in enumerate(lines, start=1):
        ws.cell(i, 1, text).alignment = Alignment(wrap_text=False)
    ws.cell(1, 1).font = Font(bold=True, size=14)
    head = len(lines) + 1
    for c, h in enumerate(("Column", "Header", "Meaning", "Possible values"), start=1):
        cell = ws.cell(head, c, h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")
    spec = {**specific, **README_CONFIDENCE}
    for i in range(1, 30):
        letter = get_column_letter(i)
        entry = README_COMMON[i - 1] if i <= len(README_COMMON) and README_COMMON[i - 1] else spec[letter]
        header, meaning, values = entry
        row = head + i
        for c, v in enumerate((letter, header, meaning, values), start=1):
            ws.cell(row, c, v).alignment = Alignment(wrap_text=True, vertical="top")
    for letter, width in (("A", 9), ("B", 42), ("C", 60), ("D", 70)):
        ws.column_dimensions[letter].width = width
    wb.active = 0


def stage2(sess, release):
    wb = load_workbook(OUT_REL)
    ws = data_sheet(wb)
    if ws.cell(1, COL_U).value != "Completed Code Mapping Relation":
        raise SystemExit(f"{OUT_REL.name} has no stage-1 columns; run stage 1 first.")
    rows = [r for r in range(2, ws.max_row + 1) if ws.cell(r, COL_K).value is not None]
    jobs = [(clean(ws.cell(r, 7).value), str(ws.cell(r, COL_H).value or ""),
             clean(ws.cell(r, COL_P).value), clean(ws.cell(r, COL_U).value),
             ws.cell(r, COL_R).value) for r in rows]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda j: propose_rule(sess, release, *j), jobs))

    for col, name, width in ((COL_T2U, "Descendant match (T2U)", 40),
                             (COL_T2T, "Descendant match title", 40),
                             (COL_T2R, "Descendant match relation", 20),
                             (COL_RULE, "Proposed mapping rule", 50),
                             (COL_NOTE, "Rule notes", 60)):
        set_header(ws, col, name, width)
    set_header(ws, COL_CONF, "Confidence", 12)
    set_header(ws, COL_CONF_WHY, "Confidence rationale", 70)
    for r, res in zip(rows, results):
        for col, v in zip((COL_T2U, COL_T2T, COL_T2R, COL_RULE, COL_NOTE), res):
            ws.cell(r, col, v or None)
        level, reason = grade_stem(str(ws.cell(r, COL_H).value or ""),
                                   str(ws.cell(r, COL_V).value or ""), *res)
        ws.cell(r, COL_CONF, level)
        ws.cell(r, COL_CONF_WHY, reason)
    add_readme(wb, "Mapping relations and proposed Foundation mapping rules: stem-code suggestions",
               ["Each row is a still-actionable CIHI feedback entry whose suggested ICD-11 code (column K) is a "
                "single MMS stem code.",
                "Step 4 adds the Foundation entity of that code (P), its relation to the ICD-10 source (U, V), "
                "a proposed Foundation mapping rule (W-AA) and a confidence grade (AB, AC)."],
               README_STEM, release)
    wb.save(OUT_REL)
    conf = {lv: sum(1 for r in rows if ws.cell(r, COL_CONF).value == lv) for lv in LEVELS}

    kinds = {"≡": 0, "⊃": 0, "⊂": 0}
    for res in results:
        for sym in kinds:
            if f" {sym} " in res[3]:
                kinds[sym] += 1
    print(f"Stage 2: proposed rules for {sum(kinds.values())} of {len(rows)} rows "
          f"(≡ {kinds['≡']}, ⊃ {kinds['⊃']}, ⊂ {kinds['⊂']}; "
          f"{sum(1 for x in results if x[0])} via a descendant match); "
          f"no rule: {sum(1 for x in results if not x[3])}")
    print(f"  Confidence: high {conf['high']}, medium {conf['medium']}, low {conf['low']}")


# ------------------------------------------------------------------
# Stage 3: post-coordinated suggestions - relations and mapping rules
# ------------------------------------------------------------------
# Medical-knowledge judgments of the relation between the ICD-10 source and
# the post-coordination, for rows without a manual relation (column M):
# (ICD-10 code, suggested code) -> (relation, reason). Two conventions drive
# most entries: an ICD-10 'A and B' title means A and/or B, whereas an ICD-11
# 'A/B' cluster requires both (-> Narrower); and a dagger 'X in diseases
# classified elsewhere' title is a cluster of the manifestation and the
# disease (-> Equivalent). Only judgments that differ from the rules are kept.
POSTCOORD_CHECK = {
    ('A41.4', '1C41/1G40'): ('Broader', 'sepsis due to any bacterium; anaerobes not specified'),
    ('A42.7', '1C10.Y/1G40'): ('Equivalent', 'actinomycosis with sepsis'),
    ('A54.6', '1A72.2/1A72.1'): ('Narrower', "ICD-10 'anus and rectum' means either or both; the cluster requires both"),
    ('A56.3', '1A81.Y&XA0D34&XA4KU2'): ('Equivalent', 'chlamydial infection at anus and rectum'),
    ('B25.0', '1D82.Y/CA40.1Y'): ('Equivalent', 'cytomegaloviral disease with viral pneumonia'),
    ('C41.0', '2B5Z&XA1RZ4&XA3Y16'): ('Narrower', 'requires both cranial and facial bones and mesenchymal type'),
    ('C72.5', '2A02.1Z&XA8EK9'): ('Broader', 'target covers tumours of any behaviour, not only malignant'),
    ('C92.4', '2A60.0&XH1A50'): ('Equivalent', 'AML with t(15;17) is acute promyelocytic leukaemia'),
    ('D12.4', '2E92.4Z&XA2G13'): ('Equivalent', 'benign neoplasm of large intestine at descending colon'),
    ('D21.2', '2E8Y&XA5A05&XA45A6&XA4TQ2'): ('Narrower', "trochanteric region narrows 'lower limb, including hip'"),
    ('D21.3', '2E8Y&XA5A05&XA5D93'): ('Equivalent', 'benign connective-tissue neoplasm of thorax'),
    ('E13.1', '5A22.0/5A13.Y'): ('Equivalent', 'E13.1 is ketoacidosis without coma (coma is E13.0)'),
    ('E44.1', '5B7Z&XS5W'): ('Equivalent', 'mild undernutrition'),
    ('E90', '5C3Z/5D2Z'): ('Related', 'dagger code for disorders in other diseases; the cluster names two unspecified disorders'),
    ('F05.1', '6D70.Z/6D8Z'): ('Equivalent', 'delirium with dementia'),
    ('F11.6', '6D72.12&XM7S23'): ('Equivalent', 'amnestic disorder due to opioids'),
    ('F12.4', '6C41.5/6C41.4'): ('Equivalent', 'cannabis withdrawal with delirium'),
    ('F12.6', '6D72.12&XM9S25'): ('Equivalent', 'amnestic disorder due to cannabis'),
    ('H04.4', '9A11.Y&XT8W'): ('Broader', 'target is any lacrimal drainage disorder, not only inflammation'),
    ('H13.0', '1F66.Y/9A60.Y'): ('Equivalent', 'filariasis with conjunctivitis'),
    ('H54.0', '9D90.6&XK9J'): ('Equivalent', 'bilateral blindness'),
    ('H90.7', 'AB51.2&XK70'): ('Equivalent', 'unilateral mixed hearing loss'),
    ('I32.0', 'BB20.0/1C4Z'): ('Equivalent', 'infectious pericarditis with bacterial disease'),
    ('I63.6', '8B11.2Y/8B22.1'): ('Related', 'venous infarction is not an embolic arterial occlusion'),
    ('I74.5', 'BD30.1Y&XA83D6'): ('Narrower', 'target covers acute occlusion only'),
    ('J38.7', 'CA0H.Y&XA2RH5'): ('Equivalent', "'other diseases of larynx' is the 'other specified' residual"),
    ('J39.2', 'CA0Y&XA93V5'): ('Equivalent', "'other diseases of pharynx' is the 'other specified' residual"),
    ('K25.2', 'DA60.Y&XT5R/ME24.9Z/ME24.3Z'): ('Equivalent', 'acute gastric ulcer with bleeding and perforation'),
    ('K26.1', 'DA63.Y&XT5R/ME24.3Z'): ('Equivalent', 'acute duodenal ulcer with perforation'),
    ('K26.5', 'DA63.Y&XT8W'): ('Narrower', 'extension restricts to chronic; source also covers unspecified duration'),
    ('K26.6', 'DA63.Z&XT8W/ME24.9Z/ME24.3Z'): ('Narrower', 'extension restricts to chronic; source also covers unspecified duration'),
    ('K28.2', 'DA62.3&XT5R/ME24.90/ME24.3Y'): ('Equivalent', 'acute anastomotic ulcer with bleeding and perforation'),
    ('K28.7', 'DA62.Y&XT8W'): ('Broader', "'without haemorrhage or perforation' is not expressed"),
    ('K46.0', 'DD5Z/ME24.2'): ('Equivalent', 'hernia with obstruction'),
    ('K67.2', '1A62.2Y/DC50.1Y'): ('Narrower', 'target restricts to late syphilis'),
    ('L23.4', 'EK00.Y&XM8H37'): ('Equivalent', 'allergic contact dermatitis due to dye'),
    ('L25.0', 'EA8Y&XE79N'): ('Broader', 'target is eczematous dermatosis of any kind due to cosmetics'),
    ('L25.2', 'EK5Y&XM8H37'): ('Broader', 'target is any skin disorder provoked by dyes'),
    ('L50.2', 'EB01.1/EB01.Y'): ('Narrower', 'source is cold and/or heat urticaria; the cluster requires both'),
    ('L98.4', 'ME60.2&XT8W'): ('Equivalent', 'chronic skin ulcer'),
    ('M16.6', 'FA00.2&XK9J'): ('Equivalent', 'other secondary hip osteoarthritis, bilateral'),
    ('M17.3', 'FA01.1&XK70'): ('Equivalent', 'M17.3 is unilateral post-traumatic knee osteoarthritis'),
    ('M18.2', 'FA02.1&XK9J&XA0JX0'): ('Broader', 'target covers any carpometacarpal joint, not only the first'),
    ('M42.1', 'FB82.1&XA5J55'): ('Broader', 'target is not restricted to adult osteochondrosis'),
    ('M70.7', 'FB50.Z&XA4TQ2'): ('Narrower', 'trochanteric region only; source covers any other bursitis of hip'),
    ('M80.0', 'FB83.11/FB80.B'): ('Equivalent', 'postmenopausal osteoporosis with pathological fracture'),
    ('M80.1', 'FB80.B/FC01.9'): ('Equivalent', 'postoophorectomy osteoporosis with pathological fracture'),
    ('M90.7', 'FB80.B/2F9Z'): ('Narrower', 'target restricts to neoplasms of unknown behaviour'),
    ('N07.9', 'GB4Z&XB7K'): ('Equivalent', 'hereditary glomerular disease'),
    ('N29.0', '1A62.2Y&XA6KU8'): ('Equivalent', 'late syphilis of kidney'),
    ('N77.0', 'GA00.3/1G2Z'): ('Narrower', 'target restricts to parasitic disease'),
    ('Q18.9', 'LA5Z/LA6Z'): ('Narrower', "ICD-10 'face and neck' means either or both; the cluster requires both"),
    ('Q37.0', 'LA42.0/LA40.1'): ('Equivalent', 'cleft hard palate with bilateral cleft lip'),
    ('Q37.1', 'LA42.0/LA40.0'): ('Equivalent', 'cleft hard palate with unilateral cleft lip'),
    ('Q42.3', 'LB17.Z&XA0D34'): ('Broader', 'target is any anomaly of the anal canal'),
    ('Q68.0', 'LA6Y&XA2H61'): ('Equivalent', 'developmental anomaly of the sternocleidomastoid'),
    ('S58.0', 'NC38.Z&XA69H4'): ('Equivalent', 'traumatic amputation at the elbow joint'),
    ('S78.0', 'NC78.Z&XA4XS4'): ('Equivalent', 'traumatic amputation at the hip joint'),
    ('V80.3', 'PA2E/PA2F'): ('Broader', 'the colliding vehicle is not expressed'),
    ('W56', 'PG6Z&XE2AH'): ('Related', 'target is of undetermined intent; W56 is accidental'),
    ('X08', 'PB1Y&XE3NR'): ('Equivalent', 'unintentional exposure to fire, flame or smoke'),
    ('Y05', 'PE1Y&XE213'): ('Equivalent', 'sexual assault by bodily force'),
    ('Y07.3', 'PJ2Z&XE2HC'): ('Equivalent', 'maltreatment by official authorities'),
    ('Z49.2', 'QB94.2/QB94.Y'): ('Narrower', 'cluster requires both peritoneal and other dialysis'),
    ('G30.0', '8A20&XT2Q'): ('Equivalent', 'early-onset Alzheimer disease'),
    ('T11.4', 'ND53.Y&XA21T7'): ('Equivalent', 'blood-vessel injury of arm'),
    ('T13.3', 'ND55&XA06U6'): ('Equivalent', 'peripheral-nerve injury of leg'),
    ('T81.6', 'NE81.Z/PK8Z/PL11.3'): ('Broader', 'the acute reaction is not expressed'),
    ('W50', 'PA70/PA74/PA76'): ('Narrower', "cluster requires all three mechanisms; 'twisted' is not covered"),
    ('Y26', 'PH30/PH31&XE3NR'): ('Narrower', 'cluster requires both controlled and uncontrolled fire'),
    ('H54.6', '9D90.2&XK70'): ('Equivalent', 'unilateral moderate vision impairment'),
    ('I21.1', 'BA41.0&XA3RM8'): ('Equivalent', 'acute STEMI of the inferior wall'),
    ('K28.0', 'DA62.3/ME24.90'): ('Broader', 'acuity of the ulcer is not expressed'),
    ('S64.3', 'NC55.Y&XA37M8&XA8DJ6'): ('Equivalent', 'digital nerve injury of thumb'),
    ('W54', 'PA75&XE33Q'): ('Narrower', 'target covers bites only, not being struck'),
    ('M80.4', 'FB83.13/FB80.B'): ('Equivalent', 'drug-induced osteoporosis with pathological fracture'),
    ('Q23.9', 'LA8A.2Z/LA87.1Z'): ('Narrower', "ICD-10 'aortic and mitral' means either or both; the cluster requires both"),
    ('Q60.3', 'LB30.0Y&XK70'): ('Broader', 'target covers other reduction defects, not only hypoplasia'),
    ('Q67.4', 'LB70.Y/LB71.Y/DA0E.Y'): ('Narrower', 'cluster requires anomalies of all three sites'),
    ('R53', 'MG25/MG22'): ('Narrower', "ICD-10 'malaise and fatigue' means either or both; the cluster requires both"),
    ('G06.0', '1D03.3Z/1D04.1Z'): ('Narrower', "ICD-10 'abscess and granuloma' means either or both; the cluster requires both"),
    ('G73.6', '8C8Z/5D2Z'): ('Equivalent', 'secondary myopathy with metabolic disorder'),
    ('H51.1', '9C83.2/9C83.3'): ('Related', 'insufficiency and excess cannot coexist, so the cluster is not a valid concept'),
    ('H54.5', '9D90.3&XK70'): ('Equivalent', 'unilateral severe vision impairment'),
    ('I23.0', 'BB24/BA60.Y'): ('Equivalent', 'haemopericardium as a complication after acute MI'),
    ('I43.1', 'BC43.Z/5D2Z'): ('Equivalent', 'cardiomyopathy with metabolic disorder'),
    ('X39', 'PJ0Y/PJ0Z'): ('Related', "cluster of 'other specified' and 'unspecified' forces is not a coherent concept"),
    ('Y06.9', 'PF1A/PF1B'): ('Related', 'source holds two titles; cluster requires both abandonment and neglect'),
    ('Y84.2', 'PK8Y/PK81.C'): ('Narrower', 'cluster requires both an other procedure and radiotherapy'),
    ('Z55.4', 'QE50.1Z/QE50.10'): ('Narrower', "ICD-10 'and' means either or both; the cluster requires both"),
    ('K46.1', 'DD5Z/ME24.8'): ('Equivalent', 'hernia with gangrene'),
    ('K52.0', 'DA42.81/DA94.31/DB33.41'): ('Narrower', 'cluster requires all three sites; source is gastroenteritis and/or colitis'),
    ('K62.4', 'DB51/DB30.4'): ('Narrower', "ICD-10 'anus and rectum' means either or both; the cluster requires both"),
    ('M18.0', 'FA02.0&XA0JX0&XK9J'): ('Broader', 'target covers any carpometacarpal joint, not only the first'),
    ('P58.4', 'KA87.4/KA87.5'): ('Narrower', 'cluster requires both maternal and neonatal drug exposure'),
    ('Q24.2', 'LA8G.0/LA8F'): ('Narrower', 'cluster requires both a divided left atrium and a right-atrial anomaly'),
}

PC_COLS = ((23, "Precoordinated equivalent (T3U)", 40),
           (24, "T3U title", 40),
           (25, "New Foundation entity (T4U) definition", 70),
           (26, "Proposed mapping rule", 50),
           (27, "Rule notes", 60),
           (COL_CONF, "Confidence", 12),
           (COL_CONF_WHY, "Confidence rationale", 70))


def pc_target_text(label):
    """Readable meaning of a post-coordination for the rules: the describe
    label without residual markers ('Other specified', ', unspecified') and
    brackets, e.g. 'Benign neoplasm of the large intestine, unspecified
    [Descending colon]' -> 'Benign neoplasm of the large intestine Descending colon'."""
    t = re.sub(r"^(other specified|certain specified)\s+", "", label or "", flags=re.I)
    t = re.sub(r",\s*(unspecified|not elsewhere classified)", "", t, flags=re.I)
    return re.sub(r"[\[\]]", " ", t).replace(" / ", " ")


def t4u_definition(sess, fexpr):
    """'URI(title)&URI(title)/...' from describe's foundationUri expression."""
    parts = re.split(r"\s+([&/])\s+", fexpr)  # separators are space-delimited
    out = ""
    for i, p in enumerate(parts):
        if i % 2:
            out += p
        else:
            out += f"{p}({icdapi.foundation_entity(sess, p)['title']})"
    return out


def find_t3(sess, g, s_title, stem_uri):
    """Existing Foundation entity under the stem equivalent to the source."""
    if not stem_uri:
        return None, None
    for uri, title in icdapi.subtree_search(sess, s_title, stem_uri, n=3):
        ent = icdapi.foundation_entity(sess, uri)
        rel = CANDIDATE_CHECK.get((g, uri), (rel_to_candidate(s_title, ent),))[0]
        if rel == "Equivalent":
            return uri, ent["title"] or title
    return None, None


def stage3(sess, release):
    shutil.copyfile(SRC_PC, OUT_PC)
    wb = load_workbook(OUT_PC)
    ws = data_sheet(wb)
    rows = [r for r in range(2, ws.max_row + 1) if ws.cell(r, COL_K).value is not None]
    def expr_of(r):
        return re.sub(r"\s*([&/])\s*", r"\1", clean(ws.cell(r, COL_K).value))

    exprs = sorted({expr_of(r) for r in rows})
    with ThreadPoolExecutor(8) as ex:
        desc = dict(zip(exprs, ex.map(lambda e: icdapi.describe(sess, release, e), exprs)))

    set_header(ws, COL_U, "Completed Code Mapping Relation", 30)
    set_header(ws, COL_V, "Reasoning", 70)
    for col, name, width in PC_COLS:
        set_header(ws, col, name, width)

    def one(r):
        g = clean(ws.cell(r, 7).value)
        s_title = str(ws.cell(r, COL_H).value or "")
        k = expr_of(r)
        d = desc[k]
        label, fexpr = d.get("label", ""), d.get("foundationUri", "")
        mms_error = d.get("error", "")
        flag = f" Not a valid MMS post-coordination: {mms_error}." if mms_error else ""
        # Relation
        m = ws.cell(r, COL_M).value
        if m not in (None, ""):
            rel, why = str(m).strip(), "Manual"
            why += flag
        elif not label:
            rel, why = "", "describe failed for the suggested code"
        else:
            rel, why = relationship(s_title, pc_target_text(label), [])
            why = f"{why}. Target: '{label}'.{flag}"
            if (g, k) in POSTCOORD_CHECK:
                new, reason = POSTCOORD_CHECK[(g, k)]
                why = f"Medical-knowledge check: {reason} (rules gave {rel or 'none'}: {why})"
                rel = new
        # Rule
        a = str(ws.cell(r, COL_R).value or "").strip().lower()
        t3 = t3t = t4 = rule = ""
        if not ("update who map" in a or a.startswith("update map")):
            note = f"No rule: Action for WHO is '{ws.cell(r, COL_R).value}', not 'Update (WHO) map'"
        elif re.fullmatch(r"[A-Z]\d\d\.8", g):
            note = "No rule: ICD-10 source is an X.8 'other' residual"
        elif any(c.endswith("Y") for c in re.split(r"[&/]", k)):
            note = "No rule: the post-coordination contains a code ending in Y"
        elif not fexpr:
            note = "No rule: describe failed for the suggested code"
        else:
            t3, t3t = find_t3(sess, g, s_title, d.get("stemFoundationUri"))
            if t3:
                rule, note = f"{g} ≡ {t3}", "Existing Foundation entity under the stem is equivalent to the source"
            elif rel == "Equivalent":
                t4 = t4u_definition(sess, fexpr)
                rule = f"{g} ≡ T4U[new entity: {t4}]"
                note = "No equivalent Foundation entity; propose a new one defined by the post-coordination"
                if mms_error:
                    note += "; review: the post-coordination is not valid in MMS"
            else:
                note = f"No rule: the post-coordination is {rel or 'unassessed'} relative to the source; review"
        level, reason = grade_pc(g, s_title, k, why, t3, t3t or "", t4, rule, note)
        return r, label, fexpr, rel, why, (t3, t3t, t4, rule, note, level, reason)

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(one, rows))
    for r, label, fexpr, rel, why, rule_cols in results:
        if not ws.cell(r, COL_L).value and label:
            ws.cell(r, COL_L, label)
        if not ws.cell(r, COL_P).value and fexpr:
            ws.cell(r, COL_P, fexpr)
        ws.cell(r, COL_U, rel)
        ws.cell(r, COL_V, why)
        for (col, _, _), v in zip(PC_COLS, rule_cols):
            ws.cell(r, col, v or None)
    add_readme(wb, "Mapping relations and proposed Foundation mapping rules: post-coordinated suggestions",
               ["Each row is a still-actionable CIHI feedback entry whose suggested ICD-11 code (column K) is a "
                "post-coordinated expression.",
                "Step 4 adds the expression's meaning (L) and Foundation expression (P), its relation to the "
                "ICD-10 source (U, V), a proposed Foundation mapping rule (W-AA) and a confidence grade (AB, AC)."],
               README_PC, release)
    wb.save(OUT_PC)

    conf = {lv: sum(1 for x in results if x[5][5] == lv) for lv in LEVELS}
    n_manual = sum(1 for x in results if x[4].startswith("Manual"))
    n_med = sum(1 for x in results if x[4].startswith("Medical"))
    n_bad = sum(1 for k in {expr_of(r) for r in rows} if desc[k].get("error"))
    rules = [x[5][3] for x in results]
    print(f"Stage 3: wrote {len(rows)} rows -> {OUT_PC}")
    print(f"  Relations: manual (column M) {n_manual}, by rules {len(rows) - n_manual} "
          f"(medical-knowledge check {n_med}); "
          f"{n_bad} distinct expressions not valid in MMS")
    print(f"  Rules: {sum(1 for x in rules if x)} "
          f"(≡ existing entity {sum(1 for x in results if x[5][0])}, "
          f"≡ new entity {sum(1 for x in results if x[5][2])}); "
          f"no rule {sum(1 for x in rules if not x)}")
    print(f"  Confidence: high {conf['high']}, medium {conf['medium']}, low {conf['low']}")


sess = icdapi.session()
release = icdapi.choose_release(sess, args.release,
                                purpose="Look up Foundation entities in")
print(f"Using ICD-11 MMS {release}.")
if args.stage in ("1", "all"):
    stage1(sess, release)
if args.stage in ("2", "all"):
    stage2(sess, release)
if args.stage in ("3", "all"):
    stage3(sess, release)
