"use client";

import { InvoiceStatus } from "@/types/invoice";

const config: Record<string, { label: string; cls: string }> = {
  processing: { label: "Processing", cls: "bg-purple-900/50 text-purple-300" },
  paid: { label: "Paid", cls: "bg-green-900/50 text-green-300" },
  rejected: { label: "Rejected", cls: "bg-red-900/50 text-red-300" },
  pending_review: { label: "Needs Review", cls: "bg-orange-900/50 text-orange-300" },
  error: { label: "Error", cls: "bg-zinc-700 text-gray-300" },
  pending: { label: "Pending", cls: "bg-blue-900/50 text-blue-300" },
  approved: { label: "Awaiting Payment", cls: "bg-blue-900/50 text-blue-300" },
};

export function StatusBadge({ status }: { status: string }) {
  const { label, cls } = config[status] ?? { label: status, cls: "bg-zinc-700 text-gray-300" };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

export function RiskBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.7
      ? "bg-red-900/50 text-red-300"
      : score >= 0.4
      ? "bg-orange-900/50 text-orange-300"
      : "bg-green-900/50 text-green-300";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      Risk {pct}%
    </span>
  );
}
