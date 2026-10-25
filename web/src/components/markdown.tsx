import ReactMarkdown from "react-markdown";

/** Renders model answers and quoted sources. Raw HTML in the text is not rendered. */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p dir="auto" className="leading-7 [&:not(:first-child)]:mt-3">{children}</p>,
        ul: ({ children }) => <ul className="mt-2 list-disc ps-6">{children}</ul>,
        ol: ({ children }) => <ol className="mt-2 list-decimal ps-6">{children}</ol>,
        li: ({ children }) => <li dir="auto">{children}</li>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
