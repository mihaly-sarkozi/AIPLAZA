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
  getKbTrainingLog,
  deleteKbTrainingPoint,
  type KbItem,
  type KbPermissionItem,
  type KbTrainingLogEntry,
  type CreateKbPayload,
  type UpdateKbPayload,
  type DeleteKbPayload,
  type PersonalDataMode,
  type PersonalDataSensitivity,
} from "../services";
import { queryKeys } from "../../../queryKeys";

export type { KbItem, KbPermissionItem, KbTrainingLogEntry, CreateKbPayload, UpdateKbPayload, DeleteKbPayload, PersonalDataMode, PersonalDataSensitivity };

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

export function useKbTrainingLog(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<KbTrainingLogEntry[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kb, kbUuid ?? "", "train", "log"],
    queryFn: () => getKbTrainingLog(kbUuid!),
    enabled: !!kbUuid,
    ...options,
  });
}

function invalidateKbTrainLog(queryClient: ReturnType<typeof useQueryClient>, uuid: string) {
  queryClient.invalidateQueries({ queryKey: [...queryKeys.kb, uuid, "train", "log"] });
  queryClient.invalidateQueries({ queryKey: queryKeys.kb });
}

export function useKbTrainTextMutation(
  options?: UseMutationOptions<
    unknown,
    Error,
    { uuid: string; title: string; content: string; confirm_pii?: boolean }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      uuid,
      title,
      content,
      confirm_pii = false,
    }: {
      uuid: string;
      title: string;
      content: string;
      confirm_pii?: boolean;
    }) => {
      const res = await api.post(`/kb/${uuid}/train/text`, {
        title,
        content,
        confirm_pii,
      });
      return res.data;
    },
    onSuccess: (_, { uuid }) => invalidateKbTrainLog(queryClient, uuid),
    ...options,
  });
}

export function useKbTrainFileMutation(
  options?: UseMutationOptions<
    unknown,
    Error,
    { uuid: string; formData: FormData; confirm_pii?: boolean }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      uuid,
      formData,
      confirm_pii = false,
    }: {
      uuid: string;
      formData: FormData;
      confirm_pii?: boolean;
    }) => {
      if (confirm_pii) formData.append("confirm_pii", "true");
      const res = await api.post(`/kb/${uuid}/train/file`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (_, { uuid }) => invalidateKbTrainLog(queryClient, uuid),
    ...options,
  });
}

export function useDeleteKbTrainingPointMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; pointId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ uuid, pointId }) => deleteKbTrainingPoint(uuid, pointId),
    onSuccess: (_, { uuid }) => invalidateKbTrainLog(queryClient, uuid),
    ...options,
  });
}
