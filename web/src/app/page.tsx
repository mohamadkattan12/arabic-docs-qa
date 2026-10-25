"use client";

import { useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ask, type Citation } from "@/lib/api";

type Turn = {
  question: string;
  text: string;
  status: "streaming" | "answered" | "not-found" | "refused" | "error";
  citations: Citation[];
  error?: string;
};

const EXAMPLES = [
  "كم يوم إجازة سنوية يستحق الموظف؟",
  "How many days can I work remotely per week?",
  "ما هو حد الفندق لليلة الواحدة خارج المملكة؟",
  "What is the notice period when resigning?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const busy = turns.at(-1)?.status === "streaming";

  function update(index: number, patch: Partial<Turn> | ((t: Turn) => Partial<Turn>)) {
    setTurns((all) =>
      all.map((t, i) => (i === index ? { ...t, ...(typeof patch === "function" ? patch(t) : patch) } : t)),
    );
  }

  async function submit(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    const index = turns.length;
    setTurns((all) => [...all, { question: text, text: "", status: "streaming", citations: [] }]);
    setQuestion("");
    try {
      const done = await ask(text, (delta) => update(index, (t) => ({ text: t.text + delta })));
      update(index, {
        text: done.text,
        citations: done.citations,
        status: done.answerable
          ? "answered"
          : done.refused || done.truncated
            ? "refused"
            : "not-found",
      });
    } catch (e) {
      update(index, { status: "error", error: e instanceof Error ? e.message : String(e) });
      setQuestion(text); // keep the question so the user can retry
    }
    inputRef.current?.focus();
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Ask the company policies</h1>
        <p className="text-muted-foreground">
          Ask in Arabic or English. Answers cite the document and section they come from.
        </p>
      </div>

      {turns.length === 0 ? (
        <section aria-label="Example questions" className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">Try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((q) => (
              <Button key={q} variant="outline" size="sm" dir="auto" onClick={() => submit(q)}>
                {q}
              </Button>
            ))}
          </div>
        </section>
      ) : (
        <ol aria-label="Conversation" className="flex flex-col gap-6">
          {turns.map((turn, i) => (
            <li key={i} className="flex flex-col gap-3">
              <p dir="auto" className="self-end rounded-lg bg-muted px-4 py-2 font-medium">
                {turn.question}
              </p>
              <Answer turn={turn} onRetry={() => submit(turn.question)} />
            </li>
          ))}
        </ol>
      )}

      <form
        className="sticky bottom-0 flex flex-col gap-2 border-t bg-background py-4"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <label htmlFor="question" className="text-sm font-medium">
          Your question
        </label>
        <Textarea
          id="question"
          ref={inputRef}
          dir="auto"
          rows={2}
          maxLength={1000}
          value={question}
          placeholder="e.g. كم يوم إجازة مرضية؟"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit(question);
            }
          }}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">Enter to send, Shift+Enter for a new line</span>
          <Button type="submit" disabled={busy || !question.trim()}>
            {busy ? "Answering…" : "Ask"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function Answer({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  const [open, setOpen] = useState<number | null>(null);

  if (turn.status === "error") {
    return (
      <div role="alert" className="rounded-lg border border-destructive/50 px-4 py-3">
        <p className="text-destructive">Couldn&apos;t get an answer: {turn.error}</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border px-4 py-3" aria-live="polite" aria-busy={turn.status === "streaming"}>
      {turn.text ? (
        <div>
          <Markdown>{turn.text}</Markdown>
        </div>
      ) : (
        turn.status === "streaming" && <p className="text-muted-foreground">Searching the documents…</p>
      )}
      {turn.status === "not-found" && <Badge variant="secondary">Not in the documents</Badge>}
      {turn.status === "refused" && <Badge variant="secondary">Couldn&apos;t answer</Badge>}
      {turn.citations.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Sources</p>
          <ul className="flex flex-wrap gap-2">
            {turn.citations.map((c, i) => (
              <li key={i}>
                <Button
                  variant="outline"
                  size="sm"
                  aria-expanded={open === i}
                  aria-controls={`quote-${i}`}
                  onClick={() => setOpen(open === i ? null : i)}
                >
                  <bdi>{c.document}</bdi>
                  <span aria-hidden="true">·</span>
                  <bdi>{c.location}</bdi>
                </Button>
              </li>
            ))}
          </ul>
          {open !== null && turn.citations[open] && (
            <blockquote
              id={`quote-${open}`}
              dir="auto"
              className="border-s-4 ps-3 text-sm text-muted-foreground"
            >
              <Markdown>{turn.citations[open].quote}</Markdown>
            </blockquote>
          )}
        </div>
      )}
    </div>
  );
}
