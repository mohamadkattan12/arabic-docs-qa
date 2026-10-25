"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deleteDocument, listDocuments, uploadDocument, type DocumentRow } from "@/lib/api";

type Status = { kind: "idle" | "working" | "success" | "error"; message?: string };
const dateFormat = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const { data: docs, error: loadError, refetch } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [confirming, setConfirming] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onError = (err: Error) => setStatus({ kind: "error", message: err.message });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["documents"] });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onMutate: (file) => setStatus({ kind: "working", message: `Uploading ${file.name}…` }),
    onSuccess: (result) => {
      setStatus({
        kind: "success",
        message: result.created ? `Added ${result.name}.` : `${result.name} is already in the library.`,
      });
      if (fileRef.current) fileRef.current.value = "";
      return refresh();
    },
    onError,
  });

  const deleteMutation = useMutation({
    mutationFn: (doc: DocumentRow) => deleteDocument(doc.id),
    onMutate: (doc) => {
      setConfirming(null);
      setStatus({ kind: "working", message: `Deleting ${doc.name}…` });
    },
    onSuccess: (_, doc) => {
      setStatus({ kind: "success", message: `Deleted ${doc.name}.` });
      return refresh();
    },
    onError,
  });

  function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setStatus({ kind: "error", message: "Choose a .pdf, .md or .txt file first." });
      fileRef.current?.focus();
      return;
    }
    uploadMutation.mutate(file);
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="text-muted-foreground">
          The assistant answers only from these documents. Markdown and text work best for Arabic;
          Arabic PDFs can lose letters during text extraction.
        </p>
      </div>

      <form onSubmit={upload} className="flex flex-col gap-2 rounded-lg border p-4">
        <label htmlFor="file" className="text-sm font-medium">
          Add a document (.pdf, .md or .txt, up to 10 MB)
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input id="file" ref={fileRef} type="file" accept=".pdf,.md,.txt" className="min-w-0" />
          <Button type="submit" disabled={status.kind === "working"}>
            {status.kind === "working" ? "Uploading…" : "Upload"}
          </Button>
        </div>
        <p
          aria-live="polite"
          className={status.kind === "error" ? "text-sm text-destructive" : "text-sm text-muted-foreground"}
        >
          {status.message}
        </p>
      </form>

      {loadError ? (
        <div role="alert" className="rounded-lg border border-destructive/50 p-4">
          <p className="text-destructive">Couldn&apos;t load documents: {loadError.message}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      ) : docs === undefined ? (
        <p className="text-muted-foreground" aria-live="polite">
          Loading documents…
        </p>
      ) : docs.length === 0 ? (
        <p className="rounded-lg border p-4 text-muted-foreground">
          No documents yet. Upload one above, or restart the API to load the demo policies.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Language</TableHead>
              <TableHead className="text-end">Sections</TableHead>
              <TableHead>Added</TableHead>
              <TableHead>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {docs.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="max-w-48 truncate font-medium">
                  <bdi title={doc.name}>{doc.name}</bdi>
                </TableCell>
                <TableCell>{doc.lang === "ar" ? "Arabic" : "English"}</TableCell>
                <TableCell className="text-end tabular-nums">{doc.chunks}</TableCell>
                <TableCell>{dateFormat.format(new Date(doc.created_at))}</TableCell>
                <TableCell className="text-end">
                  {confirming === doc.id ? (
                    <span className="inline-flex gap-1">
                      <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate(doc)}>
                        Confirm delete
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                        Cancel
                      </Button>
                    </span>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Delete ${doc.name}`}
                      onClick={() => setConfirming(doc.id)}
                    >
                      Delete
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
