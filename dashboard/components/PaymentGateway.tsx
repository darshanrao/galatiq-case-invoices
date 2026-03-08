"use client";

import { useState } from "react";
import { X, CreditCard, Building2, CheckCircle2, Loader2 } from "lucide-react";
import { Invoice } from "@/types/invoice";
import { usePay } from "@/hooks/useInvoices";

interface Props {
  invoice: Invoice;
  onClose: () => void;
  onPaid: (updatedInvoice: Invoice) => void;
}

export function PaymentGateway({ invoice, onClose, onPaid }: Props) {
  const [confirmed, setConfirmed] = useState(false);
  const pay = usePay();

  const vendor = invoice.vendor ?? "Unknown Vendor";
  const amount = invoice.amount ?? 0;

  const handlePay = () => {
    pay.mutate(invoice.id, {
      onSuccess: (updated: Invoice) => {
        setConfirmed(true);
        setTimeout(() => onPaid(updated), 1800);
      },
    });
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60">
      <div className="bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 border border-zinc-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700 bg-zinc-800/60">
          <div className="flex items-center gap-2">
            <CreditCard size={18} className="text-blue-400" />
            <h2 className="font-semibold text-gray-100">Payment Authorization</h2>
          </div>
          {!pay.isPending && !confirmed && (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
              <X size={18} />
            </button>
          )}
        </div>

        <div className="p-6">
          {confirmed ? (
            /* Success state */
            <div className="flex flex-col items-center gap-4 py-4">
              <CheckCircle2 size={52} className="text-green-400" />
              <p className="text-green-300 font-semibold text-lg">Payment Sent</p>
              <p className="text-gray-400 text-sm text-center">
                ${amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} dispatched to{" "}
                <span className="text-gray-200">{vendor}</span>
              </p>
            </div>
          ) : (
            <>
              {/* Payment summary */}
              <div className="bg-zinc-800 rounded-xl p-4 mb-5 border border-zinc-700">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-blue-900/40 border border-blue-700/40">
                    <Building2 size={20} className="text-blue-300" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-gray-500 mb-0.5">Paying to</p>
                    <p className="font-semibold text-gray-100">{vendor}</p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-zinc-700 flex items-baseline justify-between">
                  <span className="text-sm text-gray-400">Amount</span>
                  <span className="text-2xl font-bold text-white">
                    ${amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              {/* Payment method */}
              <div className="mb-5">
                <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Payment Method</p>
                <div className="flex items-center gap-3 bg-zinc-800 border border-zinc-600 rounded-lg px-4 py-3">
                  <div className="w-2 h-2 rounded-full bg-blue-400" />
                  <span className="text-sm font-medium text-gray-200">ACH Bank Transfer</span>
                  <span className="ml-auto text-xs text-gray-500">Standard 1–2 days</span>
                </div>
              </div>

              {/* Invoice reference */}
              <div className="mb-6 text-xs text-gray-500 flex justify-between">
                <span>Invoice reference</span>
                <span className="text-gray-400 font-mono">{invoice.id}</span>
              </div>

              {/* Actions */}
              {pay.isError && (
                <p className="text-red-400 text-xs mb-3 text-center">
                  Payment failed — please try again.
                </p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={onClose}
                  disabled={pay.isPending}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-zinc-600 text-gray-300 text-sm font-medium hover:bg-zinc-700 transition disabled:opacity-40"
                >
                  Cancel
                </button>
                <button
                  onClick={handlePay}
                  disabled={pay.isPending}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {pay.isPending ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Processing…
                    </>
                  ) : (
                    "Confirm Payment"
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
