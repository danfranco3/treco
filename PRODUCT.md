# Product

## Register

product

## Users

Software engineers and engineering leads who run AI coding agents (Claude Code, Cursor, Codex) against a ticket backlog. Two modes:

- **Solo developer, live**: watching the dashboard while an agent session is active — like tailing logs but structured. Wants to know if the agent is stuck, how much it has cost, and which criteria have been hit.
- **Solo developer, async**: checking in after a session ends. Wants a clear record of what happened, what was completed, what cost what.
- **Eng lead, multi-agent**: overseeing several agents running in parallel on different tickets. Needs operational awareness: which agents are active, which are blocked, whether anything needs human intervention.

Primary job: trust that agents are making real progress on real work without babysitting them.

## Product Purpose

Treco is a real-time observability layer for AI coding agents. It connects to agent sessions via CLI hooks, captures structured events (tool calls, criteria checks, session end), and surfaces them as a live dashboard: which agent is working on which ticket, how far through the acceptance criteria they are, and how much the session has cost so far.

Success: an engineer can start a Claude Code session, open Treco, and immediately see accurate state — agent active, ticket assigned, criteria ticking off — without any manual instrumentation beyond `treco init`.

## Brand Personality

Clear. Calm. Confident.

The interface doesn't perform busyness. It shows what's happening with precision and lets the engineer get on with other work. No celebration, no alarm — just reliable signal.

Reference: PostHog dark — data-forward, excellent hierarchy, technical credibility without the "hacker" aesthetic. Information dense but never crowded.

## Anti-references

- **AI product aesthetics**: Vercel AI, LangSmith, Weights & Biases — warm neutral backgrounds, gradient text, "magic" framing, cream/lavender palettes. Treco is a tool, not a brand experience.
- **Hackathon dark mode**: glowing neon borders, cyan-on-black glow effects, purple gradients, cyber typography. Looks striking in a demo; destroys trust in daily use.
- **Generic SaaS metrics dashboards**: identical card grids of big numbers with colored icons. Cargo-culted from Datadog; meaningless without context.

## Design Principles

1. **Signal over spectacle.** Every pixel is data or structure. Decoration that doesn't carry meaning is noise that competes with signal.
2. **State communicates.** Motion, color, and weight are reserved for state changes: agent active vs. idle, criterion done vs. pending, session in progress vs. ended. They're not decoration.
3. **Density earns trust.** Developers read dense interfaces the way they read code. Spacious "beginner" layouts feel condescending. Earn density by making it scannable, not by cramming.
4. **Consistency is invisible.** Buttons, badges, loading states, empty states: one vocabulary across all screens. When everything behaves the same way, the tool disappears into the task.
5. **Calm is a feature.** The agent may be doing intense work. The dashboard should feel like a steadily breathing instrument panel, not an alarm. Confidence comes from clarity, not from animation.

## Accessibility & Inclusion

WCAG 2.1 AA. All body text ≥ 4.5:1 contrast. Large text / UI components ≥ 3:1. Full keyboard navigation. Every animation has a `prefers-reduced-motion` fallback (typically instant transition). No color-only state indicators — always pair color with shape, text, or icon.
