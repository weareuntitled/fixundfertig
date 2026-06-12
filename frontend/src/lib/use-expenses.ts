import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "./api";

const expenseSchema = z.object({
  id: z.number().int(),
  company_id: z.number().int(),
  date: z.string(),
  category: z.string(),
  description: z.string().default(""),
  amount: z.number(),
  source: z.string().default("MANUAL"),
});

export type Expense = z.infer<typeof expenseSchema>;

const expenseListSchema = z.array(expenseSchema);

export function useExpenses() {
  return useQuery({
    queryKey: ["expenses"],
    queryFn: () =>
      api
        .get<unknown>("/api/expenses")
        .then((data) => expenseListSchema.parse(data)),
  });
}
