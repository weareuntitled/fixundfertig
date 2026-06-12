import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import {
  invoiceReadSchema,
  invoiceStatusSchema,
  type InvoiceRead,
  type InvoiceStatus,
  type InvoiceItem,
} from "./schemas/invoice";

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: () =>
      api
        .get<unknown>("/api/invoices")
        .then((data) => z.array(invoiceReadSchema).parse(data)),
  });
}

export function useInvoice(id: number) {
  return useQuery({
    queryKey: ["invoices", id],
    queryFn: () =>
      api
        .get<unknown>(`/api/invoices/${id}`)
        .then((data) => invoiceReadSchema.parse(data)),
    enabled: id > 0,
  });
}

export function useUpdateInvoiceStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: InvoiceStatus }) =>
      api.put<unknown>(`/api/invoices/${id}/status`, { status }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoices", vars.id] });
    },
  });
}

export function useAddInvoiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, item }: { invoiceId: number; item: Omit<InvoiceItem, "id"> }) =>
      api
        .post<unknown>(`/api/invoices/${invoiceId}/items`, item)
        .then((data) => invoiceReadSchema.parse(data)),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoices", vars.invoiceId] });
    },
  });
}

export function useUpdateInvoiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      invoiceId,
      itemId,
      item,
    }: {
      invoiceId: number;
      itemId: number;
      item: Omit<InvoiceItem, "id">;
    }) =>
      api
        .put<unknown>(`/api/invoices/${invoiceId}/items/${itemId}`, item)
        .then((data) => invoiceReadSchema.parse(data)),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoices", vars.invoiceId] });
    },
  });
}

export function useDeleteInvoiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, itemId }: { invoiceId: number; itemId: number }) =>
      api
        .delete<unknown>(`/api/invoices/${invoiceId}/items/${itemId}`)
        .then((data) => invoiceReadSchema.parse(data)),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoices", vars.invoiceId] });
    },
  });
}

export { ApiError, invoiceStatusSchema };
export type { InvoiceRead };
