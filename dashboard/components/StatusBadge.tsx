"use client";

import { InvoiceStatus } from "@/types/invoice";

const config: Record<string, { label: string; cls: string }> = {
  processing: { label: "Processing", cls: "bg-purple-100 text-purple-700" },
  paid: { label: "Paid", cls: "bg-green-100 text-green-700" },
  rejected: { label: "Rejected", cls: "bg-red-100 text-red-700" },
  pending_review: { label: "Needs Review", cls: "bg-orange-100 text-orange-700" },
  error: { label: "Error", cls: "bg-gray-100 text-gray-700" },
  pending: { label: "Pending", cls: "bg-blue-100 text-blue-700" },
  approved: { label: "Approved", cls: "bg-green-100 text-green-700" },
};

export function StatusBadge({ status }: { status: string }) {
  const { label, cls } = config[status] ?? { label: status, cls: "bg-gray-100 text-gray-700" };
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
      ? "bg-red-100 text-red-700"
      : score >= 0.4
      ? "bg-orange-100 text-orange-700"
      : "bg-green-100 text-green-700";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      Risk {pct}%
    </span>
  );
}
