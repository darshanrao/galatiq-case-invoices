"use client";

import { Invoice } from "@/types/invoice";
import { StatusBadge, RiskBadge } from "./StatusBadge";
import { X } from "lucide-react";

interface Props {
  invoice: Invoice;
  onClose: () => void;
}

export function InvoiceDetail({ invoice, onClose }: Props) {
  const ingestion = invoice.ingestion_data;
  const validation = invoice.validation_data;
  const approval = invoice.approval_data;
  const payment = invoice.payment_data;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 overflow-y-auto py-8">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-gray-900 text-xl">{invoice.id}</h2>
              <StatusBadge status={invoice.status} />
            </div>
            <p className="text-sm text-gray-500">{invoice.original_filename}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <InfoCell label="Vendor" value={invoice.vendor ?? "—"} />
            <InfoCell
              label="Amount"
              value={invoice.amount != null ? `$${invoice.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
            />
            <InfoCell label="Due Date" value={invoice.due_date ?? "—"} />
            <InfoCell label="Uploaded" value={new Date(invoice.uploaded_at).toLocaleDateString()} />
            {invoice.completed_at && (
              <InfoCell label="Completed" value={new Date(invoice.completed_at).toLocaleDateString()} />
            )}
          </div>

          {/* Line items */}
          {ingestion?.line_items && ingestion.line_items.length > 0 && (
            <Section title="Line Items">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-100">
                    <th className="pb-2 text-gray-500 font-medium">Item</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Qty</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Unit Price</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {ingestion.line_items.map((li, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1.5 text-gray-700">{li.item}</td>
                      <td className="py-1.5 text-right text-gray-600">{li.quantity}</td>
                      <td className="py-1.5 text-right text-gray-600">${li.unit_price.toFixed(2)}</td>
                      <td className="py-1.5 text-right font-medium text-gray-800">
                        ${(li.line_total ?? li.quantity * li.unit_price).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}

          {/* Validation */}
          {validation && (
            <Section title="Validation">
              <p className={`text-sm font-semibold mb-2 ${validation.passed ? "text-green-600" : "text-red-600"}`}>
                {validation.passed ? "✓ Passed" : "✗ Failed"}
              </p>
              {validation.flags.length > 0 && (
                <div className="space-y-1.5">
                  {validation.flags.map((f, i) => (
                    <div
                      key={i}
                      className={`text-xs px-3 py-1.5 rounded ${
                        f.severity === "HARD_FAIL"
                          ? "bg-red-50 text-red-700 border border-red-100"
                          : f.severity === "WARNING"
                          ? "bg-orange-50 text-orange-700 border border-orange-100"
                          : "bg-blue-50 text-blue-700 border border-blue-100"
                      }`}
                    >
                      <span className="font-semibold">[{f.severity}]</span> {f.message}
                    </div>
                  ))}
                </div>
              )}
              {validation.arithmetic && (
                <div className="mt-2 text-xs text-gray-600">
                  Arithmetic: claimed ${validation.arithmetic.claimed_total.toFixed(2)} · computed $
                  {validation.arithmetic.computed_total.toFixed(2)} ·{" "}
                  <span className={validation.arithmetic.matches ? "text-green-600" : "text-red-600"}>
                    {validation.arithmetic.matches ? "Match ✓" : `Discrepancy $${validation.arithmetic.discrepancy.toFixed(2)}`}
                  </span>
                </div>
              )}
            </Section>
          )}

          {/* Approval */}
          {approval && (
            <Section title="Approval Decision">
              <div className="flex items-center gap-3 mb-3">
                <span className={`font-bold text-lg ${
                  approval.decision === "APPROVED" ? "text-green-600" :
                  approval.decision === "REJECTED" ? "text-red-600" : "text-orange-600"
                }`}>
                  {approval.decision}
                </span>
                <RiskBadge score={approval.risk_score} />
                <span className="text-xs text-gray-400">{approval.source}</span>
              </div>
              <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 border border-gray-100">
                {approval.reasoning}
              </p>
            </Section>
          )}

          {/* Payment */}
          {payment && (
            <Section title="Payment">
              <div
                className={`rounded-xl p-4 text-center font-semibold ${
                  payment.status === "paid"
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                }`}
              >
                {payment.status === "paid"
                  ? `✓ Paid $${payment.amount?.toLocaleString()} to ${payment.vendor}`
                  : `✗ Rejected — ${payment.rejection_reason ?? "no reason given"}`}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-medium text-gray-800">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </div>
  );
}
