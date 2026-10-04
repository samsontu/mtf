"""
Shared WHO ICD-API helpers for the cihifeedback scripts.

  session()                 authenticated requests.Session (credentials are
                            read from bin/icdapi_credentials.json)
  choose_release(sess, r)   MMS release id: r if given, else the most recent
                            release after the user confirms it
  code_exists(sess, rel, c) True if code c exists in MMS release rel
  foundation_of(sess, rel, c)
                            (Foundation URI, title, synonyms) of MMS code c
  foundation_entity(sess, uri)
                            {title, synonyms, parent, descendant} of a
                            Foundation entity (cached)
  autocode(sess, rel, text) best MMS autocode match ({} on failure)
  subtree_search(sess, text, uri)
                            top Foundation search hits within uri's subtree
  describe(sess, rel, expr) MMS describe of a post-coordinated expression;
                            if MMS rejects it, assembled code by code with
                            the rejection reason in `error`
"""

import json
import re
import sys
from pathlib import Path

import requests

CRED = Path(__file__).resolve().parent / "icdapi_credentials.json"
API = "https://id.who.int/icd"


def session():
    cred = json.loads(CRED.read_text())
    cid, sec = cred["client_id"], cred["client_secret"]
    tok = requests.post(
        "https://icdaccessmanagement.who.int/connect/token",
        data={"client_id": cid, "client_secret": sec,
              "scope": "icdapi_access", "grant_type": "client_credentials"},
        timeout=30,
    ).json()["access_token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Accept": "application/json",
                      "Accept-Language": "en", "API-Version": "v2"})
    return s


def choose_release(sess, release=None, purpose="Check suggested codes against"):
    """Return the MMS release id to use, confirming the latest with the user.

    If `release` is given it is used as is. Otherwise the most recent
    release is looked up and the user is asked to confirm it (or type
    another release id). Exits when not running interactively."""
    if release:
        return release
    info = sess.get(f"{API}/release/11/mms", timeout=30).json()
    latest = info["latestRelease"].rstrip("/").split("/")[-2]
    available = [u.rstrip("/").split("/")[-2] for u in info.get("release", [])]
    print(f"Most recent ICD-11 MMS release: {latest}")
    print(f"Available releases: {', '.join(available)}")
    if not sys.stdin.isatty():
        raise SystemExit("Not running interactively: re-run with --release "
                         f"{latest} (or another release) to confirm.")
    ans = input(f"{purpose} {latest}? "
                "[Y = yes / n = abort / or type another release id]: ").strip()
    if ans == "" or ans.lower() in ("y", "yes"):
        return latest
    if ans in available:
        return ans
    raise SystemExit("Aborted; no files written.")


def codeinfo(sess, release, code):
    r = sess.get(f"{API}/release/11/{release}/mms/codeinfo/{code}", timeout=30)
    return r.json() if r.status_code == 200 else None


def code_exists(sess, release, code):
    ci = codeinfo(sess, release, code)
    return ci is not None and str(ci.get("code", "")).upper() == code


def foundation_of(sess, release, code):
    """Return (Foundation URI, Foundation title, [synonyms]) for an MMS code.

    The MMS entity's `source` is its Foundation entity. Residual
    categories (.../unspecified, .../other) have no source; they are
    mapped to the Foundation entity of their parent (same numeric id).
    Returns (None, None, []) if the code cannot be resolved."""
    ci = codeinfo(sess, release, code)
    if not ci or not ci.get("stemId"):
        return None, None, []
    stem = ci["stemId"]
    r = sess.get(stem, timeout=30)
    src = r.json().get("source") if r.status_code == 200 else None
    if not src:
        m = re.search(r"/mms/(\d+)/(unspecified|other)$", stem)
        if not m:
            return None, None, []
        src = f"http://id.who.int/icd/entity/{m.group(1)}"
    f = sess.get(src, timeout=30)
    if f.status_code != 200:
        return src, None, []
    j = f.json()
    title = (j.get("title") or {}).get("@value", "")
    syns = [(s.get("label") or {}).get("@value", "") for s in j.get("synonym", [])]
    return src, title, [s for s in syns if s]


def _https(uri):
    return uri.replace("http://", "https://", 1)


_FND = {}


def foundation_entity(sess, uri):
    """Title, synonyms, parents and all descendants of a Foundation entity."""
    if uri not in _FND:
        r = sess.get(_https(uri), params={"include": "descendant"}, timeout=60)
        j = r.json() if r.status_code == 200 else {}
        _FND[uri] = {
            "title": (j.get("title") or {}).get("@value", ""),
            "synonyms": [(x.get("label") or {}).get("@value", "") for x in j.get("synonym", [])],
            "parent": j.get("parent", []),
            "descendant": j.get("descendant", []),
        }
    return _FND[uri]


def autocode(sess, release, text):
    r = sess.get(f"{API}/release/11/{release}/mms/autocode",
                 params={"searchText": text}, timeout=30)
    return r.json() if r.status_code == 200 else {}


def subtree_search(sess, text, uri, n=5):
    """[(Foundation URI, title)] of the best search hits under uri."""
    r = sess.get(f"{API}/entity/search",
                 params={"q": text, "subtreesFilter": uri, "useFlexisearch": "true"},
                 timeout=30)
    if r.status_code != 200:
        return []
    hits = r.json().get("destinationEntities", [])[:n]
    return [(h.get("id"), re.sub(r"</?em[^>]*>", "", h.get("title", ""))) for h in hits]


def describe(sess, release, expr):
    """MMS describe of a post-coordinated expression. On success the API's
    JSON (label, foundationUri, stemFoundationUri, ...). When MMS rejects the
    combination (e.g. an extension not allowed on the stem's axes), the
    expression is assembled code by code instead and `error` holds the API's
    reason."""
    r = sess.get(f"{API}/release/11/{release}/mms/describe",
                 params={"code": expr}, timeout=30)
    if r.status_code == 200:
        return r.json()
    labels, furis = [], []
    for i, part in enumerate(re.split(r"([&/])", expr)):
        if i % 2:
            labels.append(part)
            furis.append(part)
            continue
        uri, _, _ = foundation_of(sess, release, part)
        ci = codeinfo(sess, release, part)
        m = sess.get(_https(ci["stemId"]), timeout=30) if ci and ci.get("stemId") else None
        title = ((m.json().get("title") or {}).get("@value", "")
                 if m is not None and m.status_code == 200 else "")
        labels.append(f"[{title}]" if part.startswith("X") else title)
        furis.append(uri or part)
    label = "".join(f" {x} " if x == "/" else (" " if x == "&" else x) for x in labels)
    fexpr = "".join(f" {x} " if x in "&/" else x for x in furis)
    stem_uri = furis[0] if furis and furis[0].startswith("http") else ""
    return {"label": label.strip(), "foundationUri": fexpr, "stemFoundationUri": stem_uri,
            "error": r.text.strip().strip('"')[:300]}
