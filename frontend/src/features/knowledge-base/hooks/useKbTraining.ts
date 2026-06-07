import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { queryKeys } from "../../../queryKeys";
import type { SubmitTextTrainingResult } from "../../../api/services/kb/kbTrainingApi";
import { getTrainingBatch, submitTextTraining } from "../services";
import type { IngestRun } from "../services";

export function useTrainingBatch(
  batchId: string | undefined,
  options?: Omit<UseQueryOptions<IngestRun>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.kbTrainingBatch(batchId ?? ""),
    queryFn: () => getTrainingBatch(batchId!),
    enabled: !!batchId,
    ...options,
  });
}

export function useSubmitTextTrainingMutation(
  options?: UseMutationOptions<
    SubmitTextTrainingResult,
    Error,
    { kbUuid: string; content: string; title?: string | null }
  >
) {
  const queryClient = useQueryClient();
  const { onSuccess, ...mutationOptions } = options ?? {};
  return useMutation({
    mutationFn: ({ kbUuid, content, title }) =>
      submitTextTraining(kbUuid, { content, ...(title != null ? { title } : {}) }),
    onSuccess: (result, variables, onMutateResult, context) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.kbTrainingBatch(result.batchId) });
      onSuccess?.(result, variables, onMutateResult, context);
    },
    ...mutationOptions,
  });
}
