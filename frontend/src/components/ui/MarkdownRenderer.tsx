import React, { useState } from 'react';
import { Copy, Check, ExternalLink } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // Process code blocks first to isolate them from line-by-line parsing
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const parts: Array<{ type: 'code' | 'text'; lang?: string; code?: string; text?: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', text: content.slice(lastIndex, match.index) });
    }
    parts.push({
      type: 'code',
      lang: match[1] || 'text',
      code: match[2].trim()
    });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', text: content.slice(lastIndex) });
  }

  return (
    <div className={`space-y-3 text-xs leading-relaxed text-[var(--color-ink-2)] ${className}`}>
      {parts.map((part, pIdx) => {
        if (part.type === 'code' && part.code !== undefined) {
          return <CodeBlock key={pIdx} code={part.code} lang={part.lang || 'code'} />;
        }
        return <TextMarkdownBlock key={pIdx} text={part.text || ''} />;
      })}
    </div>
  );
};

const CodeBlock: React.FC<{ code: string; lang: string }> = ({ code, lang }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-2.5 rounded-[var(--radius-card)] bg-slate-950 border border-slate-800 overflow-hidden">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900/80 border-b border-slate-800 text-[11px] text-[var(--color-muted)] font-mono">
        <span className=" font-semibold text-[var(--color-muted)]">{lang}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center space-x-1 text-[var(--color-muted)] hover:text-[var(--color-ink)] transition focus-visible:ring-1 focus-visible:ring-emerald-500 rounded px-1 py-0.5"
          title="Copy code"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[11px] font-mono text-emerald-300/90 leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
};

const TextMarkdownBlock: React.FC<{ text: string }> = ({ text }) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Empty lines
    if (!trimmed) {
      i++;
      continue;
    }

    // Table detection: starts with | and next line has |---|
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length && lines[i + 1].trim().includes('|-')) {
      const headerRow = trimmed
        .slice(1, -1)
        .split('|')
        .map(c => c.trim());
      i += 2; // skip header and divider

      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        const rowCols = lines[i]
          .trim()
          .slice(1, -1)
          .split('|')
          .map(c => c.trim());
        rows.push(rowCols);
        i++;
      }

      elements.push(
        <div key={`table-${i}`} className="my-2.5 overflow-x-auto rounded-[var(--radius-card)] border border-slate-800">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-900/90 border-b border-slate-800 text-[var(--color-ink-2)] font-semibold">
              <tr>
                {headerRow.map((h, colIdx) => (
                  <th key={colIdx} className="px-3.5 py-2">
                    {renderInlineMarkdown(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
              {rows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-900/40 transition">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3.5 py-2 text-[var(--color-ink-2)]">
                      {renderInlineMarkdown(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Headings (styled typography within chat message blocks)
    if (trimmed.startsWith('### ')) {
      elements.push(
        <div key={`h3-${i}`} className="text-sm font-bold text-[var(--color-ink)] tracking-tight mt-3 mb-1">
          {renderInlineMarkdown(trimmed.slice(4))}
        </div>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <div key={`h2-${i}`} className="text-base font-bold text-[var(--color-ink)] tracking-tight mt-4 mb-1.5 border-b border-slate-800 pb-1">
          {renderInlineMarkdown(trimmed.slice(3))}
        </div>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <div key={`h1-${i}`} className="text-lg font-bold text-[var(--color-ink)] tracking-tight mt-4 mb-2">
          {renderInlineMarkdown(trimmed.slice(2))}
        </div>
      );
      i++;
      continue;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      elements.push(
        <blockquote key={`bq-${i}`} className="my-2 border-l-2 border-emerald-500/60 pl-3 py-1 bg-slate-900/40 rounded-r-lg text-[var(--color-ink-2)] italic text-xs">
          {renderInlineMarkdown(trimmed.slice(2))}
        </blockquote>
      );
      i++;
      continue;
    }

    // Unordered List
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const listItems: string[] = [];
      while (i < lines.length && (lines[i].trim().startsWith('- ') || lines[i].trim().startsWith('* '))) {
        listItems.push(lines[i].trim().slice(2));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="my-1.5 space-y-1 list-disc list-inside text-[var(--color-ink-2)]">
          {listItems.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {renderInlineMarkdown(item)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered List
    if (/^\d+\.\s/.test(trimmed)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^\d+\.\s/, ''));
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="my-1.5 space-y-1 list-decimal list-inside text-[var(--color-ink-2)]">
          {listItems.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {renderInlineMarkdown(item)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={`p-${i}`} className="leading-relaxed text-[var(--color-ink-2)]">
        {renderInlineMarkdown(trimmed)}
      </p>
    );
    i++;
  }

  return <>{elements}</>;
};

/**
 * Parses inline bold (**text**), italic (*text*), inline code (`code`), and links ([text](url))
 */
function renderInlineMarkdown(str: string): React.ReactNode {
  if (!str) return '';

  // Tokenize regex for inline code, links, bold, and italic
  const inlineRegex = /(`[^`]+`)|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)|(\*[^*]+\*)/g;
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = inlineRegex.exec(str)) !== null) {
    if (match.index > lastIdx) {
      parts.push(str.slice(lastIdx, match.index));
    }

    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      // Inline code
      parts.push(
        <code key={match.index} className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-emerald-300 font-mono text-[11px]">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('[') && token.includes('](') && token.endsWith(')')) {
      // Link
      const linkMatch = token.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (linkMatch) {
        parts.push(
          <a
            key={match.index}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 inline-flex items-center space-x-0.5"
          >
            <span>{linkMatch[1]}</span>
            <ExternalLink className="w-2.5 h-2.5 inline ml-0.5" aria-hidden="true" />
          </a>
        );
      }
    } else if (token.startsWith('**') && token.endsWith('**')) {
      // Bold
      parts.push(
        <strong key={match.index} className="font-semibold text-[var(--color-ink)]">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      // Italic
      parts.push(
        <em key={match.index} className="italic text-[var(--color-ink-2)]">
          {token.slice(1, -1)}
        </em>
      );
    }

    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < str.length) {
    parts.push(str.slice(lastIdx));
  }

  return parts;
}
