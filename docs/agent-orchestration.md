# Agent Orchestration & Prompting Practices

Distilled from Anthropic's guidance and Claude Code docs (researched 2026-07-06). This is the operating manual for how we run agents on this project. Sources at the bottom.

## Core stance

- **Simplicity first.** Add agentic complexity only when a single session stops being enough. Most tasks here are a single focused agent; multi-agent is for parallel, independent work.
- **Transparency.** The orchestrator (main session) states the plan and delegates explicitly. No hidden agent-to-agent side channels.
- **Context-centric decomposition, not role-centric.** Split work by *independent context boundaries* (e.g. "the Python pipeline", "the Leaflet site"), not by handing one agent "write" and another "test" the same file — that creates coordination churn.

## Our orchestration model (decided)

Main session = **orchestrator** (Opus). It plans, delegates to sub-agents, verifies their output, and only then integrates.

Pipeline per deliverable: **developer (Sonnet) → verifier (Opus) → grill-reviewer (Opus) → fix → present.**

- **Autonomy:** run autonomously; **halt only at genuine forks** (a consequential, hard-to-reverse decision or a gap in the spec). Surface the fork, get a decision, continue. Matches the handoff's decision-log discipline.
- **Model split:** builders (developer, tester) on **Sonnet** for cost; critics (verifier, grill-reviewer) on **Opus** for sharper reasoning. This is the evaluator-optimizer pattern — cheap generation, strong evaluation.

## Anthropic's 5 workflow patterns (reference)

1. **Prompt chaining** — sequential steps, each feeding the next. Use when a task cleanly decomposes into ordered stages.
2. **Routing** — classify input, dispatch to a specialist. (e.g. "is this a JS-site task or a Python-pipeline task?")
3. **Parallelization** — fan out independent subtasks, gather results. Best for work with no cross-dependencies (e.g. batch-processing many GPX files, researching several topics at once).
4. **Orchestrator–workers** — central LLM dynamically splits a task it can't pre-plan, delegates, synthesizes. Our default.
5. **Evaluator–optimizer** — one agent generates, another critiques in a loop. Our build→verify→grill pipeline.

## Rules for writing sub-agents

- **Description drives delegation** — be specific about *when* to use the agent, not just what it does.
- **Scope tools to role.** Reviewers/verifiers get read + run only (no Edit/Write) so they can't "fix" instead of report. Builders get full edit access.
- **Self-sufficient prompts.** A sub-agent starts cold — it re-derives context. Give it everything; never tell it to "wait on" or "reference the parent's" state.
- **Fresh eyes for review.** Spawn a *new* agent for verification/critique so it carries none of the builder's assumptions.
- **Independent tasks parallelize; coupled logic stays in one session.**

## Anti-patterns to avoid

- Multiple agents editing the **same file** → conflicts.
- Over-specialization → a zoo of narrow agents nobody remembers to use. Keep the roster small (we run 4).
- Complex agent-to-agent coordination → if teammates must challenge each other live, that's an *agent team*, not sub-agents.
- Sequential *dependent* work split across agents → keep tightly coupled steps together.
- Trusting sub-agent output unverified → always verify before integrating.

## Prompting checklist (per delegation)

- [ ] Goal stated in one sentence, plus the definition of done.
- [ ] All context the cold agent needs (paths, conventions, the privacy crux).
- [ ] Explicit scope boundaries (what NOT to touch — e.g. `raw/`, `done/`, no CI).
- [ ] Output format (what to report back).
- [ ] Which forks require halting vs. deciding autonomously.

## Sources

- [When to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them)
- [Subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code)
- [Multi-agent coordination patterns](https://claude.com/blog/multi-agent-coordination-patterns)
- [Building Effective AI Agents (Anthropic)](https://www.anthropic.com/research/building-effective-agents)
- [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams)
