"""
hunter/controllers/search_controller.py
=========================================
Owns search state (query string + field selector) and provides the
boolean module filtering logic used by LibraryPane.

Search syntax
-------------
The search bar supports a simple boolean query language:

    word          Simple substring match in the selected field.
    A + B         AND — module must match both A and B.
    A | B         OR  — module must match either A or B.
    -word         NOT — exclude modules that match this term.

Operator precedence: ``|`` (OR) is evaluated first to split the query
into groups; within each group ``+`` (AND) is evaluated left to right;
``-`` (NOT) negates a single AND term.

Examples::

    aws                        All modules containing "aws"
    T1078 + cloud              Modules with both T1078 and "cloud"
    apt33 | apt34              Modules matching either APT group
    endpoint + -windows        Endpoint modules that are NOT windows-specific

Fields
------
"All Fields"  Name + tags + MITRE + author + category + priority + action titles
"Name"        Module name only
"Tags"        Tags list only
"MITRE"       MITRE technique IDs only (supports partial: "T1059" matches "T1059.001")
"""


class SearchController:
    """Manages the active search query, field selector, and module filtering."""

    FIELDS = ("All Fields", "Name", "Tags", "MITRE")

    def __init__(self):
        # Current query string, already lowercased for fast comparison
        self.query: str = ""
        # Which field(s) to search within
        self.field: str = "All Fields"

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_query(self, q: str) -> None:
        """Update the search query (lowercased for case-insensitive matching)."""
        self.query = q.lower().strip()

    def set_field(self, field: str) -> None:
        """Update the active search field; silently ignores unknown values."""
        if field in self.FIELDS:
            self.field = field

    # ── Filtering ─────────────────────────────────────────────────────────────

    def filter(self, modules: list[dict], category: str) -> list[dict]:
        """Return only the modules that match the current category and query.

        Category filtering is applied first (fast set lookup), then the
        full boolean search is applied to the remaining modules.
        """
        return [
            m for m in modules
            if (category == "All" or m.get("category") == category)
            and self._module_matches(m)
        ]

    # ── Private: single-term hit check ───────────────────────────────────────

    def _term_hit(self, mod: dict, term: str) -> bool:
        """Return True if *term* is found anywhere in *mod* under the active field.

        Uses pre-cached ``_search_*`` fields (populated by
        ``module_store.cache_search_fields``) for zero-allocation string
        comparison at query time.
        """
        if not term:
            return True   # empty term always matches

        f = self.field

        # Name field
        if f in ("All Fields", "Name"):
            if term in mod.get("_search_name", mod["name"].lower()):
                return True

        # Tags field — check each tag
        if f in ("All Fields", "Tags"):
            if any(term in t for t in mod.get("_search_tags", [])):
                return True

        # MITRE field — partial match supported (e.g. "T1059" hits "T1059.001")
        if f in ("All Fields", "MITRE"):
            if any(term in t for t in mod.get("_search_mitre", [])):
                return True

        # Extra fields only checked for "All Fields"
        if f == "All Fields":
            if term in mod.get("_search_author", ""):
                return True
            if term in mod.get("_search_cat", ""):
                return True
            if term in mod.get("_search_prio", ""):
                return True
            if any(term in t for t in mod.get("_search_titles", [])):
                return True

        return False

    # ── Private: full boolean query evaluation ────────────────────────────────

    def _module_matches(self, mod: dict) -> bool:
        """Evaluate the full boolean query against *mod*.

        Algorithm:
        1. Split query on ``|`` to get OR-groups.
        2. The module matches if ANY OR-group matches.
        3. An OR-group matches if ALL its AND-terms (+) match.
        4. A NOT term (-word) is satisfied when the word does NOT hit.
        """
        q = self.query
        if not q:
            return True   # empty search shows everything

        # OR-level split
        for or_group in [g.strip() for g in q.split("|") if g.strip()]:
            group_ok = True

            # AND-level split within this OR-group
            for term in [t.strip() for t in or_group.split("+") if t.strip()]:
                if term.startswith("-"):
                    # NOT: the term after "-" must NOT match
                    bare = term[1:].strip()
                    if bare and self._term_hit(mod, bare):
                        group_ok = False
                        break
                else:
                    # Positive match required
                    if not self._term_hit(mod, term):
                        group_ok = False
                        break

            if group_ok:
                # This OR-group satisfied — module matches overall
                return True

        return False   # no OR-group was satisfied
