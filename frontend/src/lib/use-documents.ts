import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "./api";

const documentSchema = z.object({
  id: z.number().int(),
  filename: z.string().default(""),
  original_filename: z.string().default(""),
  mime: z.string().default(""),
  size: z.number().int().default(0),
  source: z.string().default("MANUAL"),
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
