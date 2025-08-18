# pf2e_mcp/tools/db_tools.py
from __future__ import annotations
import os, sqlite3, json, logging, re
from typing import Optional, List, Any, Dict, Iterable, Tuple

from pydantic import BaseModel, Field, conint
from mcp.server.fastmcp import FastMCP
from pf2e_mcp.registry.base import BaseToolRegistry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config / tokenization helpers
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = os.getenv("PF2E_DB_PATH", "pf2e.db")
MAX_TERMS = 32
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{1,30}")
STOPWORDS = {
    "a","an","the","and","or","of","to","in","on","at","for","with","by","from","as","is","are",
    "be","this","that","these","those"
}

def _tokenize(text: str) -> List[str]:
    if not text: return []
    return [t.lower() for t in TOKEN_RE.findall(text)]

def _fts_match_from_query(q: str) -> str:
    toks = [t for t in _tokenize(q) if t not in STOPWORDS][:MAX_TERMS]
    if not toks:
        return ""
    parts = [f"\"{t}\"" for t in toks]
    phrase = f"\"{' '.join(toks)}\""
    return " OR ".join(parts + [phrase])

# ---------------------------------------------------------------------------
# Optional WordNet synonym fallback
# ---------------------------------------------------------------------------
try:
    import nltk  # type: ignore
    from nltk.corpus import wordnet as wn  # type: ignore
    from nltk.stem import WordNetLemmatizer  # type: ignore
    _wn_ok = True
except Exception:
    wn = None
    WordNetLemmatizer = None
    _wn_ok = False

def _ensure_wordnet() -> bool:
    if not _wn_ok:
        return False
    try:
        nltk.data.find("corpora/wordnet")
        nltk.data.find("corpora/omw-1.4")
        return True
    except LookupError:
        return False

def _expand_synonyms(tokens: Iterable[str], cap_per_token: int = 6, cap_total: int = 30) -> List[str]:
    if not _ensure_wordnet():
        return []
    lem = WordNetLemmatizer()
    out: List[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in STOPWORDS or len(tok) < 3:
            continue
        base = lem.lemmatize(tok)
        if base not in seen:
            seen.add(base)
            out.append(base)
        count = 0
        for syn in wn.synsets(base):
            for l in syn.lemmas():
                w = l.name().replace("_", " ").lower()
                if w in STOPWORDS or not w.isascii():
                    continue
                if TOKEN_RE.fullmatch(w.replace(" ", "")) is None:
                    continue
                if w not in seen:
                    seen.add(w)
                    out.append(w)
                    count += 1
                    if count >= cap_per_token:
                        break
            if count >= cap_per_token:
                break
        if len(out) >= cap_total:
            break
    return out

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class DBSearchHit(BaseModel):
    name: str
    category: str
    aon_id: Optional[int] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    traits: Optional[list[str]] = None
    rank: float

class DBSearchResponse(BaseModel):
    query: str
    section: Optional[str] = None
    results: List[DBSearchHit] = Field(default_factory=list)
    used_synonym_fallback: bool = False

class DBGetResponse(BaseModel):
    section: str
    aon_id: int
    name: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    summary: Optional[str] = None
    traits: Optional[list[str]] = None
    source: Optional[str] = None
    level: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _open(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON;")
    return con

def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    cols = set()
    for r in con.execute(f"PRAGMA table_info({table});"):
        cols.add(r["name"])
    return cols

def _detect_columns(db_path: str) -> Tuple[str, str]:
    """
    Returns (traits_col, data_col) from docs table.
    Prefers JSON columns if present, but falls back to plain text names.
    """
    with _open(db_path) as con:
        cols = _table_columns(con, "docs")

    traits_col = "traits_json" if "traits_json" in cols else ("traits" if "traits" in cols else None)
    data_col = "data_json"   if "data_json"   in cols else ("data"   if "data"   in cols else None)

    if traits_col is None:
        log.warning("docs table has no traits_json/traits column; traits will be None in results.")
        traits_col = ""  # use blank to build COALESCE safely

    if data_col is None:
        log.warning("docs table has no data_json/data column; data will be {} in results.")
        data_col = ""  # blank allowed; we’ll COALESCE to NULL

    return traits_col, data_col

def _rows_to_hits(rows: List[sqlite3.Row]) -> List[DBSearchHit]:
    results: list[DBSearchHit] = []
    for r in rows:
        traits = None
        try:
            traits_raw = r["traits_json"]
            if traits_raw:
                # traits_raw may already be JSON text; try to load
                traits = json.loads(traits_raw)
            elif isinstance(traits_raw, list):
                traits = traits_raw
        except Exception:
            # Best effort: if plain text traits, split by commas
            try:
                if r["traits_json"]:
                    traits = [t.strip() for t in str(r["traits_json"]).split(",") if t.strip()]
            except Exception:
                pass

        results.append(DBSearchHit(
            name=r["name"],
            category=r["category"],
            aon_id=r["aon_id"],
            url=r["url"],
            summary=r["summary"],
            traits=traits,
            rank=float(r["rank"]),
        ))
    return results

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------
class PF2eDBToolset(BaseToolRegistry):
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # Detect column names once
        self.traits_col, self.data_col = _detect_columns(self.db_path)
        log.info("PF2eDBToolset: using traits_col=%r data_col=%r", self.traits_col, self.data_col)

    def register(self, mcp: FastMCP) -> None:

        @mcp.tool(name="pf2e_db_search")
        def pf2e_db_search(
            query: str,
            section: Optional[str] = None,
            limit: conint(ge=1, le=50) = 10,
            synonym_fallback: bool = True,
        ) -> DBSearchResponse:
            """
            Full-text search the local PF2e DB (FTS5). Optional section/category filter (e.g., 'spell','feat','action').
            If no results and synonym_fallback=True, retry once with WordNet-expanded terms.
            """
            q = (query or "").strip()
            if not q:
                return DBSearchResponse(query=query, section=section, results=[])

            match = _fts_match_from_query(q)
            if not match:
                return DBSearchResponse(query=q, section=section, results=[])

            log.info("pf2e_db_search: q=%r section=%r limit=%d", q, section, int(limit))
            log.debug("pf2e_db_search: MATCH=%s", match)

            # Build SELECT with robust trait aliasing
            # Use COALESCE to gracefully handle missing columns
            traits_expr = "NULL"
            if self.traits_col:
                traits_expr = f"COALESCE(d.{self.traits_col}, NULL)"

            base_sql = f"""
            SELECT
                d.name,
                d.category,
                d.aon_id,
                d.url,
                d.summary,
                {traits_expr} AS traits_json,
                bm25(docs_fts) AS rank
            FROM docs_fts
            JOIN docs d ON d.aon_id = docs_fts.rowid
            WHERE docs_fts MATCH ? {{section_clause}}
            ORDER BY rank
            LIMIT ?;
            """

            section_clause = ""
            params: list[Any] = [match, int(limit)]
            if section:
                section_clause = "AND d.category = ?"
                base_sql = base_sql.replace("{section_clause}", section_clause)
                params = [match, section, int(limit)]
            else:
                base_sql = base_sql.replace("{section_clause}", "")

            with _open(self.db_path) as con:
                rows = list(con.execute(base_sql, params))
            if rows:
                return DBSearchResponse(query=q, section=section, results=_rows_to_hits(rows), used_synonym_fallback=False)

            # Fallback: synonyms
            if synonym_fallback:
                toks = [t for t in _tokenize(q) if t not in STOPWORDS][:MAX_TERMS]
                expanded = _expand_synonyms(toks, cap_per_token=6, cap_total=30)
                if expanded:
                    exp_match = " OR ".join([f"\"{t}\"" for t in expanded])
                    log.info("pf2e_db_search: fallback with synonyms (%d terms)", len(expanded))
                    log.debug("pf2e_db_search: fallback MATCH=%s", exp_match)
                    fsql = f"""
                    SELECT
                        d.name,
                        d.category,
                        d.aon_id,
                        d.url,
                        d.summary,
                        {traits_expr} AS traits_json,
                        bm25(docs_fts) AS rank
                    FROM docs_fts
                    JOIN docs d ON d.aon_id = docs_fts.rowid
                    WHERE docs_fts MATCH ? {{section_clause}}
                    ORDER BY rank
                    LIMIT ?;
                    """
                    fparams: list[Any] = [exp_match, int(limit)]
                    if section:
                        fsql = fsql.replace("{section_clause}", "AND d.category = ?")
                        fparams = [exp_match, section, int(limit)]
                    else:
                        fsql = fsql.replace("{section_clause}", "")
                    with _open(self.db_path) as con:
                        rows = list(con.execute(fsql, fparams))
                    if rows:
                        return DBSearchResponse(query=q, section=section, results=_rows_to_hits(rows), used_synonym_fallback=True)

            return DBSearchResponse(query=q, section=section, results=[], used_synonym_fallback=False)

        @mcp.tool(name="pf2e_db_get")
        def pf2e_db_get(section: str, aon_id: int) -> DBGetResponse:
            """
            Fetch a single record by category (section) and AoN ID.
            """
            # Build robust SELECT with detected columns
            traits_expr = "NULL"
            if self.traits_col:
                traits_expr = f"COALESCE({self.traits_col}, NULL)"

            data_expr = "NULL"
            if self.data_col:
                data_expr = f"COALESCE({self.data_col}, NULL)"

            sql = f"""
            SELECT
                name,
                url,
                text,
                summary,
                {traits_expr} AS traits_json,
                source,
                level,
                {data_expr} AS data_json
            FROM docs
            WHERE category = ? AND aon_id = ?
            LIMIT 1;
            """

            with _open(self.db_path) as con:
                row = con.execute(sql, [section, aon_id]).fetchone()

            if not row:
                return DBGetResponse(section=section, aon_id=aon_id)

            # traits
            traits = None
            try:
                if row["traits_json"]:
                    traits = json.loads(row["traits_json"])
                elif isinstance(row["traits_json"], str):
                    # try comma-split fallback
                    t = [t.strip() for t in row["traits_json"].split(",") if t.strip()]
                    traits = t or None
            except Exception:
                pass

            # data
            data: Dict[str, Any] = {}
            try:
                if row["data_json"]:
                    data = json.loads(row["data_json"])
            except Exception:
                data = {}

            return DBGetResponse(
                section=section, aon_id=aon_id,
                name=row["name"], url=row["url"], text=row["text"],
                summary=row["summary"], traits=traits, source=row["source"],
                level=row["level"], data=data
            )
