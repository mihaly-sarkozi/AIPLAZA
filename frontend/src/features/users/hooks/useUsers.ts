import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resendInvite,
  patchMe,
  changePassword,
  type UserListItem,
  type UpdateUserPayload,
} from "../../../api/services/userService";
import { queryKeys } from "../../../queryKeys";

export type { UserListItem, UpdateUserPayload };

export function useUsers(options?: Omit<UseQueryOptions<UserListItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: getUsers,
    ...options,
  });
}

export function useCreateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, { email: string; name?: string; role: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useUpdateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, UpdateUserPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useDeleteUserMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useResendInviteMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resendInvite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function usePatchMeMutation(
  options?: UseMutationOptions<
    { name?: string; preferred_locale?: string; preferred_theme?: string },
    Error,
    { name?: string; preferred_locale?: string; preferred_theme?: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchMe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
    },
    ...options,
  });
}

export function useChangePasswordMutation(
  options?: UseMutationOptions<unknown, Error, { current_password: string; new_password: string }>
) {
  return useMutation({
    mutationFn: changePassword,
    ...options,
  });
}
