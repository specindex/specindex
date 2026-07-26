import type { ProjectNewsItem } from "@/lib/types";
import { formatDate } from "@/lib/format";

type Props = {
  news: ProjectNewsItem[];
};

export function ProjectNews({ news }: Props) {
  if (news.length === 0) return null;

  return (
    <div className="card p-4 md:p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        Related news
      </h2>
      <ul className="mt-3 space-y-3">
        {news.map((n) => (
          <li key={n.url}>
            <a
              href={n.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium text-[var(--color-ink)] hover:text-[var(--color-green)] hover:underline"
            >
              {n.title}
            </a>
            <p className="mt-0.5 text-xs text-[var(--color-gray-600)]">
              {n.source_name}
              {n.published_at ? ` · ${formatDate(n.published_at.slice(0, 10))}` : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
