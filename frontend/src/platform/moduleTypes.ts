import type { ComponentType } from "react";

export type FrontendRole = "user" | "admin" | "owner" | (string & {});

export interface FrontendUser {
  id: number;
  email: string;
  role: FrontendRole;
  name?: string | null;
  preferred_locale?: string | null;
  preferred_theme?: string | null;
  locale?: string;
  theme?: string;
}

export type ModuleLayoutSlot = "public" | "main";

export interface ModuleRouteDefinition {
  key: string;
  path: string;
  layout?: ModuleLayoutSlot;
  requiresAuth?: boolean;
  requiredPermission?: string;
  loader?: () => Promise<{ default: ComponentType }>;
  redirectTo?: string;
  redirectState?: unknown;
}

export interface ModuleMenuDefinition {
  key: string;
  path: string;
  labelKey: string;
  requiresAuth?: boolean;
  requiredPermission?: string;
  /** Kisebb szám = felül a hamburger menüben. */
  order?: number;
}

export interface FrontendModuleDefinition {
  key: string;
  routes(): ModuleRouteDefinition[];
  menuItems(): ModuleMenuDefinition[];
  preload?(context: { user: FrontendUser | null }): void;
}
