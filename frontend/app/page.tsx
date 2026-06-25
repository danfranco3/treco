"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useInView } from "motion/react";
import { Leaf, ExternalLink, ArrowRight, CheckCircle2, Bot, BarChart3, Terminal, Zap } from "lucide-react";

const GITHUB_URL = "https://github.com/danfranco3/treco";

function FadeUp({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <div
      className={className}
      style={{
        animation: `fadeUp 0.5s ease-out ${delay}s both`,
      }}
    >
      {children}
    </div>
  );
}

function TerminalBlock() {
  const lines = [
    { prompt: "$", text: "pip install treco" },
    { prompt: "$", text: "treco init" },
    { prompt: "",  text: "✓ Agent registered  ·  workspace: my-project" },
    { prompt: "",  text: "✓ Claude Code hooks wired" },
    { prompt: "",  text: "✓ Dashboard at http://localhost:3000" },
    { prompt: "$", text: "treco start" },
    { prompt: "",  text: "◎ aurora  →  working on AUTH-42" },
  ];
  const [visible, setVisible] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i++;
      setVisible(i);
      if (i >= lines.length) clearInterval(id);
    }, 260);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView]);

  return (
    <div ref={ref} className="rounded-xl bg-stone-900 border border-stone-800 p-5 font-mono text-sm overflow-x-auto shadow-modal">
      <div className="flex items-center gap-1.5 mb-4">
        <span className="w-3 h-3 rounded-full bg-red-500/70" />
        <span className="w-3 h-3 rounded-full bg-amber-500/70" />
        <span className="w-3 h-3 rounded-full bg-green-500/70" />
        <span className="ml-2 text-stone-500 text-xs">~/my-project</span>
      </div>
      {lines.slice(0, visible).map((l, i) => (
        <div key={i} className="flex gap-3 leading-6">
          <span className="text-green-400 select-none w-3">{l.prompt}</span>
          <span className={l.prompt ? "text-stone-100" : "text-stone-400"}>{l.text}</span>
        </div>
      ))}
      {visible < lines.length && (
        <div className="flex gap-3 leading-6">
          <span className="text-green-400 select-none w-3">{lines[visible]?.prompt ?? ""}</span>
          <span className="inline-block w-2 h-4 bg-green-400 animate-pulse" />
        </div>
      )}
    </div>
  );
}

const FEATURES = [
  {
    Icon: Bot,
    title: "Live agent kanban",
    body: "Every agent visible: idle, working, errored. Left-edge indicator pulses while active. Updates in real time via SSE.",
  },
  {
    Icon: CheckCircle2,
    title: "Criteria checklist",
    body: "Each ticket's acceptance criteria tick off as the agent completes them. Agent name and timestamp on every check.",
  },
  {
    Icon: BarChart3,
    title: "Cost per session",
    body: "Tokens in, tokens out, estimated USD. Per-model breakdown, per-event bar chart. Know what every session costs.",
  },
  {
    Icon: Terminal,
    title: "Event feed",
    body: "Terminal-style log of every tool call, criterion check, and session event. Live-streamed. Searchable with Cmd+K.",
  },
];

const WORKS_WITH = ["Claude Code", "Cursor", "LangChain", "CrewAI", "AutoGen", "Any HTTP agent"];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[var(--green)] flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-base tracking-tight text-[var(--text)]">Treco</span>
        </div>
        <div className="flex items-center gap-5">
          <Link href="/dashboard" className="text-sm text-[var(--text-2)] hover:text-[var(--text)] transition-colors">
            Dashboard
          </Link>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
            className="text-sm text-[var(--text-2)] hover:text-[var(--text)] transition-colors flex items-center gap-1.5">
            <ExternalLink className="w-4 h-4" />
            GitHub
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium bg-[var(--green)] text-white hover:bg-[var(--green-2)] transition-colors">
            Get started
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-36 pb-20 px-6 max-w-5xl mx-auto">
        <div style={{ animation: "fadeUp 0.5s ease-out 0s both" }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[var(--green)]/30 bg-[var(--green-3)] text-[var(--green)] text-xs font-medium mb-8">
            <span className="relative flex h-1.5 w-1.5">
              <span className="ping-slow absolute inline-flex h-full w-full rounded-full bg-[var(--green)] opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--green)]" />
            </span>
            open source · AGPL v3
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.08] mb-6 text-[var(--text)]">
            Know exactly what<br />
            your <span className="text-[var(--green)]">agents</span> shipped.
          </h1>

          <p className="text-xl text-[var(--text-2)] max-w-2xl mb-10 leading-relaxed">
            Connect Claude Code, Cursor, or any HTTP agent and get live kanban status,
            acceptance criteria ticking off in real time, and per-session token cost.
            Self-host in two commands. No account required.
          </p>

          <div className="flex items-center gap-4 flex-wrap">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-base font-semibold bg-[var(--green)] text-white hover:bg-[var(--green-2)] transition-colors">
              Get started free
              <ArrowRight className="w-4 h-4" />
            </a>
            <Link href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-base font-medium border border-[var(--border)] text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors">
              View live demo
            </Link>
          </div>
        </div>

        <FadeUp className="mt-16" delay={0.15}>
          <TerminalBlock />
        </FadeUp>
      </section>

      {/* Works with */}
      <FadeUp className="py-12 px-6 border-y border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-5xl mx-auto">
          <p className="text-xs text-[var(--text-3)] font-medium uppercase tracking-widest mb-6 text-center">
            Works with
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {WORKS_WITH.map((name) => (
              <span key={name}
                className="px-4 py-2 rounded-full border border-[var(--border)] text-sm text-[var(--text-2)] bg-[var(--bg)] shadow-card">
                {name}
              </span>
            ))}
          </div>
        </div>
      </FadeUp>

      {/* Features */}
      <section className="py-24 px-6 max-w-5xl mx-auto">
        <FadeUp>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4 text-[var(--text)]">
            One dashboard. Every session on the record.
          </h2>
          <p className="text-[var(--text-2)] text-lg max-w-xl mb-16">
            No polling. No manual status updates. Treco streams events directly from the agent — so you know what ran, what it cost, and whether it hit every criterion.
          </p>
        </FadeUp>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FEATURES.map((f, i) => (
            <FadeUp key={f.title} delay={i * 0.07}>
              <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 h-full shadow-card hover:shadow-card-hover transition-shadow">
                <div className="w-10 h-10 rounded-xl bg-[var(--green-3)] flex items-center justify-center mb-4">
                  <f.Icon className="w-5 h-5 text-[var(--green)]" />
                </div>
                <h3 className="text-base font-semibold text-[var(--text)] mb-2">{f.title}</h3>
                <p className="text-sm text-[var(--text-2)] leading-relaxed">{f.body}</p>
              </div>
            </FadeUp>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 px-6 bg-[var(--surface)] border-y border-[var(--border)]">
        <div className="max-w-5xl mx-auto">
          <FadeUp>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-16 text-center text-[var(--text)]">
              Two commands. Live in under a minute.
            </h2>
          </FadeUp>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
            {[
              {
                n: "01",
                title: "Install and init",
                body: "pip install treco && treco init registers your agent, starts a local server, and wires Claude Code hooks automatically.",
                code: "pip install treco\ntreco init",
              },
              {
                n: "02",
                title: "Create or import a ticket",
                body: "Create a ticket from the CLI or import from GitHub Issues, Linear, or Jira via the dashboard. Acceptance criteria are extracted automatically.",
                code: "treco new \"Fix login bug\"\n# or import via dashboard",
              },
              {
                n: "03",
                title: "Run your agent",
                body: "Start Claude Code normally. Treco captures every tool call, token count, and criterion completion in real time.",
                code: "treco start\nclaude \"implement the issue\"",
              },
            ].map((s, i) => (
              <FadeUp key={s.n} delay={i * 0.1}>
                <div className="flex flex-col gap-4">
                  <span className="text-4xl font-bold text-[var(--green)] font-mono">{s.n}</span>
                  <h3 className="text-lg font-semibold text-[var(--text)]">{s.title}</h3>
                  <p className="text-sm text-[var(--text-2)] leading-relaxed">{s.body}</p>
                  <pre className="mt-auto text-xs font-mono bg-stone-900 border border-stone-800 rounded-lg px-4 py-3 text-green-400 leading-5 whitespace-pre overflow-x-auto">{s.code}</pre>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 border-t border-[var(--border)]">
        <FadeUp className="max-w-2xl mx-auto text-center">
          <div className="w-14 h-14 rounded-2xl bg-[var(--green)] flex items-center justify-center mx-auto mb-6">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-[var(--text)]">
            Ship with your agents.<br />Know what they built.
          </h2>
          <p className="text-[var(--text-2)] text-lg mb-10">
            Open source. AGPL v3. Self-host in two commands. No account required.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg px-8 py-3 text-base font-semibold bg-[var(--green)] text-white hover:bg-[var(--green-2)] transition-colors">
              Get started free
              <ArrowRight className="w-4 h-4" />
            </a>
            <Link href="/dashboard"
              className="inline-flex items-center rounded-lg px-8 py-3 text-base font-medium border border-[var(--border)] text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors">
              View demo
            </Link>
          </div>
          <p className="text-xs text-[var(--text-3)] mt-8 font-mono">
            pip install treco · treco init · open localhost:3000
          </p>
        </FadeUp>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-5xl mx-auto flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-[var(--green)] flex items-center justify-center">
              <Leaf className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-sm text-[var(--text)]">Treco</span>
            <span className="text-[var(--text-3)] text-xs ml-1">agent observability</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-[var(--text-3)]">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--text)] transition-colors flex items-center gap-1.5">
              <ExternalLink className="w-3.5 h-3.5" />
              GitHub
            </a>
            <Link href="/dashboard" className="hover:text-[var(--text)] transition-colors">Dashboard</Link>
            <span>AGPL v3</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
