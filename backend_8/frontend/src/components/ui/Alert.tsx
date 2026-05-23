import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "../../utils/cn";

type AlertTone = "error" | "warning" | "success" | "info";

interface AlertProps extends ComponentPropsWithoutRef<"div"> {
  tone?: AlertTone;
  children: ReactNode;
}

const toneClasses: Record<AlertTone, string> = {
  error: "alert-base alert-error",
  warning: "alert-base alert-warning",
  success: "alert-base alert-success",
  info: "alert-base alert-info",
};

export default function Alert({ tone = "info", className, children, ...props }: AlertProps) {
  return (
    <div className={cn(toneClasses[tone], className)} {...props}>
      {children}
    </div>
  );
}
