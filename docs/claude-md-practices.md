# CLAUDE.md Authoring Practices

Researched 2026-07-06. Rules we follow for keeping `CLAUDE.md` effective. Sources at bottom.

## Size

- **Hard ceiling: under 200 lines.** Practical sweet spot: **80–120 lines.** Beyond ~200, Claude physically cannot hold all rules in working memory while also doing the task — rules get dropped, not defied.
- Every line spends "instruction budget." If a line doesn't change a decision, cut it.

## What belongs in CLAUDE.md

- Information that **materially changes decisions** and that Claude **cannot infer from the code**: the privacy crux, the no-CI rule, the filename-is-identity convention, where secrets live.
- Stable, always-relevant, project-wide facts.

## What does NOT belong

- Anything Claude can read from the code itself (file structure it can glob, framework it can see in `package.json`).
- Personality/pep-talk ("be a senior engineer", "think step by step") — no behavior change, pure budget waste.
- Deep, topic-specific, or occasionally-relevant detail → put it in a **linked doc** under `docs/` and reference it, so it loads only when needed.

## Structure

- Markdown headers + bullets, grouped by topic.
- Lead with the **non-negotiables** (the "do not change" list) — highest signal first.
- Keep the root file small and stable; churn lives in the linked docs.

## Modular pattern (what we do)

- `CLAUDE.md` = lean index + non-negotiables + pointers.
- `docs/*.md` = the deep material (orchestration, Mapy API, testing, open questions). Referenced by path so a session opens them on demand rather than paying for them at every launch.
- Path-scoped rules (`.claude/rules/`) are an option if we later want instructions that load only when touching matching files.

## Maintenance

- Revisit when a decision changes; delete stale lines rather than appending.
- If the file creeps over ~150 lines, move a section into a `docs/` file and leave a one-line pointer.

## Sources

- [Claude Code memory docs](https://code.claude.com/docs/en/memory)
- [The Complete Guide to CLAUDE.md](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)
- [Claude Code memory explained](https://joseparreogarcia.substack.com/p/claude-code-memory-explained)
