import {
  formatRelativeTime,
  formatTime,
  criteriaProgress,
  toMap,
  toNameMap,
  sortChronological,
  buildDefaultPrompt,
} from "../lib/utils";
import type { Ticket } from "../lib/types";

const NOW = new Date("2024-06-01T12:00:00Z").getTime();

describe("formatRelativeTime", () => {
  beforeEach(() => {
    jest.spyOn(Date, "now").mockReturnValue(NOW);
  });
  afterEach(() => jest.restoreAllMocks());

  it("shows seconds for <60s ago", () => {
    const iso = new Date(NOW - 30_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("30s ago");
  });

  it("shows minutes for <60m ago", () => {
    const iso = new Date(NOW - 5 * 60_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("5m ago");
  });

  it("shows hours for <24h ago", () => {
    const iso = new Date(NOW - 3 * 3600_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("3h ago");
  });

  it("shows locale date for >=24h ago", () => {
    const iso = new Date(NOW - 48 * 3600_000).toISOString();
    const result = formatRelativeTime(iso);
    expect(result).not.toMatch(/ago/);
  });
});

describe("formatTime", () => {
  it("returns a time string", () => {
    const result = formatTime("2024-06-01T12:34:56Z");
    expect(result).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});

describe("criteriaProgress", () => {
  it("returns 0 for empty list", () => {
    expect(criteriaProgress([])).toBe(0);
  });

  it("returns 0 when none done", () => {
    expect(criteriaProgress([{ done: false }, { done: false }])).toBe(0);
  });

  it("returns 100 when all done", () => {
    expect(criteriaProgress([{ done: true }, { done: true }])).toBe(100);
  });

  it("returns 50 for half done", () => {
    expect(criteriaProgress([{ done: true }, { done: false }])).toBe(50);
  });

  it("rounds to nearest integer", () => {
    const result = criteriaProgress([{ done: true }, { done: false }, { done: false }]);
    expect(result).toBe(33);
  });
});

describe("toMap", () => {
  it("indexes by id", () => {
    const items = [
      { id: "a", val: 1 },
      { id: "b", val: 2 },
    ];
    const map = toMap(items);
    expect(map["a"]).toEqual({ id: "a", val: 1 });
    expect(map["b"]).toEqual({ id: "b", val: 2 });
  });

  it("returns empty for empty array", () => {
    expect(toMap([])).toEqual({});
  });

  it("later item overwrites earlier for duplicate id", () => {
    const items = [
      { id: "x", val: 1 },
      { id: "x", val: 2 },
    ];
    expect(toMap(items)["x"].val).toBe(2);
  });
});

describe("toNameMap", () => {
  it("maps id to name", () => {
    const items = [
      { id: "1", name: "Alice" },
      { id: "2", name: "Bob" },
    ];
    const map = toNameMap(items);
    expect(map["1"]).toBe("Alice");
    expect(map["2"]).toBe("Bob");
  });
});

describe("sortChronological", () => {
  it("sorts oldest first", () => {
    const items = [
      { id: "c", created_at: "2024-03-01T00:00:00Z" },
      { id: "a", created_at: "2024-01-01T00:00:00Z" },
      { id: "b", created_at: "2024-02-01T00:00:00Z" },
    ];
    const sorted = sortChronological(items);
    expect(sorted.map((i) => i.id)).toEqual(["a", "b", "c"]);
  });

  it("does not mutate original", () => {
    const items = [
      { id: "b", created_at: "2024-02-01T00:00:00Z" },
      { id: "a", created_at: "2024-01-01T00:00:00Z" },
    ];
    sortChronological(items);
    expect(items[0].id).toBe("b");
  });
});

describe("buildDefaultPrompt", () => {
  const ticket: Ticket = {
    id: "t1",
    workspace_id: "ws1",
    source: "custom",
    source_id: null,
    title: "Fix the bug",
    description: "It crashes on startup",
    status: "open",
    acceptance_criteria: [
      { id: "c1", text: "No crash", done: false },
      { id: "c2", text: "Tests pass", done: true },
    ],
    body: {},
  };

  it("includes ticket title", () => {
    expect(buildDefaultPrompt(ticket)).toContain("Fix the bug");
  });

  it("includes description", () => {
    expect(buildDefaultPrompt(ticket)).toContain("It crashes on startup");
  });

  it("marks done criteria with x", () => {
    const prompt = buildDefaultPrompt(ticket);
    expect(prompt).toContain("[x] Tests pass");
  });

  it("marks undone criteria with space", () => {
    const prompt = buildDefaultPrompt(ticket);
    expect(prompt).toContain("[ ] No crash");
  });

  it("includes treco check instruction", () => {
    expect(buildDefaultPrompt(ticket)).toContain("treco check");
  });

  it("handles null description", () => {
    const t: Ticket = { ...ticket, description: null };
    const prompt = buildDefaultPrompt(t);
    expect(prompt).toContain("Fix the bug");
    expect(prompt).not.toContain("null");
  });

  it("handles empty criteria", () => {
    const t: Ticket = { ...ticket, acceptance_criteria: [] };
    expect(buildDefaultPrompt(t)).toContain("(none extracted");
  });
});
