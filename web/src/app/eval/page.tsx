"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { latestEval, type ModelSummary } from "@/lib/api";

const COLUMNS: { key: keyof ModelSummary; label: string }[] = [
  { key: "answer_score", label: "Answer score" },
  { key: "citation_accuracy", label: "Citations" },
  { key: "refusal_accuracy", label: "Refuses when not in docs" },
  { key: "false_refusal_rate", label: "False refusals" },
  { key: "injection_resisted", label: "Injection resisted" },
  { key: "cost_per_100_usd", label: "Cost / 100 questions" },
  { key: "median_latency_s", label: "Median latency" },
];

function format(key: keyof ModelSummary | "pct", value: number | null): string {
  if (value === null) return "n/a";
  if (key === "cost_per_100_usd") return `$${value.toFixed(2)}`;
  if (key === "median_latency_s") return `${value.toFixed(1)} s`;
  return `${Math.round(value)}%`;
}

export default function EvalPage() {
  const { data: result, error, refetch } = useQuery({ queryKey: ["eval"], queryFn: latestEval });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Evaluation</h1>
        <p className="text-muted-foreground">
          The same Arabic and English test questions, answered by each model and scored.
        </p>
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-destructive/50 p-4">
          <p className="text-destructive">Couldn&apos;t load results: {error.message}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      ) : result === undefined ? (
        <p className="text-muted-foreground" aria-live="polite">
          Loading results…
        </p>
      ) : result === null ? (
        <div className="rounded-lg border p-4">
          <p>No evaluation has been run yet. Run it from the repo root (it calls the Claude API):</p>
          <pre className="mt-2 overflow-x-auto rounded bg-muted p-3 text-sm">
            docker compose run --rm eval --yes
          </pre>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Run {result.created_at} · {result.dataset_size} questions · judge {result.judge_model} · retrieval{" "}
            {result.retrieval_mode}
          </p>
          <section aria-labelledby="models-heading" className="flex flex-col gap-2">
            <h2 id="models-heading" className="text-lg font-semibold">
              Answer models
            </h2>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    {COLUMNS.map((c) => (
                      <TableHead key={c.key} className="text-end">
                        {c.label}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(result.models).map(([model, s]) => (
                    <TableRow key={model}>
                      <TableCell className="font-medium">
                        {model}
                        {model === result.recommended && (
                          <Badge className="ms-2">Recommended</Badge>
                        )}
                      </TableCell>
                      {COLUMNS.map((c) => (
                        <TableCell key={c.key} className="text-end tabular-nums">
                          {format(c.key, s[c.key])}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>
          <section aria-labelledby="retrieval-heading" className="flex flex-col gap-2">
            <h2 id="retrieval-heading" className="text-lg font-semibold">
              Retrieval: right section in the top 6
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Mode</TableHead>
                  <TableHead className="text-end">All</TableHead>
                  <TableHead className="text-end">Same language</TableHead>
                  <TableHead className="text-end">Cross-language</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(result.retrieval).map(([mode, r]) => (
                  <TableRow key={mode}>
                    <TableCell className="font-medium">{mode}</TableCell>
                    <TableCell className="text-end tabular-nums">{format("pct", r.hit_at_6)}</TableCell>
                    <TableCell className="text-end tabular-nums">{format("pct", r.same_language)}</TableCell>
                    <TableCell className="text-end tabular-nums">{format("pct", r.cross_language)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-sm text-muted-foreground">
              Arabic PDF extraction keeps {Math.round(result.pdf_word_recall * 100)}% of the source
              words intact.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
