# Pair Relationship Classification Prompt (v1)

You decide what relationship, if any, a source text describes between two named spiritual / mythological entities.

## Input
You receive:
- Two entity names: **A** and **B**
- One or more passages of source text where both appear

## Taxonomy

Return **exactly one** label from this list, or `unknown`:

- `parent_of` — A is the mother, father, creator, or progenitor of B
- `child_of` — A is the offspring / emanation of B
- `consort_of` — A and B are spouses / sexual partners (symmetric)
- `sibling_of` — A and B are siblings (symmetric)
- `allied_with` — A and B fight together / are companions (symmetric)
- `enemy_of` — A and B are adversaries (symmetric)
- `teacher_of` — A instructs / initiates B
- `student_of` — A is instructed by B
- `serves` — A is a messenger / servant / assistant of B
- `ruled_by` — A is subordinate to B in a hierarchy
- `manifests_as` — A appears or incarnates as B (same being, different form)
- `aspect_of` — A is one facet / road / path of B (e.g. "Eleguá is an aspect of Eshu")
- `syncretized_with` — A is identified with B across traditions (e.g. orisha ↔ saint)
- `created_by` — A was brought into being by B (one-time act, not ongoing parenthood)
- `associated_with` — A and B appear together in context but with no clearer relationship

Return `unknown` if the passage mentions both but states no relationship.

## Rules

1. **Quote verbatim.** The `quote` field must be a verbatim substring of the passage that supports the label. ≤300 chars. If `unknown`, use an empty string.
2. **Direction matters.** `parent_of` vs `child_of` describes who is whose parent; read carefully. `A parent_of B` means "A is B's parent."
3. **Symmetric labels** (`consort_of`, `sibling_of`, `allied_with`, `enemy_of`, `syncretized_with`): direction doesn't matter.
4. **Confidence 0.0–1.0**: 0.9+ when the text says it explicitly; 0.5–0.7 when it's implied; below 0.5 — prefer `unknown`.
5. Return **only JSON**. No prose, no markdown.

## Output Schema

```json
{
  "label": "parent_of" | "child_of" | "...",
  "confidence": 0.0,
  "quote": "verbatim substring ≤300 chars or empty"
}
```

## Input

A: **{{NAME_A}}**
B: **{{NAME_B}}**

Passages:
```
{{PASSAGES}}
```

Return only the JSON object.
