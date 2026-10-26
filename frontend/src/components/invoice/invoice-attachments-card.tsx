import { useRef, useState } from "react";
import { Download, FileText, Loader2, Paperclip, Plus, Upload, X } from "lucide-react";
import { useDocuments, useUploadDocument, type Document } from "@/lib/use-documents";
import {
  useAddInvoiceAttachment,
  useDeleteInvoiceAttachment,
} from "@/lib/use-invoices";
import { useNotification } from "@/lib/use-notifications";
import type { InvoiceAttachment } from "@/lib/schemas/invoice";

interface InvoiceAttachmentsCardProps {
  invoiceId: number;
  attachments: InvoiceAttachment[];
}

function formatSize(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function AttachmentRow({
  attachment,
  onRemove,
  removing,
}: {
  attachment: InvoiceAttachment;
  onRemove: (attachment: InvoiceAttachment) => void;
  removing: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-bright)] px-2.5 py-2">
      <div className="flex min-w-0 items-start gap-2">
        <FileText size={16} className="mt-0.5 shrink-0 text-[var(--color-text-muted)]" />
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-[var(--color-text-primary)]">
            {attachment.title || attachment.filename || `Beleg ${attachment.document_id}`}
          </p>
          <p className="truncate text-[12px] text-[var(--color-text-muted)]">
            {attachment.filename}
            {attachment.size > 0 && <span> · {formatSize(attachment.size)}</span>}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <a
          href={`/api/documents/${attachment.document_id}/file`}
          target="_blank"
          rel="noopener"
          className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-brand-text)]"
          title="Beleg öffnen"
        >
          <Download size={15} />
        </a>
        <button
          type="button"
          onClick={() => onRemove(attachment)}
          disabled={removing}
          className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded text-[var(--color-text-muted)] transition-colors hover:bg-red-500/10 hover:text-red-600 disabled:opacity-50"
          title="Beleg entfernen"
        >
          <X size={15} />
        </button>
      </div>
    </div>
  );
}

function AttachmentPicker({
  available,
  selectedId,
  adding,
  onSelect,
  onAdd,
}: {
  available: Document[];
  selectedId: number | null;
  adding: boolean;
  onSelect: (id: number | null) => void;
  onAdd: () => void;
}) {
  return (
    <div className="flex flex-col gap-2 border-t border-[var(--color-border)] pt-[var(--space-md)]">
      <select
        value={selectedId ?? ""}
        onChange={(event) => onSelect(event.target.value ? Number(event.target.value) : null)}
        className="min-h-[44px] flex-1 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 text-[13px] text-[var(--color-text-primary)]"
      >
        <option value="">Beleg auswählen …</option>
        {available.map((document) => (
          <option key={document.id} value={document.id}>
            {document.vendor ? `${document.vendor} · ` : ""}
            {document.title || document.original_filename}
            {document.doc_number ? ` · ${document.doc_number}` : ""}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={onAdd}
        disabled={selectedId === null || adding}
        className="inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] transition-colors hover:bg-[var(--color-surface-container-high)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {adding ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
        Hinzufügen
      </button>
    </div>
  );
}

export function InvoiceAttachmentsCard({ invoiceId, attachments }: InvoiceAttachmentsCardProps) {
  const { data: documents } = useDocuments();
  const addAttachment = useAddInvoiceAttachment();
  const uploadDocument = useUploadDocument();
  const fileInput = useRef<HTMLInputElement>(null);
  const removeAttachment = useDeleteInvoiceAttachment();
  const { notify } = useNotification();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const attachedIds = new Set(attachments.map((attachment) => attachment.document_id));
  const available = (documents ?? []).filter((document) => !attachedIds.has(document.id));

  const add = () => {
    if (selectedId === null) return;
    addAttachment.mutate(
      { invoiceId, documentId: selectedId },
      {
        onSuccess: () => {
          setSelectedId(null);
          notify("success", "Beleg angehängt");
        },
        onError: (error: Error) => notify("error", error.message),
      },
    );
  };

  const upload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    uploadDocument.mutate(file, {
      onSuccess: (document) =>
        addAttachment.mutate(
          { invoiceId, documentId: document.id },
          {
            onSuccess: () => notify("success", "Anlage hochgeladen und angehängt"),
            onError: (error: Error) => notify("error", error.message),
          },
        ),
      onError: (error: Error) => notify("error", error.message),
    });
  };

  const remove = (attachment: InvoiceAttachment) => {
    removeAttachment.mutate(
      { invoiceId, attachmentId: attachment.id },
      {
        onSuccess: () => notify("success", "Beleg entfernt"),
        onError: (error: Error) => notify("error", error.message),
      },
    );
  };

  return (
    <div id="anlagen" className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-md)] py-[var(--space-sm)]">
        <h3 className="flex items-center gap-2 text-[16px] font-semibold text-[var(--color-text-heading)]">
          <Paperclip size={18} />
          Anlagen
          {attachments.length > 0 && (
            <span className="rounded-full bg-[var(--color-surface-container-high)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-text-secondary)]">
              {attachments.length}
            </span>
          )}
        </h3>
      </div>

      <div className="space-y-[var(--space-sm)] px-[var(--space-md)] py-[var(--space-sm)]">
        {attachments.length === 0 && (
          <p className="text-[14px] text-[var(--color-text-secondary)]">
            Noch keine Anlagen. Hochgeladene Dateien (PDF, JPG, PNG) kannst du beim Senden als separate Anhänge mitschicken; die Rechnungs-PDF bleibt unverändert.
          </p>
        )}

        {attachments.map((attachment) => (
          <AttachmentRow
            key={attachment.id}
            attachment={attachment}
            onRemove={remove}
            removing={removeAttachment.isPending && removeAttachment.variables?.attachmentId === attachment.id}
          />
        ))}

        <div>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            className="hidden"
            aria-label="Anlage auswählen"
            onChange={upload}
          />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={uploadDocument.isPending || addAttachment.isPending}
            className="inline-flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-[var(--radius-lg)] bg-[var(--color-brand-text)] px-4 text-[12px] font-semibold uppercase tracking-[0.05em] text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploadDocument.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
            Anlage hochladen
          </button>
        </div>

        <AttachmentPicker
          available={available}
          selectedId={selectedId}
          adding={addAttachment.isPending}
          onSelect={setSelectedId}
          onAdd={add}
        />

      </div>
    </div>
  );
}
