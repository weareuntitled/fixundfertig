import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "./api";

const customerSchema = z.object({
  id: z.number().int(),
  name: z.string().default(""),
  vorname: z.string().default(""),
  nachname: z.string().default(""),
  email: z.string().default(""),
  strasse: z.string().default(""),
  plz: z.string().default(""),
  ort: z.string().default(""),
  country: z.string().default(""),
  vat_id: z.string().default(""),
  recipient_name: z.string().default(""),
  recipient_street: z.string().default(""),
  recipient_postal_code: z.string().default(""),
  recipient_city: z.string().default(""),
  offen_eur: z.number().default(0),
  archived: z.boolean().default(false),
});

export type Customer = z.infer<typeof customerSchema>;

const customerListSchema = z.array(customerSchema);

export function useCustomers() {
  return useQuery({
    queryKey: ["customers"],
    queryFn: () =>
      api
        .get<unknown>("/api/customers")
        .then((data) => customerListSchema.parse(data)),
  });
}

export function useCustomer(id: number) {
  return useQuery({
    queryKey: ["customers", id],
    queryFn: () =>
      api
        .get<unknown>(`/api/customers/${id}`)
        .then((data) => customerSchema.parse(data)),
    enabled: id > 0,
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api
        .post<unknown>("/api/customers", data)
        .then((res) => customerSchema.parse(res)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      api
        .put<unknown>(`/api/customers/${id}`, data)
        .then((res) => customerSchema.parse(res)),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["customers", vars.id] });
    },
  });
}

export function useDeleteCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/customers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}
