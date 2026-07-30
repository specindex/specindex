"use client";

import { useState } from "react";

// Small, scoped Q&A panel -- deliberately not a big Claude-style chat
// window (a mockup/Gemini-review iteration earlier this session concluded
// an always-on primary chat surface doesn't fit a dataset-lookup product).
// Single question in, single answer out, one exchange at a time. Reused by
// ProjectDetailView (grounded in one project) and SignedInHome (grounded in
// the signed-in user's territory).
export function AskPanel({
  title,
  placeholder,
  onAsk,
}: {
  title: string;
  placeholder: string;
  onAsk: (question: string) => Promise<string>;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await onAsk(question.trim());
      setAnswer(result);
    } catch {
      setError("Couldn't get an answer right now -- try again in a moment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--color-green)]/25 bg-[var(--color-green-light)]/40 p-4">
      <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--color-green)]">
        ✦ {title}
      </p>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="shrink-0 rounded-lg bg-[var(--color-green)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      {answer && !error && (
        <p className="mt-3 text-sm leading-relaxed text-[var(--color-gray-700)]">{answer}</p>
      )}
    </div>
  );
}
