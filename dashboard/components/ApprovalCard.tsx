"use client";

import { useState } from "react";
import { Invoice } from "@/types/invoice";
import { RiskBadge, StatusBadge } from "./StatusBadge";
import { useApprove, useReject } from "@/hooks/useInvoices";
import { CheckCircle, XCircle, ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  invoice: Invoice;
}

export function ApprovalCard({ invoice }: Props) {
  const [reasoning, setReasoning] = useState("");
  const [expanded, setExpanded] = useState(false);
  const approve = useApprove();
  const reject = useReject();

  const review = invoice.review_data;
  const approval = invoice.approval_data;

  const isPending = approve.isPending || reject.isPending;

  return (
    <div className="bg-zinc-800 rounded-xl border border-zinc-700 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-5 gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-bold text-gray-100 text-lg">{invoice.id}</span>
            <StatusBadge status={invoice.status} />
            {review && <RiskBadge score={review.risk_score} />}
          </div>
          <p className="text-gray-400">{invoice.vendor ?? review?.vendor ?? "—"}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-2xl font-bold text-gray-100">
            ${(invoice.amount ?? review?.amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          {invoice.original_filename && (
            <p className="text-xs text-gray-400 mt-0.5">{invoice.original_filename}</p>
          )}
        </div>
      </div>

      {/* Flags */}
      {review?.flag_pattern && (
        <div className="px-5 pb-3">
          <p className="text-xs text-gray-500 mb-1">Flags detected:</p>
          <div className="flex flex-wrap gap-1.5">
            {review.flag_pattern.split("|").filter(Boolean).map((f) => (
              <span key={f} className="px-2 py-0.5 bg-orange-900/50 text-orange-300 rounded-full text-xs font-medium">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Agent explanation */}
      {review?.flag_explanation && (
        <div className="px-5 pb-3">
          <p className="text-xs text-gray-500 mb-1">Agent explanation:</p>
          <p className="text-sm text-gray-300 bg-zinc-700/50 rounded-lg p-3 border border-zinc-600">
            {review.flag_explanation}
          </p>
        </div>
      )}

      {/* Recommendation */}
      {review?.recommendation && (
        <div className="px-5 pb-3">
          <span className={`text-xs font-semibold px-2 py-1 rounded ${
            review.recommendation === "APPROVE"
              ? "bg-green-900/50 text-green-300"
              : "bg-red-900/50 text-red-300"
          }`}>
            AI Recommends: {review.recommendation}
          </span>
        </div>
      )}

      {/* Validation flags detail */}
      {invoice.validation_data?.flags && invoice.validation_data.flags.length > 0 && (
        <div className="px-5 pb-3">
          <button
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {invoice.validation_data.flags.length} validation flag(s)
          </button>
          {expanded && (
            <div className="mt-2 space-y-1">
              {invoice.validation_data.flags.map((f, i) => (
                <div key={i} className={`text-xs px-3 py-1.5 rounded ${
                  f.severity === "HARD_FAIL"
                    ? "bg-red-900/40 text-red-300"
                    : "bg-orange-900/40 text-orange-300"
                }`}>
                  <span className="font-semibold">[{f.severity}]</span> {f.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reasoning textarea */}
      <div className="px-5 pb-3">
        <textarea
          className="w-full text-sm border border-zinc-600 rounded-lg p-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 bg-zinc-900 text-gray-200 placeholder-gray-500"
          rows={2}
          placeholder="Add reasoning (optional)…"
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3 px-5 pb-5">
        <button
          disabled={isPending}
          onClick={() => approve.mutate({ id: invoice.id, reasoning })}
          className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white font-semibold py-2.5 rounded-xl transition-colors"
        >
          <CheckCircle size={16} />
          Approve
        </button>
        <button
          disabled={isPending}
          onClick={() => reject.mutate({ id: invoice.id, reasoning })}
          className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white font-semibold py-2.5 rounded-xl transition-colors"
        >
          <XCircle size={16} />
          Reject
        </button>
      </div>

      {(approve.isError || reject.isError) && (
        <p className="px-5 pb-4 text-sm text-red-400">
          {approve.error?.message || reject.error?.message}
        </p>
      )}
    </div>
  );
}
