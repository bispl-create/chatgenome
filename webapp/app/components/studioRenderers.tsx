"use client";

import { buildCustomStudioRendererRegistry } from "./customStudioRenderers";
import { buildGenericStudioRendererRegistry } from "./genericStudioRenderers";
import { type StudioRendererBuilderArgs, type StudioRendererRegistry } from "./studioRendererTypes";

export type { StudioRendererBuilderArgs, StudioRendererRegistry } from "./studioRendererTypes";

export function buildStudioRendererRegistry(args: StudioRendererBuilderArgs): StudioRendererRegistry {
  return {
    ...buildGenericStudioRendererRegistry(args),
    ...buildCustomStudioRendererRegistry(args),
  };
}
