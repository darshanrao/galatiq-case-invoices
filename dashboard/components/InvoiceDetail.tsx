"use client";

import { useState, useEffect } from "react";
import { Invoice } from "@/types/invoice";
import { StatusBadge, RiskBadge } from "./StatusBadge";
import { PaymentGateway } from "./PaymentGateway";
import { X, Banknote } from "lucide-react";

interface Props {
  invoice: Invoice;
  onClose: () => void;
}

export function InvoiceDetail({ invoice, onClose }: Props) {
  const [currentInvoice, setCurrentInvoice] = useState<Invoice>(invoice);
  const [showPaymentGateway, setShowPaymentGateway] = useState(false);

  // Keep currentInvoice in sync with the parent's polling updates,
  // but don't overwrite local state after payment is confirmed
  useEffect(() => {
    setCurrentInvoice((prev) => (prev.payment_data ? prev : invoice));
  }, [invoice]);

  const ingestion = currentInvoice.ingestion_data;
  const validation = currentInvoice.validation_data;
  const approval = currentInvoice.approval_data;
  const payment = currentInvoice.payment_data;

  return (
    <>
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 overflow-y-auto py-8">
      <div className="bg-zinc-800 rounded-2xl shadow-2xl w-full max-w-2xl mx-4 border border-zinc-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-gray-100 text-xl">
                {currentInvoice.ingestion_data?.invoice_number ?? currentInvoice.id}
              </h2>
              <StatusBadge status={currentInvoice.status} />
            </div>
            <p className="text-xs text-zinc-500 font-mono">{currentInvoice.id} · {currentInvoice.original_filename}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <InfoCell label="Vendor" value={currentInvoice.vendor ?? "—"} />
            <InfoCell
              label="Amount"
              value={currentInvoice.amount != null ? `$${currentInvoice.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
            />
            <InfoCell label="Due Date" value={currentInvoice.due_date ?? "—"} />
            <InfoCell label="Uploaded" value={new Date(currentInvoice.uploaded_at).toLocaleDateString()} />
            {currentInvoice.completed_at && (
              <InfoCell label="Completed" value={new Date(currentInvoice.completed_at).toLocaleDateString()} />
            )}
          </div>

          {/* Line items */}
          {ingestion?.line_items && ingestion.line_items.length > 0 && (
            <Section title="Line Items">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-zinc-700">
                    <th className="pb-2 text-gray-500 font-medium">Item</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Qty</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Unit Price</th>
                    <th className="pb-2 text-gray-500 font-medium text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {ingestion.line_items.map((li, i) => (
                    <tr key={i} className="border-b border-zinc-700/50">
                      <td className="py-1.5 text-gray-300">{li.item}</td>
                      <td className="py-1.5 text-right text-gray-400">{li.quantity}</td>
                      <td className="py-1.5 text-right text-gray-400">${li.unit_price.toFixed(2)}</td>
                      <td className="py-1.5 text-right font-medium text-gray-200">
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
              <p className={`text-sm font-semibold mb-2 ${validation.passed ? "text-green-400" : "text-red-400"}`}>
                {validation.passed ? "✓ Passed" : "✗ Failed"}
              </p>
              {validation.flags.length > 0 && (
                <div className="space-y-1.5">
                  {validation.flags.map((f, i) => (
                    <div
                      key={i}
                      className={`text-xs px-3 py-1.5 rounded ${
                        f.severity === "HARD_FAIL"
                          ? "bg-red-900/40 text-red-300 border border-red-700/50"
                          : f.severity === "WARNING"
                          ? "bg-orange-900/40 text-orange-300 border border-orange-700/50"
                          : "bg-blue-900/40 text-blue-300 border border-blue-700/50"
                      }`}
                    >
                      <span className="font-semibold">[{f.severity}]</span> {f.message}
                    </div>
                  ))}
                </div>
              )}
              {validation.arithmetic && (
                <div className="mt-2 text-xs text-gray-400">
                  Arithmetic: claimed ${validation.arithmetic.claimed_total.toFixed(2)} · computed $
                  {validation.arithmetic.computed_total.toFixed(2)} ·{" "}
                  <span className={validation.arithmetic.matches ? "text-green-400" : "text-red-400"}>
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
                  approval.decision === "APPROVED" ? "text-green-400" :
                  approval.decision === "REJECTED" ? "text-red-400" : "text-orange-400"
                }`}>
                  {approval.decision}
                </span>
                <RiskBadge score={approval.risk_score} />
                <span className="text-xs text-gray-400">{approval.source}</span>
              </div>
              <p className="text-sm text-gray-300 bg-zinc-700/50 rounded-lg p-3 border border-zinc-600">
                {approval.reasoning}
              </p>
            </Section>
          )}

          {/* Pay button — shown when invoice is approved but not yet paid */}
          {currentInvoice.status === "approved" && !payment && (
            <Section title="Payment">
              <div className="rounded-xl p-4 bg-blue-900/20 border border-blue-700/40 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-blue-200">Ready for payment</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Invoice approved — authorize the bank transfer to release funds.
                  </p>
                </div>
                <button
                  onClick={() => setShowPaymentGateway(true)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition whitespace-nowrap"
                >
                  <Banknote size={15} />
                  Pay Now
                </button>
              </div>
            </Section>
          )}

          {/* Payment result */}
          {payment && (
            <Section title="Payment">
              <div
                className={`rounded-xl p-4 font-semibold ${
                  payment.status === "paid"
                    ? "bg-green-900/40 text-green-300 border border-green-700/50"
                    : "bg-red-900/40 text-red-300 border border-red-700/50"
                }`}
              >
                {payment.status === "paid" ? (
                  <div className="space-y-1.5">
                    <p>✓ Paid ${payment.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })} to {payment.vendor}</p>
                    {payment.transaction_id && (
                      <p className="text-xs font-normal text-green-400/80">
                        Txn: {payment.transaction_id} · {payment.payment_method} · {payment.paid_at ? new Date(payment.paid_at).toLocaleString() : ""}
                      </p>
                    )}
                  </div>
                ) : (
                  `✗ Rejected — ${payment.rejection_reason ?? "no reason given"}`
                )}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>

    {showPaymentGateway && (
      <PaymentGateway
        invoice={currentInvoice}
        onClose={() => setShowPaymentGateway(false)}
        onPaid={(updated) => {
          setCurrentInvoice(updated);
          setShowPaymentGateway(false);
        }}
      />
    )}
    </>
  );
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-medium text-gray-200">{value}</p>
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
