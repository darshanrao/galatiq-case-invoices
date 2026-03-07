"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function DecisionForm({ reviewId, apiUrl }: { reviewId: string; apiUrl: string }) {
  const router = useRouter();
  const [reasoning, setReasoning] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(decision: "APPROVED" | "REJECTED") {
    if (!reasoning.trim()) {
      setError("Please provide a reasoning before deciding.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiUrl}/api/reviews/${reviewId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reasoning }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail ?? "Request failed");
      }
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Your reasoning <span className="text-red-500">*</span>
        </label>
        <textarea
          className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          rows={3}
          placeholder="Explain your decision in one or two sentences. This becomes the business rule for future identical invoices."
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          disabled={loading}
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-3">
        <button
          onClick={() => submit("APPROVED")}
          disabled={loading}
          className="flex-1 rounded-lg bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold py-3 transition"
        >
          {loading ? "Submitting…" : "Approve"}
        </button>
        <button
          onClick={() => submit("REJECTED")}
          disabled={loading}
          className="flex-1 rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-semibold py-3 transition"
        >
          {loading ? "Submitting…" : "Reject"}
        </button>
      </div>

      <p className="text-xs text-gray-400 text-center">
        Your decision will be stored immediately as a business rule (count = 3).
        The next invoice with the same flag pattern will auto-decide without human review.
      </p>
    </div>
  );
}
