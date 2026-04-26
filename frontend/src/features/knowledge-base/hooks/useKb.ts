import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import {
  getKbList,
  createKb,
  createFileIngestRun,
  createTextIngestRun,
  createUrlIngestRun,
  updateKb,
  deleteKb,
  clearKb,
  getIngestRun,
  getKbPermissions,
  listIngestRuns,
  reprocessIngestItem,
  setKbPermissions,
  type IngestRun,
  type KbItem,
  type KbPermissionItem,
  type CreateKbPayload,
  type UpdateKbPayload,
  type DeleteKbPayload,
  type ClearKbPayload,
  type PersonalDataMode,
} from "../services";
import { queryKeys } from "../../../queryKeys";

export type {
  IngestRun,
  KbItem,
  KbPermissionItem,
  CreateKbPayload,
  UpdateKbPayload,
  DeleteKbPayload,
  ClearKbPayload,
  PersonalDataMode,
};

export function useKbPermissions(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<KbPermissionItem[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kb, kbUuid ?? "", "permissions"],
    queryFn: () => getKbPermissions(kbUuid!),
    enabled: !!kbUuid,
    ...options,
  });
}

export function useSetKbPermissionsMutation(
  options?: UseMutationOptions<
    unknown,
    Error,
    { uuid: string; permissions: Array<{ user_id: number; permission: string }> }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ uuid, permissions }) => setKbPermissions(uuid, permissions),
    onSuccess: (_, { uuid }) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.kb, uuid, "permissions"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.kb });
    },
    ...options,
  });
}

export function useKbList(options?: Omit<UseQueryOptions<KbItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: queryKeys.kb,
    queryFn: getKbList,
    ...options,
  });
}

export function useCreateKbMutation(
  options?: UseMutationOptions<KbItem, Error, CreateKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createKb,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb }),
    ...options,
  });
}

export function useUpdateKbMutation(
  options?: UseMutationOptions<KbItem, Error, UpdateKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateKb,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb }),
    ...options,
  });
}

export function useDeleteKbMutation(
  options?: UseMutationOptions<unknown, Error, DeleteKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteKb,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb }),
    ...options,
  });
}

export function useClearKbMutation(
  options?: UseMutationOptions<unknown, Error, ClearKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: clearKb,
    onSuccess: async (_, { uuid }) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.kb });
      await queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(uuid) });
    },
    ...options,
  });
}

export function useIngestRuns(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<IngestRun[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.kbIngestRuns(kbUuid ?? ""),
    queryFn: () => listIngestRuns(kbUuid!),
    enabled: !!kbUuid,
    ...options,
  });
}

export function useIngestRun(
  runId: string | undefined,
  options?: Omit<UseQueryOptions<IngestRun>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.kbIngestRun(runId ?? ""),
    queryFn: () => getIngestRun(runId!),
    enabled: !!runId,
    ...options,
  });
}

export function useCreateTextIngestMutation(
  options?: UseMutationOptions<IngestRun, Error, { kbUuid: string; title: string; text: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kbUuid, title, text }) => createTextIngestRun(kbUuid, { title, text }),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(run.corpus_uuid) });
      queryClient.setQueryData(queryKeys.kbIngestRun(run.id), run);
    },
    ...options,
  });
}

export function useCreateFileIngestMutation(
  options?: UseMutationOptions<IngestRun, Error, { kbUuid: string; files: File[] }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kbUuid, files }) => createFileIngestRun(kbUuid, files),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(run.corpus_uuid) });
      queryClient.setQueryData(queryKeys.kbIngestRun(run.id), run);
    },
    ...options,
  });
}

export function useCreateUrlIngestMutation(
  options?: UseMutationOptions<
    IngestRun,
    Error,
    { kbUuid: string; items: Array<{ url: string; title?: string }> }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kbUuid, items }) => createUrlIngestRun(kbUuid, items),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(run.corpus_uuid) });
      queryClient.setQueryData(queryKeys.kbIngestRun(run.id), run);
    },
    ...options,
  });
}

export function useReprocessIngestItemMutation(
  options?: UseMutationOptions<IngestRun, Error, { itemId: string; kbUuid: string }>
) {
  const queryClient = useQueryClient();
  const { onSuccess, ...restOptions } = options ?? {};
  return useMutation({
    ...restOptions,
    mutationFn: ({ itemId }) => reprocessIngestItem(itemId),
    onSuccess: async (run, variables, context, mutation) => {
      const { kbUuid } = variables;
      await queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(kbUuid) });
      queryClient.setQueryData(queryKeys.kbIngestRun(run.id), run);
      await onSuccess?.(run, variables, context, mutation);
    },
  });
}
