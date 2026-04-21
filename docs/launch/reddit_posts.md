# Reddit Launch Post Drafts

**Date written:** 2026-04-21
**Embargo:** staggered Mon–Wed launch week
**Target subs (draft order):** `r/folklore`, `r/mythology`, `r/AskReligiousStudies`, `r/AskAnthropology`, `r/classics`

Each post is tailored to the sub's norms: academic subs get the methodology + integrity pitch, folklore/mythology subs get the discovery + browsability pitch. Do not post the same text across subs — mods will remove for spam.

**Golden rules for posting:**
1. Post from a multi-year-old account with subreddit-native history. Otherwise mods assume self-promo.
2. Always disclose that you're the creator. "I built this" is fine; "Just found this cool site" is dishonest.
3. Link to the landing page (`/`) or a relevant collection, never to a specific entity. The sub decides what's interesting.
4. Do NOT cross-post for at least 48h between subs.
5. Answer every top-level comment within 4h on launch day.

---

## 1. r/folklore (Monday, ~1800 ET)

**Title:**
> I built a source-tracked database of folk entities and cryptids — 2,000+ spirits, nature entities, and creatures from global traditions, with provenance for every claim

**Body:**

I've been building REALMS for a few months. It's a free, open, ad-free database of spiritual entities from folk and traditional religious traditions — every entry tied back to a source text with integrity checks you can inspect.

Examples folks here might find interesting:

- [Chullachaqui](/entity/chullachaqui/) — Amazonian forest spirit with one foot smaller than the other
- [Domovoi](/entity/domovoi/) — Slavic household spirit who lives behind the hearth
- [Wendigo](/entity/wendigo/) — the Algonquian cannibal-spirit entry (note: we stop short of reproducing sacred ritual material, see our [ethics page](/about/ethics/))
- [Full collection of forest & woodland spirits](/collection/forest-spirits/)

Every entity has:
- the source texts it was extracted from (Wikipedia, Internet Archive monographs, PubMed abstracts)
- a verbatim quote supporting every claim
- a nightly integrity audit (currently running at >99% — [live dashboard](/about/methodology/))
- CC-BY-4.0 licensed data — download the whole thing if you want

No accounts, no tracking, no ads. "Report an issue" button on every entity page.

Would love to know which entries are wrong or thin — folklore has a hundred regional variants and we definitely have gaps.

**[github.com/apeters247/realms](https://github.com/apeters247/realms)** — source code + issues.

---

## 2. r/mythology (Tuesday, ~1200 ET)

**Title:**
> A searchable graph of deities, spirits, and cryptids linked by family/syncretism across 95+ traditions (free, CC-licensed, no ads)

**Body:**

REALMS is a knowledge base I've been building — it treats deities, orishas, ancestors, tricksters, psychopomps etc. as nodes in a graph, with typed edges like parent_of, consort_of, syncretized_with.

Couple of things you might find fun:

- [Filter by tradition](/graph/) — pick "Yoruba" and you get a little family tree. Switch to "Santería" to see how it mapped onto Catholic saints.
- [Collections](/collections/) — auto-generated thematic groupings (solar deities, psychopomps, tricksters, household spirits, etc.)
- [Timeline](/timeline/) — entities placed on a century-scale chart by first-attested documentation
- [Map](/map/) — entities located by their geographical tradition

Two things I specifically optimized for:

1. **Attribution.** Every field has a verbatim source quote. You can click back to the source text.
2. **Relationships between traditions.** Syncretism is a first-class edge type. Orishas that got mapped onto Catholic saints during the Atlantic slave trade are linked both ways.

No ads, no signup. Dataset is CC-BY-4.0. Tell me where it's wrong.

---

## 3. r/AskReligiousStudies (Wednesday, ~1000 ET)

**Title:**
> [Resource] REALMS — a provenance-tracked database of religious entities with public integrity metrics; looking for feedback from the scholarly side

**Body:**

Built a research tool and would value the sub's scrutiny. REALMS is a knowledge base of religious and folk entities — 2,000+ entries across 95+ traditions — with an explicit methodology and a measurable integrity standard. Relevant mechanics:

- **Extraction pipeline**: LLM (Claude Sonnet 4.5) extracts structured entity records from Wikipedia, archive.org public-domain ethnography, and PubMed abstracts. Prompt version v4; every field has a verbatim source quote.
- **Verification**: two independent stages. Stage 1 deterministically checks the quote exists in the source chunk. Stage 2 uses a different LLM (Gemini 2.0 Flash) to judge whether the quote supports the claim.
- **Oracle audit**: nightly random sample (~20 claims/day) submitted to Claude Opus for independent judgement. Corpus-level error rate exposed at [`/integrity/stats`](/integrity/stats) and rendered as a badge on our [methodology page](/about/methodology/).
- **Tier scope**: classical religious traditions and regional folklore/cryptids only. We hard-exclude modern entheogenic visionary material, New Age, and modern occultism. The [ethics page](/about/ethics/) explains why.
- **Outputs**: per-entity BibTeX, CSL-JSON (Zotero/Mendeley), JSON, plus full dataset dump. Licensed CC-BY-4.0.

What I'd love:
- Pointers to under-represented traditions (non-English sources especially)
- Calls for redactions on material you think shouldn't be reproduced even at encyclopedic granularity
- Pushback on the tier boundaries — where should the line actually be?

Source & issue tracker: **[github.com/apeters247/realms](https://github.com/apeters247/realms)**. Happy to DM about contributions if you have domain expertise.

---

## 4. r/AskAnthropology (Wednesday evening, ~2000 ET)

**Title:**
> [Resource, seeking feedback] Cross-traditional graph of spirit entities with source provenance — mainly built to stop conflating Tier-1 ethnography with Tier-3 psychonaut material

**Body:**

The personal itch behind REALMS was a frustration with existing cross-tradition databases: they conflate well-attested ethnographic entities (orishas, Sumerian gods, wendigos, yakshas) with late-modern entities that have no comparable source base (machine elves, tulpamancy constructs, UFO contactee material). So REALMS draws an explicit scope boundary:

- **In:** Tier 1 (classical religious + indigenous) + Tier 2 (regional folklore/cryptids)
- **Out:** Tier 3 (entheogenic visionary), Tier 4 (modern occult / fiction / UFO-adjacent)

[Ethics page](/about/ethics/) explains the reasoning. I'd love this sub's critique of that boundary especially — it's doing a lot of work and I'm not confident it's in the right place.

Every entity has:
- source-level provenance (every claim has a verbatim quote from an identified source)
- a [four-stage verification pipeline](/about/methodology/) with a live integrity badge
- CC-BY-4.0 data dump if you want to analyze it

Known caveats:
- English-only sources; non-English ethnography is under-represented
- Wikipedia skews what's "popular" — I'm working on archive.org to correct
- The LLM extraction does over-extract on "classes of spirits" vs individuals sometimes

Source code: **[github.com/apeters247/realms](https://github.com/apeters247/realms)**. Issue tracker is public; I review every "Report an issue" submission.

---

## 5. r/classics (launch week + 1, Tues ~1000 ET)

**Title:**
> Graph of the Greek & Roman pantheon, linked to their Near Eastern + Etruscan antecedents (CC-BY data, citation export)

**Body:**

The classical corner of REALMS is probably the most complete. Some entry points:

- [Greek pantheon filter](/graph/?tradition=Greek)
- [Roman pantheon](/graph/?tradition=Roman) — see how many entries are explicitly flagged as Greek syncretisations
- [Etruscan pantheon](/graph/?tradition=Etruscan) — sparser but the links to Roman-period borrowings are clickable
- [Near Eastern predecessors](/graph/?tradition=Sumerian) — Inanna → Ishtar → Astarte → Aphrodite lineage is mapped as typed edges

Every entity has inline BibTeX / APA / MLA / Chicago citation tools, plus CSL-JSON for Zotero / Mendeley. Dataset is downloadable, CC-BY-4.0.

Would especially love pointers on the boundary between Roman state cult and regional genii locorum — current coverage is weaker there.

Source and issues: **[github.com/apeters247/realms](https://github.com/apeters247/realms)**.

---

## Post-launch response playbook

**Common hostile comments & canonical responses:**

> "This is just Wikipedia with extra steps."

Wikipedia is one of three source layers. Every claim has a verbatim source quote that's cross-checked by an independent LLM; you can't click one field and see the quote that backs it on Wikipedia. Also Wikipedia doesn't support typed relationships — syncretism between orishas and saints isn't queryable there.

> "You're using LLMs so it's all made up."

Every extraction is gated by (a) a deterministic quote-presence check and (b) an independent semantic check. Nightly oracle sampling measures the actual error rate; see `/integrity/stats`. If you find a made-up claim, use the "Report an issue" button and we'll remove it.

> "This is cultural appropriation / you shouldn't be doing this at all."

Fair concern. We wrote [an ethics page](/about/ethics/) explicitly to engage with it. We exclude ritual procedure; we prefer living-practitioner sources when available; we link back to primary sources so readers can trace our characterisations. Where we're doing it wrong, please use the ethics issue type on the feedback form — it routes to a human reviewer.

> "Why aren't [tradition X] / [my favorite spirit] in there?"

Because coverage is uneven and LLM-extraction depends on having digitized public-domain source material. Please open a GitHub issue with the tradition name and any source material pointers you have.

> "This should be on [platform Y]."

It's all open-source and CC-BY. If someone wants to rehost, port, or fork, that's what the license is for. We focus on getting the data right; anyone can build a better UI.

---

## Metrics to watch post-launch

- **First 24h:** unique IPs, 404 rate, 5xx rate, error-reporting submissions
- **First 7d:** Reddit comment sentiment tally, time-on-page, bounce rate, social shares
- **First 30d:** GSC indexing coverage, backlinks, feedback-report resolution throughput

---

## Thank-you DMs

For any commenter who gives particularly good feedback (not surface-level), DM within 24h thanking them and inviting further engagement. No offers of anything in exchange — just gratitude.
