/**
 * Abschlag abrechnen (#499): legt die Abschlagsrechnung zu einer Rate an und
 * springt danach zu ihr. Das Verhalten liegt an einer Stelle, damit die
 * Angebotsseite und die Zahlungsplankarte dasselbe tun.
 */
import { useNavigate } from "@tanstack/react-router";
import { useCreateDownPayment } from "./use-invoices";
import { useNotification } from "./use-notifications";

export function useBillDownPayment(quoteId: number) {
  const navigate = useNavigate();
  const { notify } = useNotification();
  const bill = useCreateDownPayment();

  /** Rate abrechnen: Abschlagsrechnung anlegen und zu ihr springen. */
  const billRate = (installmentIndex: number) =>
    bill.mutate(
      { quoteId, installmentIndex },
      {
        onSuccess: (invoice) => {
          notify(
            "success",
            invoice.nr ? `Abschlagsrechnung ${invoice.nr} angelegt` : "Abschlagsrechnung angelegt",
          );
          void navigate({ to: "/invoices/$id", params: { id: String(invoice.id) } });
        },
        onError: (err: Error) => notify("error", err.message),
      },
    );

  return { billRate, isPending: bill.isPending };
}
