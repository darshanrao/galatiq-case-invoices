"use client";

import { useEffect, useState } from "react";
import { Invoice, WsEvent } from "@/types/invoice";
import { StatusBadge } from "./StatusBadge";
import { useInvoices } from "@/hooks/useInvoices";
import { useWebSocket } from "@/hooks/useWebSocket";
import { X } from "lucide-react";

interface Props {
  invoiceIds: string[];
  onClose: () => void;
}

export function BatchProgress({ invoiceIds, onClose }: Props) {
  const { data: allInvoices, refetch } = useInvoices();

  useWebSocket((event: WsEvent) => {
    if (invoiceIds.includes(event.invoice_id)) {
      refetch();
    }
  });

  const invoices = (allInvoices ?? []).filter((inv: Invoice) => invoiceIds.includes(inv.id));

  const done = invoices.filter((i: Invoice) =>
    ["paid", "rejected", "pending_review", "error"].includes(i.status)
  ).length;
  const pct = invoiceIds.length > 0 ? Math.round((done / invoiceIds.length) * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 border border-zinc-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <div>
            <h2 className="font-bold text-gray-100 text-lg">Batch Processing</h2>
            <p className="text-sm text-gray-500">
              {done} / {invoiceIds.length} completed
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <X size={20} />
          </button>
        </div>

        {/* Progress bar */}
        <div className="px-6 pt-5 pb-3">
          <div className="w-full bg-zinc-700 rounded-full h-3">
            <div
              className="bg-blue-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 mt-1 text-right">{pct}%</p>
        </div>

        {/* Per-file status */}
        <div className="px-6 pb-6 space-y-2 max-h-80 overflow-y-auto">
          {invoiceIds.map((id) => {
            const inv = invoices.find((i: Invoice) => i.id === id);
            return (
              <div
                key={id}
                className="flex items-center justify-between bg-zinc-700/50 rounded-lg px-4 py-2.5"
              >
                <div className="min-w-0">
                  <p className="font-mono text-sm text-gray-300">{id}</p>
                  {inv?.original_filename && (
                    <p className="text-xs text-gray-400 truncate">{inv.original_filename}</p>
                  )}
                </div>
                <div className="shrink-0">
                  {inv ? (
                    <StatusBadge status={inv.status} />
                  ) : (
                    <span className="text-xs text-gray-400">Queued</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {done === invoiceIds.length && (
          <div className="px-6 pb-6">
            <button
              onClick={onClose}
              className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors"
            >
              Done — View All Invoices
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
