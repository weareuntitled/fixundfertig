import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "./api";

const userSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  first_name: z.string().default(""),
  last_name: z.string().default(""),
  is_active: z.boolean().default(true),
  email_verified: z.boolean().default(false),
});

export type User = z.infer<typeof userSchema>;

const loginResponseSchema = z.object({
  user: userSchema,
  csrf_token: z.string(),
});

export type LoginResponse = z.infer<typeof loginResponseSchema>;

export function useAuth() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api.get<User>("/api/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: { email: string; password: string }) =>
      api.post<LoginResponse>("/api/auth/login", creds).then((data) => loginResponseSchema.parse(data)),
    onSuccess: (data) => {
      qc.setQueryData(["auth", "me"], data.user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/api/auth/logout"),
    onSuccess: () => {
      qc.setQueryData(["auth", "me"], null);
      qc.invalidateQueries();
    },
  });
}

export function isUnauthorizedError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}
