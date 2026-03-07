"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useInvoices } from "@/hooks/useInvoices";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ApprovalCard } from "@/components/ApprovalCard";
import { WsEvent } from "@/types/invoice";
import { AlertTriangle } from "lucide-react";

export default function ApprovalPage() {
  const qc = useQueryClient();
  const { data: invoices = [], isLoading } = useInvoices("pending_review");

  useWebSocket((event: WsEvent) => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
        <p className="text-gray-500 text-sm mt-1">
          Invoices that require human decision. Your approval is stored as a business rule
          — identical patterns auto-decide in the future.
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-gray-400">Loading…</div>
      ) : invoices.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <AlertTriangle size={40} className="text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No invoices pending review</p>
          <p className="text-gray-400 text-sm mt-1">
            Upload an invoice that triggers a novel flag pattern to see it here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">{invoices.length} invoice(s) awaiting decision</p>
          {invoices.map((inv) => (
            <ApprovalCard key={inv.id} invoice={inv} />
          ))}
        </div>
      )}
    </div>
  );
}
