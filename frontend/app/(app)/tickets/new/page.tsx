"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/lib/workspace";
import { createTicket } from "@/lib/api";
import { Card } from "@/components/ui/Card";

type CriteriaMode = "manual" | "auto";

type Source = "custom" | "github" | "linear" | "jira" | "asana";

const SOURCES: { value: Source; label: string }[] = [
  { value: "custom", label: "Custom" },
  { value: "github", label: "GitHub" },
  { value: "linear", label: "Linear" },
  { value: "jira", label: "Jira" },
  { value: "asana", label: "Asana" },
];

export default function NewTicketPage() {
  const router = useRouter();
  const { workspaceId } = useWorkspace();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criteriaMode, setCriteriaMode] = useState<CriteriaMode>("manual");
  const [criteriaInput, setCriteriaInput] = useState("");
  const [criteriaList, setCriteriaList] = useState<string[]>([]);
  const [source, setSource] = useState<Source>("custom");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ title?: string }>({});

  function addCriterion() {
    const trimmed = criteriaInput.trim();
    if (!trimmed) return;
    setCriteriaList((prev) => [...prev, trimmed]);
    setCriteriaInput("");
  }

  function removeCriterion(index: number) {
    setCriteriaList((prev) => prev.filter((_, i) => i !== index));
  }

  function handleCriteriaKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addCriterion();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const newErrors: { title?: string } = {};
    if (!title.trim()) newErrors.title = "Title is required";
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);

    try {
      const ticket = await createTicket({
        workspace_id: workspaceId,
        title: title.trim(),
        description: description.trim() || undefined,
        acceptance_criteria:
          criteriaMode === "manual" ? criteriaList : undefined,
      });
      router.push(`/tickets/${ticket.id}`);
    } catch (err) {
      setErrors({ title: err instanceof Error ? err.message : "Failed to create ticket" });
      setSubmitting(false);
    }
  }

  const showAutoExtractHint =
    criteriaMode === "manual" &&
    criteriaList.length === 0 &&
    description.trim().length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-text-muted hover:text-text-primary transition-colors text-sm"
        >
          ← Back
        </button>
        <h1 className="text-xl font-bold text-text-primary">New Ticket</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left: Create form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Title */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-text-primary" htmlFor="title">
              Title
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What needs to be built?"
              className="bg-surface border border-border-default rounded-lg px-4 py-3 text-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors"
            />
            {errors.title && (
              <p className="text-red-brand text-xs">{errors.title}</p>
            )}
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-text-primary" htmlFor="description">
              Description
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={"Describe the ticket in detail.\n\nYou can include checklists:\n- [ ] First step\n- [ ] Second step"}
              rows={7}
              className="bg-surface border border-border-default rounded-lg px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors resize-y font-mono"
            />
          </div>

          {/* Acceptance Criteria */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-text-primary">
                Acceptance Criteria
              </label>
              <div className="flex items-center gap-1 bg-surface border border-border-default rounded-lg p-0.5">
                <button
                  type="button"
                  onClick={() => setCriteriaMode("manual")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    criteriaMode === "manual"
                      ? "bg-green-brand text-white"
                      : "text-text-muted hover:text-text-primary"
                  }`}
                >
                  Manual
                </button>
                <button
                  type="button"
                  onClick={() => setCriteriaMode("auto")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    criteriaMode === "auto"
                      ? "bg-green-brand text-white"
                      : "text-text-muted hover:text-text-primary"
                  }`}
                >
                  Auto-extract
                </button>
              </div>
            </div>

            {criteriaMode === "auto" ? (
              <div className="flex items-center gap-2 px-4 py-3 bg-surface border border-green-brand/20 rounded-lg">
                <span className="text-green-brand text-sm">◈</span>
                <p className="text-sm text-text-muted">
                  Will extract criteria from description using AI
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={criteriaInput}
                    onChange={(e) => setCriteriaInput(e.target.value)}
                    onKeyDown={handleCriteriaKeyDown}
                    placeholder="Add a criterion and press Enter"
                    className="flex-1 bg-surface border border-border-default rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors"
                  />
                  <button
                    type="button"
                    onClick={addCriterion}
                    className="px-4 py-2 bg-surface-2 border border-border-default rounded-lg text-sm text-text-primary hover:border-green-brand transition-colors"
                  >
                    Add
                  </button>
                </div>

                {criteriaList.length > 0 && (
                  <ul className="flex flex-col gap-1">
                    {criteriaList.map((criterion, i) => (
                      <li
                        key={i}
                        className="flex items-center gap-2 px-3 py-2 bg-surface rounded-lg border border-border-default group"
                      >
                        <span className="w-4 h-4 rounded-full border border-border-default flex-shrink-0" />
                        <span className="flex-1 text-sm text-text-primary">{criterion}</span>
                        <button
                          type="button"
                          onClick={() => removeCriterion(i)}
                          className="text-text-muted hover:text-red-brand transition-colors text-xs opacity-0 group-hover:opacity-100"
                          aria-label="Remove criterion"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          {/* Source */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-text-primary">Source</label>
            <div className="flex gap-2 flex-wrap">
              {SOURCES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setSource(s.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                    source === s.value
                      ? "bg-green-brand/10 border-green-brand text-green-brand"
                      : "bg-surface border-border-default text-text-muted hover:text-text-primary hover:border-stone-400"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 px-6 py-3 bg-green-brand text-white font-semibold rounded-lg hover:bg-green-brand/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Creating…" : "Create Ticket"}
          </button>
        </form>

        {/* Right: Preview panel */}
        <Card className="flex flex-col gap-4 sticky top-6">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Preview</p>

          {title ? (
            <h2 className="text-xl font-bold text-text-primary leading-tight">{title}</h2>
          ) : (
            <div className="h-7 bg-surface-2 rounded w-3/4" />
          )}

          {description && (
            <p className="text-sm text-text-muted whitespace-pre-wrap leading-relaxed line-clamp-4">
              {description}
            </p>
          )}

          {criteriaMode === "auto" ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Acceptance Criteria
              </p>
              <p className="text-sm text-green-brand/70 italic">
                AI will extract criteria from your description
              </p>
            </div>
          ) : criteriaList.length > 0 ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Acceptance Criteria
              </p>
              <ul className="flex flex-col gap-1.5">
                {criteriaList.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                    <span className="mt-0.5 w-4 h-4 rounded-full border border-border-default flex-shrink-0" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          ) : showAutoExtractHint ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Acceptance Criteria
              </p>
              <p className="text-sm text-text-muted italic">
                AI will extract criteria from your description
              </p>
            </div>
          ) : null}

          {!title && !description && (
            <p className="text-sm text-text-muted italic">
              Start typing to see a preview
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
