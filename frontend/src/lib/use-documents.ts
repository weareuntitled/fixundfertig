import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api, ApiError } from "./api";

export const documentSchema = z.object({
  id: z.number().int(),
  original_filename: z.string().default(""),
  title: z.string().default(""),
  vendor: z.string().default(""),
  doc_number: z.string().default(""),
  doc_date: z.string().default(""),
  amount_total: z.number().nullable().default(null),
  amount_net: z.number().nullable().default(null),
  amount_tax: z.number().nullable().default(null),
  currency: z.string().default(""),
  mime: z.string().default(""),
  size: z.number().int().default(0),
  source: z.string().default("MANUAL"),
  type: z.string().default(""),
  description: z.string().default(""),
  created_at: z.string().default(""),
});

export type Document = z.infer<typeof documentSchema>;

const documentListSchema = z.array(documentSchema);

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: () =>
      api
        .get<unknown>("/api/documents")
        .then((data) => documentListSchema.parse(data)),
  });
}

/** Uploads one file (PDF/JPG/PNG) to the Belege and returns the stored document. */
export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const csrf = document.cookie
        .split("; ")
        .find((c) => c.startsWith("ff_csrf="))
        ?.split("=")[1];
      const response = await fetch("/api/documents/upload", {
        method: "POST",
        credentials: "include",
        headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {},
        body: form,
      });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data && typeof data === "object" && "detail" in data ? String((data as { detail: unknown }).detail) : "";
        throw new ApiError(response.status, detail || `HTTP ${response.status}`, data);
      }
      return documentSchema.parse(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}
