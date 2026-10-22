import React from "react";

interface FormattedMessageProps {
  content: string;
  className?: string;
}

// Clean and parse inline tokens: bold (**text**), italic (*text*), code (`text`), snake_case identifiers
function renderInline(text: string): React.ReactNode[] {
  // 1. Replace snake_case in quotes with clean spaced words
  let cleaned = text.replace(
    /["']([a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)+)["']/g,
    (_, inner) => `"${inner.replace(/_/g, " ")}"`
  );

  // 2. Tokenize by bold, italic, code
  // Regex matches: **bold**, *italic*, `code`
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const parts = cleaned.split(tokenRegex);

  return parts.map((part, idx) => {
    if (!part) return null;

    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      const inner = part.slice(2, -2).trim();
      return (
        <strong key={idx} className="font-semibold text-pine-950 dark:text-white">
          {inner}
        </strong>
      );
    }

    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      const inner = part.slice(1, -1).trim();
      return (
        <em key={idx} className="italic text-pine-900 dark:text-pine-200">
          {inner}
        </em>
      );
    }

    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      const inner = part.slice(1, -1).trim();
      return (
        <code
          key={idx}
          className="rounded bg-ivory-100 dark:bg-night-800 px-1.5 py-0.5 font-mono text-xs text-brand-900 dark:text-brand-300"
        >
          {inner}
        </code>
      );
    }

    // Clean any stray asterisks or pipes
    const textCleaned = part.replace(/\*\*/g, "").replace(/^\||\|$/g, "");
    return <React.Fragment key={idx}>{textCleaned}</React.Fragment>;
  });
}

export function FormattedMessage({ content, className = "" }: FormattedMessageProps) {
  if (!content) return null;

  // 1. Strip raw markdown tables (lines starting and ending with '|')
  const rawLines = content.split("\n");
  const filteredLines: string[] = [];

  for (const line of rawLines) {
    const s = line.trim();
    if (s.startsWith("|") && (s.endsWith("|") || s.includes("---"))) {
      continue; // Skip raw markdown table row
    }
    filteredLines.push(line);
  }

  const cleanContent = filteredLines.join("\n").replace(/\n{3,}/g, "\n\n").trim();

  // 2. Group into blocks (paragraphs, lists, headings)
  const rawBlocks = cleanContent.split(/\n\n+/);

  return (
    <div className={`space-y-3 leading-relaxed text-xs sm:text-sm text-pine-800 dark:text-pine-200 ${className}`}>
      {rawBlocks.map((block, blockIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);

        // Check if block is an unordered list (lines starting with -, *, or •)
        const isBulletList = lines.length > 0 && lines.every((l) => /^[-*•]\s+/.test(l));
        if (isBulletList) {
          return (
            <ul key={blockIdx} className="my-2 space-y-1.5 pl-4 list-disc text-pine-800 dark:text-pine-200">
              {lines.map((item, itemIdx) => {
                const itemText = item.replace(/^[-*•]\s+/, "");
                return (
                  <li key={itemIdx} className="leading-relaxed">
                    {renderInline(itemText)}
                  </li>
                );
              })}
            </ul>
          );
        }

        // Check if block is an ordered list (lines starting with 1., 2., etc.)
        const isNumberedList = lines.length > 0 && lines.every((l) => /^\d+\.\s+/.test(l));
        if (isNumberedList) {
          return (
            <ol key={blockIdx} className="my-2 space-y-1.5 pl-4 list-decimal text-pine-800 dark:text-pine-200">
              {lines.map((item, itemIdx) => {
                const itemText = item.replace(/^\d+\.\s+/, "");
                return (
                  <li key={itemIdx} className="leading-relaxed">
                    {renderInline(itemText)}
                  </li>
                );
              })}
            </ol>
          );
        }

        // Check if single line heading (e.g. ### Header or **Notes:** or Notes:)
        if (lines.length === 1) {
          const single = lines[0];
          const isHeading =
            single.startsWith("#") ||
            (/^(\*{0,2})(Notes|Summary|Key Observations|Findings|Related Healthcare Scheme)(\*{0,2}):?/i.test(single));

          if (isHeading) {
            const cleanHeading = single.replace(/^#+\s*/, "").replace(/^\*\*|\*\*$/g, "").trim();
            return (
              <h4
                key={blockIdx}
                className="font-bold text-xs sm:text-sm text-pine-950 dark:text-white mt-3 mb-1 flex items-center gap-1.5"
              >
                {renderInline(cleanHeading)}
              </h4>
            );
          }
        }

        // Mixed block or paragraph with potential embedded lists / headings
        return (
          <div key={blockIdx} className="space-y-1.5">
            {lines.map((line, lineIdx) => {
              if (/^[-*•]\s+/.test(line)) {
                return (
                  <div key={lineIdx} className="flex items-start gap-2 pl-3 my-1">
                    <span className="text-brand-700 dark:text-brand-400 font-bold select-none">•</span>
                    <div className="flex-1 leading-relaxed">{renderInline(line.replace(/^[-*•]\s+/, ""))}</div>
                  </div>
                );
              }

              if (/^\d+\.\s+/.test(line)) {
                const num = line.match(/^(\d+)\.\s+/)?.[1] ?? "•";
                return (
                  <div key={lineIdx} className="flex items-start gap-2 pl-3 my-1">
                    <span className="font-semibold text-brand-800 dark:text-brand-300 min-w-[1.2rem]">{num}.</span>
                    <div className="flex-1 leading-relaxed">{renderInline(line.replace(/^\d+\.\s+/, ""))}</div>
                  </div>
                );
              }

              if (/^(\*{0,2})(Notes|Summary|Key Observations|Findings)(\*{0,2}):/i.test(line)) {
                return (
                  <div key={lineIdx} className="font-semibold text-xs sm:text-sm text-pine-950 dark:text-white mt-2 mb-0.5">
                    {renderInline(line)}
                  </div>
                );
              }

              return (
                <p key={lineIdx} className="leading-relaxed">
                  {renderInline(line)}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
