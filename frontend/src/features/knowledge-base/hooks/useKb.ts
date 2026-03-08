import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";
import {
  getKbList,
  createKb,
  updateKb,
  deleteKb,
  getKbPermissions,
  setKbPermissions,
  type KbItem,
  type KbPermissionItem,
  type CreateKbPayload,
  type UpdateKbPayload,
  type DeleteKbPayload,
} from "../services";
import { queryKeys } from "../../../queryKeys";

export type { KbItem, KbPermissionItem, CreateKbPayload, UpdateKbPayload, DeleteKbPayload };

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

export function useKbTrainTextMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; title: string; content: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, title, content }: { uuid: string; title: string; content: string }) => {
      const res = await api.post(`/kb/${uuid}/train/text`, { title, content });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb }),
    ...options,
  });
}

export function useKbTrainFileMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; formData: FormData }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, formData }: { uuid: string; formData: FormData }) => {
      const res = await api.post(`/kb/${uuid}/train/file`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb }),
    ...options,
  });
}
