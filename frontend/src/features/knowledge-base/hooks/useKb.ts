import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";

export type KbItem = { uuid: string; name: string; description?: string; [key: string]: unknown };

export function useKbList(options?: Omit<UseQueryOptions<KbItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: ["kb"],
    queryFn: async () => {
      const res = await api.get("/kb");
      return res.data as KbItem[];
    },
    ...options,
  });
}

export function useCreateKbMutation(
  options?: UseMutationOptions<KbItem, Error, { name: string; description?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const res = await api.post("/kb", body);
      return res.data as KbItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
    ...options,
  });
}

export function useUpdateKbMutation(
  options?: UseMutationOptions<KbItem, Error, { uuid: string; name: string; description?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, name, description }: { uuid: string; name: string; description?: string }) => {
      const res = await api.put(`/kb/${uuid}`, { name, description });
      return res.data as KbItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
    ...options,
  });
}

export function useDeleteKbMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; confirm_name: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, confirm_name }: { uuid: string; confirm_name: string }) => {
      const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
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
    onSuccess: (_, { uuid }) =>
      queryClient.invalidateQueries({ queryKey: ["kb", uuid] }),
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
    onSuccess: (_, { uuid }) =>
      queryClient.invalidateQueries({ queryKey: ["kb", uuid] }),
    ...options,
  });
}
