import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "./api";

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
