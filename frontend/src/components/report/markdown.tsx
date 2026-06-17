import type { Components } from "react-markdown"

/** Shared markdown renderer for analysis section bodies (report + counselor view). */
export const reportMarkdown: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-4 marker:text-orange">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-4 marker:text-orange">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-navy">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-orange-dark underline underline-offset-2">
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 rounded-md border-l-[3px] border-orange bg-peach-soft/60 px-3.5 py-2.5 text-navy [&_p]:mb-0">
      {children}
    </blockquote>
  ),
  h3: ({ children }) => <h3 className="mb-1.5 mt-4 font-display font-bold text-navy">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1 mt-3 font-display font-semibold text-navy">{children}</h4>,
}
