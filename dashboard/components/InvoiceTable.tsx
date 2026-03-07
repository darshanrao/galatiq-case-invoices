"use client";

import { Invoice } from "@/types/invoice";
import { StatusBadge } from "./StatusBadge";
import { ExternalLink } from "lucide-react";

interface Props {
  invoices: Invoice[];
  onRowClick?: (invoice: Invoice) => void;
}

export function InvoiceTable({ invoices, onRowClick }: Props) {
  if (invoices.length === 0) {
    return (
      <div className="bg-zinc-800 rounded-xl border border-zinc-700 p-10 text-center text-gray-500">
        No invoices yet. Upload one above.
      </div>
    );
  }

  return (
    <div className="bg-zinc-800 rounded-xl border border-zinc-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-zinc-700/50 border-b border-zinc-700">
            <th className="px-4 py-3 text-left font-semibold text-gray-400">Invoice ID</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-400">File</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-400">Vendor</th>
            <th className="px-4 py-3 text-right font-semibold text-gray-400">Amount</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-400">Status</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-400">Uploaded</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr
              key={inv.id}
              className="border-b border-zinc-700/50 hover:bg-zinc-700/30 cursor-pointer transition-colors"
              onClick={() => onRowClick?.(inv)}
            >
              <td className="px-4 py-3 font-mono text-gray-300">{inv.id}</td>
              <td className="px-4 py-3 text-gray-400 max-w-[200px] truncate">
                {inv.original_filename ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-300">{inv.vendor ?? "—"}</td>
              <td className="px-4 py-3 text-right font-medium text-gray-100">
                {inv.amount != null ? `$${inv.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={inv.status} />
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">
                {new Date(inv.uploaded_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={(e) => { e.stopPropagation(); onRowClick?.(inv); }}
                  className="text-blue-400 hover:text-blue-300 flex items-center gap-1 ml-auto"
                >
                  <ExternalLink size={14} />
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
