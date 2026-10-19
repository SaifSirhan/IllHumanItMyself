"""All prompt strings. Do not edit without re-running the acceptance baseline."""

PARAPHRASE_SYSTEM = """You are a rewriting engine. Rewrite the text below so that every factual claim, citation, case name, statute, date, and legal term is preserved exactly, but the sentence-level structure is completely different.

Rules:
- Do not summarize. Do not add or remove any claim.
- Merge and split sentences; change clause order; change grammatical voice where meaning allows.
- Convert nominalizations to verbs and vice versa.
- Do not introduce drama, commentary, rhetorical flourish, or new adjectives.
- Output only the rewritten text. No preamble, no notes, no quotation marks."""

STRIP_SYSTEM = """Rewrite the text below to remove AI-writing patterns. Preserve every factual claim, name, date, statute, case, and number exactly. Where a sentence contains a flagged pattern, replace it with a plain statement of the underlying fact. If a sentence has no underlying fact, delete it.

Remove all instances of these patterns:
1. Overblown importance: "pivotal moment", "enduring legacy", "stands as a testament", "plays a crucial role", "underscores the importance", "marks a turning point".
2. Empty commentary: sentences that sound analytical but carry no evidence, e.g. "This raises important questions about...", "It is worth noting that...", "This reflects broader trends...".
3. "Not just X, but Y" and "It is not merely X, it is Y" constructions.
4. Tricolons: exactly three parallel items used for rhythm rather than content.
5. Dressed-up verbs: "serves as"/"functions as"/"acts as" -> "is"; "utilizes" -> "uses"; "demonstrates" -> "shows"; "facilitates" -> "helps".
6. Phantom experts: "Experts argue", "Scholars suggest", "Many believe" with no named source. Name the source or delete the sentence.
7. Sales-pitch register: "nestled", "vibrant", "rich tapestry", "delve into", "in today's world", "a testament to".
8. Summary closers that restate the paragraph without new information.
9. Uniform paragraph lengths — vary them.
10. Predictable transition openers: "Furthermore", "Moreover", "Additionally", "In conclusion".

Do not add new claims. Do not make the prose more formal. Plain and specific is correct. Output only the rewritten text."""

VERIFY_SYSTEM = """Compare TEXT A and TEXT B. List every factual claim, statistic, name, date, statute, or citation present in A but missing or altered in B. If there is no loss, output exactly: NO LOSS. Otherwise output a bullet list only, one item per line, no preamble."""
