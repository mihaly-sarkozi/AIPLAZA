import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "template",
    routes: () => [],
    menuItems: () => [],
  };
}
