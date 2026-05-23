import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type InfiniteData,
  type UseInfiniteQueryOptions,
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
  getIngestRun,
  getKbPermissions,
  listIngestRuns,
  reprocessIngestItem,
  setKbPermissions,
  type IngestRun,
  type IngestRunListResponse,
  type KbItem,
  type KbPermissionItem,
  type CreateKbPayload,
  type UpdateKbPayload,
  type DeleteKbPayload,
  type PersonalDataMode,
} from "../services";
import { queryKeys } from "../../../queryKeys";

export type {
  IngestRun,
  IngestRunListResponse,
  KbItem,
  KbPermissionItem,
  CreateKbPayload,
  UpdateKbPayload,
  DeleteKbPayload,
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kb });
      queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
    ...options,
  });
}

export function useUpdateKbMutation(
  options?: UseMutationOptions<KbItem, Error, UpdateKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateKb,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kb });
      queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
    ...options,
  });
}

export function useDeleteKbMutation(
  options?: UseMutationOptions<unknown, Error, DeleteKbPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteKb,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.kb });
      queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
    ...options,
  });
}

export function useIngestRuns(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<IngestRunListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.kbIngestRuns(kbUuid ?? ""),
    queryFn: () => listIngestRuns(kbUuid!),
    enabled: !!kbUuid,
    ...options,
  });
}

export function useInfiniteIngestRuns(
  kbUuid: string | undefined,
  options?: Omit<
    UseInfiniteQueryOptions<
      IngestRunListResponse,
      Error,
      InfiniteData<IngestRunListResponse, number>,
      readonly unknown[],
      number
    >,
    "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
  >
) {
  return useInfiniteQuery<IngestRunListResponse, Error, InfiniteData<IngestRunListResponse, number>, readonly unknown[], number>({
    queryKey: [...queryKeys.kbIngestRuns(kbUuid ?? ""), "infinite"],
    queryFn: ({ pageParam }) => listIngestRuns(kbUuid!, { limit: 10, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.offset + lastPage.limit : undefined),
    enabled: !!kbUuid,
    ...options,
  });
}

function insertIngestRunIntoInfiniteCache(
  previous: InfiniteData<IngestRunListResponse, number> | undefined,
  run: IngestRun
): InfiniteData<IngestRunListResponse, number> | undefined {
  if (!previous || previous.pages.length === 0) return previous;
  if (previous.pages.some((page) => page.items.some((item) => item.id === run.id))) return previous;
  const [firstPage, ...restPages] = previous.pages;
  const nextFirstPage: IngestRunListResponse = {
    ...firstPage,
    items: [run, ...firstPage.items],
    total_count: firstPage.total_count + 1,
    summary: {
      ...firstPage.summary,
      total_run_count: Number(firstPage.summary?.total_run_count ?? firstPage.total_count) + 1,
    },
  };
  return {
    ...previous,
    pages: [nextFirstPage, ...restPages],
  };
}

function useStoreCreatedIngestRun() {
  const queryClient = useQueryClient();
  return (run: IngestRun) => {
    queryClient.setQueryData(queryKeys.kbIngestRun(run.id), run);
    queryClient.setQueryData<InfiniteData<IngestRunListResponse, number>>(
      [...queryKeys.kbIngestRuns(run.corpus_uuid), "infinite"],
      (previous) => insertIngestRunIntoInfiniteCache(previous, run)
    );
    queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(run.corpus_uuid) });
  };
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
  const storeCreatedRun = useStoreCreatedIngestRun();
  const { onSuccess, ...mutationOptions } = options ?? {};
  return useMutation({
    mutationFn: ({ kbUuid, title, text }) => createTextIngestRun(kbUuid, { title, text }),
    onSuccess: (run, variables, onMutateResult, context) => {
      storeCreatedRun(run);
      onSuccess?.(run, variables, onMutateResult, context);
    },
    ...mutationOptions,
  });
}

export function useCreateFileIngestMutation(
  options?: UseMutationOptions<IngestRun, Error, { kbUuid: string; files: File[]; characterCounts?: number[] }>
) {
  const storeCreatedRun = useStoreCreatedIngestRun();
  const { onSuccess, ...mutationOptions } = options ?? {};
  return useMutation({
    mutationFn: ({ kbUuid, files, characterCounts }) => createFileIngestRun(kbUuid, files, characterCounts),
    onSuccess: (run, variables, onMutateResult, context) => {
      storeCreatedRun(run);
      onSuccess?.(run, variables, onMutateResult, context);
    },
    ...mutationOptions,
  });
}

export function useCreateUrlIngestMutation(
  options?: UseMutationOptions<
    IngestRun,
    Error,
    { kbUuid: string; items: Array<{ url: string; title?: string }> }
  >
) {
  const storeCreatedRun = useStoreCreatedIngestRun();
  const { onSuccess, ...mutationOptions } = options ?? {};
  return useMutation({
    mutationFn: ({ kbUuid, items }) => createUrlIngestRun(kbUuid, items),
    onSuccess: (run, variables, onMutateResult, context) => {
      storeCreatedRun(run);
      onSuccess?.(run, variables, onMutateResult, context);
    },
    ...mutationOptions,
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
