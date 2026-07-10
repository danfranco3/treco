"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/lib/workspace";
import { createTicket } from "@/lib/api";

export default function NewTicketPage() {
  const router = useRouter();
  const { workspaceId } = useWorkspace();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criteriaInput, setCriteriaInput] = useState("");
  const [criteriaList, setCriteriaList] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function addCriterion() {
    const trimmed = criteriaInput.trim();
    if (!trimmed) return;
    setCriteriaList((prev) => [...prev, trimmed]);
    setCriteriaInput("");
  }

  function handleCriteriaKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addCriterion();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("Title is required"); return; }
    setError("");
    setSubmitting(true);
    const finalCriteria = criteriaInput.trim()
      ? [...criteriaList, criteriaInput.trim()]
      : criteriaList;
    try {
      const ticket = await createTicket({
        workspace_id: workspaceId,
        title: title.trim(),
        description: description.trim() || undefined,
        acceptance_criteria: finalCriteria,
      });
      router.push(`/tickets/${ticket.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ticket");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto">
      <div>
        <button type="button" onClick={() => router.back()} className="text-text-muted hover:text-text-primary text-sm">
          ← Back
        </button>
      </div>

      <h1 className="text-xl font-bold text-text-primary">New Ticket</h1>

      <form id="new-ticket-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-text-primary" htmlFor="title">Title</label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What needs to be built?"
            className="bg-surface border border-border-default rounded-lg px-4 py-3 text-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors"
          />
          {error && <p className="text-red-brand text-xs">{error}</p>}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-text-primary" htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the ticket in detail."
            rows={5}
            className="bg-surface border border-border-default rounded-lg px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-green-brand transition-colors resize-y"
          />
          <div className="flex gap-2 mt-1">
            <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-surface-2 border border-border-default text-text-muted">
              open
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-text-primary">Acceptance Criteria</label>
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
              {criteriaList.map((c, i) => (
                <li key={i} className="flex items-center gap-2 px-3 py-2 bg-surface rounded-lg border border-border-default group">
                  <span className="w-4 h-4 rounded-full border border-border-default flex-shrink-0" />
                  <span className="flex-1 text-sm text-text-primary">{c}</span>
                  <button
                    type="button"
                    onClick={() => setCriteriaList((prev) => prev.filter((_, j) => j !== i))}
                    className="text-text-muted hover:text-red-brand text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Remove criterion"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 px-6 py-3 bg-green-brand text-white font-semibold rounded-lg hover:bg-green-brand/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Creating…" : "Create Ticket"}
        </button>
      </form>
    </div>
  );
}
