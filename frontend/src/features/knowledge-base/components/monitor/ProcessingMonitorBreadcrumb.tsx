import { Link } from "react-router-dom";

import { useTranslation } from "../../../../i18n";

type Crumb = {
  label: string;
  to?: string;
};

type ProcessingMonitorBreadcrumbProps = {
  crumbs: Crumb[];
};

export default function ProcessingMonitorBreadcrumb({ crumbs }: ProcessingMonitorBreadcrumbProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("kb.processingMonitor.breadcrumb")} className="mb-4 flex flex-wrap items-center gap-2 text-sm text-[var(--color-muted)]">
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1;
        return (
          <span key={`${crumb.label}-${index}`} className="inline-flex items-center gap-2">
            {index > 0 ? <span aria-hidden="true">/</span> : null}
            {crumb.to && !isLast ? (
              <Link to={crumb.to} className="font-medium text-[var(--color-primary)] hover:underline">
                {crumb.label}
              </Link>
            ) : (
              <span className={isLast ? "font-medium text-[var(--color-foreground)]" : undefined}>{crumb.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
