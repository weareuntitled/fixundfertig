import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export interface PasswordChangeInput {
  current_password: string;
  new_password: string;
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PasswordChangeInput) =>
      api.post<void>("/api/auth/password", input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}
