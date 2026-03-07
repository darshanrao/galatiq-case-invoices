"use client";

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useInvoices, useStats } from "@/hooks/useInvoices";
import { useWebSocket } from "@/hooks/useWebSocket";
import { StatsBar } from "@/components/StatsBar";
import { UploadZone } from "@/components/UploadZone";
import { InvoiceTable } from "@/components/InvoiceTable";
import { ProcessingModal } from "@/components/ProcessingModal";
import { InvoiceDetail } from "@/components/InvoiceDetail";
import { BatchProgress } from "@/components/BatchProgress";
import { Invoice, BatchUploadResponse, WsEvent } from "@/types/invoice";

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: invoices = [] } = useInvoices();
  const { data: stats } = useStats();

  const [processingId, setProcessingId] = useState<string | null>(null);
  const [detailInvoice, setDetailInvoice] = useState<Invoice | null>(null);
  const [batchIds, setBatchIds] = useState<string[] | null>(null);

  // WebSocket: invalidate queries on any update
  useWebSocket((event: WsEvent) => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["invoice", event.invoice_id] });
  });

  const handleUploaded = useCallback((ids: string[]) => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    if (ids.length === 1) {
      setProcessingId(ids[0]);
    }
  }, [qc]);

  const handleBatchStart = useCallback((_res: BatchUploadResponse) => {
    // batch modal opened by handleUploaded via batchIds
  }, []);

  const handleRowClick = (invoice: Invoice) => {
    if (invoice.status === "processing") {
      setProcessingId(invoice.id);
    } else {
      setDetailInvoice(invoice);
    }
  };

  const handleUploads = useCallback((ids: string[]) => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    if (ids.length === 1) {
      setProcessingId(ids[0]);
    } else {
      setBatchIds(ids);
    }
  }, [qc]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Invoice Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">
          Upload invoices below — the AI pipeline processes them automatically in real time.
        </p>
      </div>

      <StatsBar stats={stats} />
      <UploadZone onUploaded={handleUploads} onBatchStart={handleBatchStart} />

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-gray-300">All Invoices</h2>
        <span className="text-sm text-gray-500">{invoices.length} total</span>
      </div>

      <InvoiceTable invoices={invoices} onRowClick={handleRowClick} />

      {/* Modals */}
      {processingId && (
        <ProcessingModal
          invoiceId={processingId}
          onClose={() => setProcessingId(null)}
        />
      )}
      {detailInvoice && (
        <InvoiceDetail
          invoice={detailInvoice}
          onClose={() => setDetailInvoice(null)}
        />
      )}
      {batchIds && (
        <BatchProgress invoiceIds={batchIds} onClose={() => setBatchIds(null)} />
      )}
    </div>
  );
}
