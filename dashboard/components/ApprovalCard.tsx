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
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-5 gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-bold text-gray-900 text-lg">{invoice.id}</span>
            <StatusBadge status={invoice.status} />
            {review && <RiskBadge score={review.risk_score} />}
          </div>
          <p className="text-gray-600">{invoice.vendor ?? review?.vendor ?? "—"}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-2xl font-bold text-gray-900">
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
              <span key={f} className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full text-xs font-medium">
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
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 border border-gray-100">
            {review.flag_explanation}
          </p>
        </div>
      )}

      {/* Recommendation */}
      {review?.recommendation && (
        <div className="px-5 pb-3">
          <span className={`text-xs font-semibold px-2 py-1 rounded ${
            review.recommendation === "APPROVE"
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }`}>
            AI Recommends: {review.recommendation}
          </span>
        </div>
      )}

      {/* Validation flags detail */}
      {invoice.validation_data?.flags && invoice.validation_data.flags.length > 0 && (
        <div className="px-5 pb-3">
          <button
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
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
                    ? "bg-red-50 text-red-700"
                    : "bg-orange-50 text-orange-700"
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
          className="w-full text-sm border border-gray-200 rounded-lg p-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300 text-gray-700"
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
        <p className="px-5 pb-4 text-sm text-red-600">
          {approve.error?.message || reject.error?.message}
        </p>
      )}
    </div>
  );
}
