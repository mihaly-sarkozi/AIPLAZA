import type { ReactNode } from "react";
import { cn } from "../../utils/cn";

interface ModalProps {
  open: boolean;
  onClose?: () => void;
  children: ReactNode;
  className?: string;
  panelClassName?: string;
  closeOnOverlay?: boolean;
}

interface ModalHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
}

interface ModalFooterProps {
  children: ReactNode;
  className?: string;
}

export default function Modal({
  open,
  onClose,
  children,
  className,
  panelClassName,
  closeOnOverlay = false,
}: ModalProps) {
  if (!open) return null;

  return (
    <div
      className={cn("modal-overlay", className)}
      onClick={closeOnOverlay && onClose ? onClose : undefined}
      role="presentation"
    >
      <div
        className={cn("modal-card max-h-[90vh] overflow-y-auto p-6 md:p-7", panelClassName)}
        onClick={closeOnOverlay && onClose ? (e) => e.stopPropagation() : undefined}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
}

export function ModalHeader({ eyebrow, title, description }: ModalHeaderProps) {
  return (
    <div className="mb-5">
      {eyebrow ? <p className="app-page-eyebrow">{eyebrow}</p> : null}
      <h2 className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">{title}</h2>
      {description ? <p className="mt-2 text-sm leading-6 text-[var(--color-muted)]">{description}</p> : null}
    </div>
  );
}

export function ModalFooter({ children, className }: ModalFooterProps) {
  return <div className={cn("mt-6 flex justify-end gap-2", className)}>{children}</div>;
}
