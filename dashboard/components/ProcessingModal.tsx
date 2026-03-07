"use client";

import { useEffect, useState } from "react";
import { useInvoice } from "@/hooks/useInvoices";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Invoice, WsEvent } from "@/types/invoice";
import { CheckCircle2, Circle, Loader2, XCircle, X } from "lucide-react";

const STAGES = [
  { key: "ingestion", label: "Ingestion", desc: "Extract invoice fields" },
  { key: "validation", label: "Validation", desc: "Check against inventory" },
  { key: "approval", label: "Approval", desc: "VP-level decision engine" },
  { key: "payment", label: "Payment", desc: "Execute or route for review" },
];

function stageStatus(invoice: Invoice | undefined, stageKey: string) {
  if (!invoice) return "waiting";
  const dataKey = `${stageKey}_data` as keyof Invoice;
  const hasData = !!invoice[dataKey];

  if (stageKey === "payment" || stageKey === "queue_for_review") {
    const done = ["paid", "rejected", "pending_review", "error"].includes(invoice.status);
    if (done) return "done";
    if (invoice.status === "processing" && hasData) return "done";
  }

  if (hasData) return "done";

  const order = ["ingestion", "validation", "approval", "payment"];
  const idx = order.indexOf(stageKey);
  const prevKey = idx > 0 ? `${order[idx - 1]}_data` as keyof Invoice : null;
  const prevDone = !prevKey || !!invoice[prevKey];

  if (prevDone && invoice.status === "processing") return "active";
  return "waiting";
}

interface StageCardProps {
  label: string;
  desc: string;
  status: "done" | "active" | "waiting" | "failed";
  stageKey: string;
  invoice?: Invoice;
}

function StageCard({ label, desc, status, stageKey, invoice }: StageCardProps) {
  const icon =
    status === "done" ? (
      <CheckCircle2 size={22} className="text-green-500" />
    ) : status === "active" ? (
      <Loader2 size={22} className="animate-spin text-purple-600" />
    ) : status === "failed" ? (
      <XCircle size={22} className="text-red-500" />
    ) : (
      <Circle size={22} className="text-gray-500" />
    );

  const border =
    status === "done"
      ? "border-green-700/50 bg-green-900/30"
      : status === "active"
      ? "border-purple-500 bg-purple-900/40 ring-2 ring-purple-500/30"
      : status === "failed"
      ? "border-red-700/50 bg-red-900/30"
      : "border-zinc-600 bg-zinc-800/50";

  const dataKey = `${stageKey}_data` as keyof Invoice;
  const data = invoice?.[dataKey] as Record<string, unknown> | undefined;

  return (
    <div className={`rounded-xl border p-4 transition-all ${border}`}>
      <div className="flex items-center gap-3 mb-1">
        {icon}
        <div>
        <p className="font-semibold text-gray-200">{label}</p>
        <p className="text-xs text-gray-500">{desc}</p>
        </div>
      </div>
      {data && status === "done" && stageKey === "ingestion" && (
        <div className="mt-2 text-xs text-gray-400 space-y-0.5">
          {!!data.vendor && <p>Vendor: <span className="font-medium">{String(data.vendor)}</span></p>}
          {data.amount != null && (
            <p>Amount: <span className="font-medium">${Number(data.amount).toLocaleString()}</span></p>
          )}
          {!!data.invoice_number && <p>Invoice #: {String(data.invoice_number)}</p>}
        </div>
      )}
      {data && status === "done" && stageKey === "validation" && (
        <div className="mt-2 text-xs text-gray-400">
          <p>
            {(data.passed as boolean)
              ? <span className="text-green-400 font-medium">✓ Passed</span>
              : <span className="text-red-400 font-medium">✗ Failed</span>}
            {" "}— {(data.flags as unknown[])?.length ?? 0} flag(s)
          </p>
        </div>
      )}
      {data && status === "done" && stageKey === "approval" && (
        <div className="mt-2 text-xs text-gray-400">
          <p>Decision: <span className="font-medium">{String(data.decision)}</span></p>
          <p>Risk: {Math.round(Number(data.risk_score) * 100)}%</p>
        </div>
      )}
    </div>
  );
}

interface Props {
  invoiceId: string | null;
  onClose: () => void;
}

export function ProcessingModal({ invoiceId, onClose }: Props) {
  const { data: invoice, refetch } = useInvoice(invoiceId);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);

  useWebSocket((event) => {
    if (event.invoice_id === invoiceId) {
      setLastEvent(event);
      refetch();
    }
  });

  if (!invoiceId) return null;

  const isDone = invoice && ["paid", "rejected", "pending_review", "error"].includes(invoice.status);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-zinc-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <div>
            <h2 className="font-bold text-gray-100 text-lg">Processing Invoice</h2>
            <p className="text-xs text-gray-500 font-mono">{invoiceId}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <X size={20} />
          </button>
        </div>

        {/* Stage cards */}
        <div className="p-6 space-y-3">
          {STAGES.map((s) => {
            const st = stageStatus(invoice, s.key);
            return (
              <StageCard
                key={s.key}
                label={s.label}
                desc={s.desc}
                status={st}
                stageKey={s.key}
                invoice={invoice}
              />
            );
          })}
        </div>

        {/* Footer */}
        {isDone && invoice && (
          <div className="px-6 pb-6">
            <div
              className={`rounded-xl p-4 text-center font-semibold ${
                invoice.status === "paid"
                  ? "bg-green-900/40 text-green-300 border border-green-700/50"
                  : invoice.status === "pending_review"
                  ? "bg-orange-900/40 text-orange-300 border border-orange-700/50"
                  : "bg-red-900/40 text-red-300 border border-red-700/50"
              }`}
            >
              {invoice.status === "paid" && "✓ Invoice Approved & Paid"}
              {invoice.status === "pending_review" && "⚠ Sent to Human Review Queue"}
              {invoice.status === "rejected" && "✗ Invoice Rejected"}
              {invoice.status === "error" && "✗ Processing Error"}
            </div>
            <button
              onClick={onClose}
              className="mt-3 w-full py-2 rounded-xl bg-zinc-700 hover:bg-zinc-600 text-gray-200 font-medium transition-colors"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
