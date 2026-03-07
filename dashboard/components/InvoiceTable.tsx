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
      <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-400">
        No invoices yet. Upload one above.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Invoice ID</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">File</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Vendor</th>
            <th className="px-4 py-3 text-right font-semibold text-gray-600">Amount</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Uploaded</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr
              key={inv.id}
              className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
              onClick={() => onRowClick?.(inv)}
            >
              <td className="px-4 py-3 font-mono text-gray-700">{inv.id}</td>
              <td className="px-4 py-3 text-gray-600 max-w-[200px] truncate">
                {inv.original_filename ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-700">{inv.vendor ?? "—"}</td>
              <td className="px-4 py-3 text-right font-medium text-gray-900">
                {inv.amount != null ? `$${inv.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={inv.status} />
              </td>
              <td className="px-4 py-3 text-gray-400 text-xs">
                {new Date(inv.uploaded_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={(e) => { e.stopPropagation(); onRowClick?.(inv); }}
                  className="text-blue-500 hover:text-blue-700 flex items-center gap-1 ml-auto"
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
