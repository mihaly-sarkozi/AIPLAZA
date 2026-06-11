import { getModule as getBillingModule } from "@apps/billing/web/module";
import { getModule as getChatModule } from "@apps/chat/web/module";
import { getModule as getDemoModule } from "@apps/demo/web/module";
import { getModule as getKbModule } from "@apps/kb/web/module";
import { getModule as getLandingModule } from "@apps/landing/web/module";
import { getModule as getPackagesModule } from "@apps/packages/web/module";
import { getModule as getProfileModule } from "@apps/profile/web/module";
import { getModule as getSettingsModule } from "@apps/settings/web/module";
import { getModule as getTrafficModule } from "@apps/traffic/web/module";
import { getModule as getAuthModule } from "./modules/authModule";
import { getModule as getPlatformAdminModule } from "./modules/platformAdminModule";
import { getModule as getUsersModule } from "./modules/usersModule";

import type { FrontendModuleDefinition, FrontendUser, ModuleMenuDefinition, ModuleRouteDefinition } from "./moduleTypes";

const modules: FrontendModuleDefinition[] = [
  getLandingModule(),
  getDemoModule(),
  getAuthModule(),
  getPlatformAdminModule(),
  getChatModule(),
  getProfileModule(),
  getUsersModule(),
  getTrafficModule(),
  getBillingModule(),
  getPackagesModule(),
  getSettingsModule(),
  getKbModule(),
];

export function getFrontendModules(): FrontendModuleDefinition[] {
  return modules;
}

export function getModuleRoutes(layout?: ModuleRouteDefinition["layout"]): ModuleRouteDefinition[] {
  const routes = modules.flatMap((module) => module.routes());
  if (layout == null) return routes;
  return routes.filter((route) => (route.layout ?? "public") === layout);
}

export function getModuleMenuDefinitions(): ModuleMenuDefinition[] {
  return modules
    .flatMap((module) => module.menuItems())
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999));
}

export function preloadFrontendModules(user: FrontendUser | null): void {
  for (const module of modules) {
    module.preload?.({ user });
  }
}

export function getAuthenticatedFallbackPath(): string {
  return getModuleMenuDefinitions()[0]?.path ?? "/chat";
}
