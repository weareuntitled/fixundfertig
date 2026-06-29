import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

const companySchema = z.object({
  id: z.number(),
  name: z.string(),
  first_name: z.string().default(""),
  last_name: z.string().default(""),
  business_type: z.string().default(""),
  is_small_business: z.boolean().default(false),
  street: z.string().default(""),
  postal_code: z.string().default(""),
  city: z.string().default(""),
  country: z.string().default("Deutschland"),
  email: z.string().default(""),
  phone: z.string().default(""),
  iban: z.string().default(""),
  bic: z.string().default(""),
  bank_name: z.string().default(""),
  tax_id: z.string().default(""),
  vat_id: z.string().default(""),
  smtp_server: z.string().default(""),
  smtp_port: z.number().default(587),
  smtp_user: z.string().default(""),
  smtp_password: z.string().default(""),
  default_sender_email: z.string().default(""),
  n8n_webhook_url: z.string().default(""),
  n8n_webhook_url_test: z.string().default(""),
  n8n_webhook_url_prod: z.string().default(""),
  n8n_secret: z.string().default(""),
  n8n_enabled: z.boolean().default(false),
  google_drive_folder_id: z.string().default(""),
  next_invoice_nr: z.number().default(10000),
  invoice_number_template: z.string().default("{seq}"),
  invoice_filename_template: z.string().default("rechnung_{nr}"),
  logo_url: z.string().default(""),
  stripe_secret_key: z.string().default(""),
  stripe_publishable_key: z.string().default(""),
  paypal_email: z.string().default(""),
  payment_enabled: z.boolean().default(false),
});

export type Company = z.infer<typeof companySchema>;

export const companyUpdateSchema = companySchema
  .omit({ id: true })
  .partial();

export type CompanyUpdate = z.infer<typeof companyUpdateSchema>;

export function useCompany() {
  return useQuery({
    queryKey: ["company"],
    queryFn: () => api.get<Company>("/api/company").then((data) => companySchema.parse(data)),
    staleTime: 60_000,
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: CompanyUpdate) =>
      api.put<Company>("/api/company", patch).then((data) => companySchema.parse(data)),
    onSuccess: (data) => {
      qc.setQueryData(["company"], data);
    },
  });
}
