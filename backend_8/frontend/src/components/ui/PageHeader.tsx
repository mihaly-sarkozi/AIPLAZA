import type { ReactNode } from "react";
import { cn } from "../../utils/cn";

interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export default function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("app-page-header", className)}>
      <div>
        {eyebrow ? <p className="app-page-eyebrow">{eyebrow}</p> : null}
        <h1 className="app-page-title">{title}</h1>
        {description ? <p className="app-page-intro">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
    </div>
  );
}
