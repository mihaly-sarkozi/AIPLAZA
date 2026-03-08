import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import "./index.css";
import App from "./App.tsx";
import { queryClient } from "./api/queryClient";
import ErrorBoundary from "./components/ErrorBoundary";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toaster richColors position="top-center" closeButton />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>
);
