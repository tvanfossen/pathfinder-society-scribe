#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, time, sys, re
from typing import Any, Dict, Iterable, List, Optional, Tuple
import httpx
from pathlib import Path

AON_ES = "https://elasticsearch.aonprd.com/aon/_search"
AON_BASE = "https://2e.aonprd.com"

# Full category set (from your aggregation)
CATEGORIES = [
    "feat","equipment","creature","rules","action","spell","class-feature","item-bonus","trait",
    "deity","sidebar","hazard","background","creature-family","weapon","heritage","archetype",
    "category-page","source","relic","familiar-ability","ritual","language","domain","vehicle",
    "animal-companion","article","condition","ancestry","class-sample","creature-ability","curse",
    "kingdom-structure","siege-weapon","armor","creature-adjustment","skill","plane","kingdom-event",
    "class","familiar-specific","disease","deity-category","class-kit","tactic","lesson","bloodline",
    "campsite-meal","patron","skill-general-action","arcane-school","ikon","mystery","warfare-tactic",
    "shield","animal-companion-specialization","weapon-group","epithet","instinct","creature-theme-template",
    "cause","druidic-order","weather-hazard","apparition","mythic-calling","style","warfare-army",
    "arcane-thesis","implement","racket","methodology","muse","hybrid-study","research-field",
    "animal-companion-advanced","armor-group","hellknight-order","hunters-edge","set-relic",
    "conscious-mind","element","way","deviant-ability-classification","doctrine","tradition",
    "innovation","practice","subconscious-mind","tenet","animal-companion-unique",
]

HEADERS = {"User-Agent": "PF2e-Indexer/1.0", "Content-Type": "application/json"}

def open_db(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con

def init_schema(con: sqlite3.Connection, schema_path: str) -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    con.executescript(sql)
    con.commit()

def _norm_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    if u.startswith("http"):
        return u
    if not u.startswith("/"):
        u = "/" + u
    return f"{AON_BASE}{u}"

def _first_nonempty(d: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def _to_int_or_none(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(x)
    except Exception:
        return None

def map_source_to_row(src: Dict[str, Any]) -> Dict[str, Any]:
    # Elastic sources vary in casing; pull common aliases
    name = _first_nonempty(src, ["name","Name","title","Title"])
    traits = _first_nonempty(src, ["traits","Traits"])
    summary = _first_nonempty(src, ["summary","Summary","entry","Entry","desc","Desc"])
    text = _first_nonempty(src, ["text","Text","body","Body","content"])
    url = _first_nonempty(src, ["url","Url","aon_url"])
    level = _to_int_or_none(src.get("level"))
    rarity = _first_nonempty(src, ["rarity","Rarity"])
    traditions = _first_nonempty(src, ["traditions","Traditions"])
    actions = _first_nonempty(src, ["actions","Actions","Action"])
    source = _first_nonempty(src, ["source","Source","book","Book"])
    category = (src.get("category") or src.get("Category") or "").strip()

    row = {
        "category": category,
        "name": name,
        "traits": traits,
        "summary": summary,
        "text": text,
        "url": _norm_url(url),
        "level": level,
        "rarity": rarity,
        "traditions": traditions,
        "actions": actions,
        "source": source,
        "extra": json.dumps(src, ensure_ascii=False),  # keep original fields
    }
    return row

def es_search_category(category: str, batch_size: int = 1000) -> Iterable[Dict[str, Any]]:
    """Iterate all docs in a category using search_after on _doc (from/size > 10k cap)."""
    client = httpx.Client(headers=HEADERS, timeout=30.0)
    search_after = None
    total = 0
    try:
        while True:
            body = {
                "size": batch_size,
                "sort": [{"_doc":"asc"}],
                "query": {"bool": {"filter":[{"term":{"category": category}}]}},
            }
            if search_after is not None:
                body["search_after"] = search_after
            r = client.post(AON_ES, json=body)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break
            for h in hits:
                src = h.get("_source") or {}
                yield src
            total += len(hits)
            search_after = hits[-1].get("sort")
            if not search_after:
                break
    finally:
        client.close()

def rebuild(con: sqlite3.Connection,
            schema_path: str,
            categories: List[str],
            commit_every: int = 2000) -> Tuple[int,int]:
    """Drop & recreate schema, then load all categories and rebuild FTS."""
    init_schema(con, schema_path)

    cur = con.cursor()
    insert_sql = """
    INSERT INTO docs (category, name, traits, summary, text, url, level, rarity, traditions, actions, source, extra)
    VALUES (:category, :name, :traits, :summary, :text, :url, :level, :rarity, :traditions, :actions, :source, :extra)
    """
    n_rows = 0
    t0 = time.perf_counter()
    for cat in categories:
        cat_t0 = time.perf_counter()
        added = 0
        for src in es_search_category(cat):
            row = map_source_to_row(src)
            row["category"] = cat  # ensure normalized
            cur.execute(insert_sql, row)
            n_rows += 1
            added += 1
            if n_rows % commit_every == 0:
                con.commit()
        con.commit()
        dt = time.perf_counter() - cat_t0
        print(f"[idx] {cat:<24} +{added:5d} in {dt:5.2f}s")

    # (Re)build FTS from docs
    print("[fts] refreshing docs_fts …")
    con.execute("DELETE FROM docs_fts;")
    con.execute("""
        INSERT INTO docs_fts(rowid, name, traits, summary, text, category)
        SELECT aon_id, COALESCE(name,''), COALESCE(traits,''), COALESCE(summary,''), COALESCE(text,''), COALESCE(category,'')
        FROM docs;
    """)
    con.commit()
    print(f"[done] {n_rows} rows total in {time.perf_counter()-t0:0.2f}s")
    # sanity
    c = con.execute("SELECT category, COUNT(*) FROM docs GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
    for row in c[:12]:
        print(f"  {row['category']:<24} {row['COUNT(*)']:>6}")
    return n_rows, len(c)

def main():
    ap = argparse.ArgumentParser(description="Rebuild PF2e SQLite DB from AoN Elasticsearch")
    ap.add_argument("--db", default="pf2e.db")
    ap.add_argument("--schema", default="pf2e_index/schema.sql")
    ap.add_argument("--only", nargs="*", help="Limit to specific categories")
    ap.add_argument("--batch", type=int, default=1000)
    args = ap.parse_args()

    cats = args.only or CATEGORIES
    con = open_db(args.db)
    try:
        rebuild(con, args.schema, cats, commit_every=args.batch*2)
    finally:
        con.close()

if __name__ == "__main__":
    main()
