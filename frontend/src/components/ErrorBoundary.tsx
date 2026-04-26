import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches React render errors in the tree and shows a fallback.
 * Use at app root and optionally around route segments.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    const { children, fallback } = this.props;

    if (error) {
      if (typeof fallback === "function") {
        return fallback(error, this.reset);
      }
      if (fallback) {
        return fallback;
      }
      return (
        <div
          className="min-h-[40vh] flex flex-col items-center justify-center p-6 bg-[var(--color-background)] text-[var(--color-foreground)]"
          role="alert"
        >
          <h2 className="text-xl font-semibold mb-2">Valami hiba történt</h2>
          <p className="text-sm text-[var(--color-muted)] mb-4 max-w-md text-center">
            {error.message}
          </p>
          <button
            type="button"
            onClick={this.reset}
            className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
          >
            Újrapróbálás
          </button>
        </div>
      );
    }

    return children;
  }
}
