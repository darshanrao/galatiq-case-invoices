import { notFound } from "next/navigation";
import DecisionForm from "./DecisionForm";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Review = {
  id: string;
  invoice_number: string;
  vendor: string;
  amount: number;
  flag_pattern: string;
  risk_score: number;
  recommendation: string;
  flag_explanation: string;
  status: string;
  created_at: string;
  decided_at: string | null;
  decision_reasoning: string | null;
};

async function getReview(id: string): Promise<Review | null> {
  const res = await fetch(`${API}/api/reviews/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch review");
  return res.json();
}

function riskColor(score: number) {
  if (score >= 0.7) return "text-red-600 bg-red-50";
  if (score >= 0.4) return "text-yellow-600 bg-yellow-50";
  return "text-green-600 bg-green-50";
}

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const review = await getReview(id);
  if (!review) notFound();

  const isPending = review.status === "pending";

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <a href="/" className="text-sm text-blue-600 hover:underline mb-6 inline-block">
          ← Back to dashboard
        </a>

        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{review.invoice_number}</h1>
              <p className="text-gray-500 mt-1">{review.vendor}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-gray-900">${review.amount.toLocaleString()}</p>
              <span
                className={`inline-block mt-1 px-3 py-1 rounded-full text-sm font-medium ${riskColor(review.risk_score)}`}
              >
                Risk {(review.risk_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Flag details */}
          <div className="space-y-4 mb-8">
            <InfoRow label="Flags detected" value={review.flag_pattern || "none"} mono />
            <InfoRow label="Status" value={review.status} />
            <InfoRow
              label="AI recommendation"
              value={review.recommendation}
              highlight={review.recommendation === "APPROVE" ? "green" : "red"}
            />
            <div>
              <p className="text-sm font-medium text-gray-500 mb-1">Risk explanation</p>
              <p className="text-gray-700 leading-relaxed">{review.flag_explanation}</p>
            </div>
            <InfoRow label="Submitted" value={new Date(review.created_at).toLocaleString()} />
          </div>

          {/* Decision section */}
          {isPending ? (
            <DecisionForm reviewId={review.id} apiUrl={API} />
          ) : (
            <div className="rounded-xl border p-5 bg-gray-50">
              <p className="text-sm font-medium text-gray-500 mb-1">Decision</p>
              <p
                className={`text-lg font-bold ${
                  review.status === "approved" ? "text-green-600" : "text-red-600"
                }`}
              >
                {review.status.toUpperCase()}
              </p>
              {review.decided_at && (
                <p className="text-xs text-gray-400 mt-1">
                  {new Date(review.decided_at).toLocaleString()}
                </p>
              )}
              {review.decision_reasoning && (
                <p className="text-sm text-gray-600 mt-2">{review.decision_reasoning}</p>
              )}
              <p className="text-xs text-gray-400 mt-3">
                This decision has been stored as a business rule. Future invoices with the same
                flag pattern will be auto-decided.
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function InfoRow({
  label,
  value,
  mono,
  highlight,
}: {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: "green" | "red";
}) {
  const valueClass = highlight
    ? highlight === "green"
      ? "text-green-600 font-semibold"
      : "text-red-600 font-semibold"
    : "text-gray-700";

  return (
    <div>
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className={`mt-0.5 ${mono ? "font-mono text-sm" : ""} ${valueClass}`}>{value}</p>
    </div>
  );
}
