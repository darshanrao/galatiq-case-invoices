"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Invoice, Stats } from "@/types/invoice";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchInvoices(status?: string): Promise<Invoice[]> {
  const url = status ? `${API}/api/invoices?status=${status}` : `${API}/api/invoices`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch invoices");
  return res.json();
}

async function fetchInvoice(id: string): Promise<Invoice> {
  const res = await fetch(`${API}/api/invoices/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch invoice ${id}`);
  return res.json();
}

async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API}/api/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export function useInvoices(status?: string) {
  return useQuery<Invoice[]>({
    queryKey: ["invoices", status],
    queryFn: () => fetchInvoices(status),
    refetchInterval: 3000,
  });
}

export function useInvoice(id: string | null) {
  return useQuery<Invoice>({
    queryKey: ["invoice", id],
    queryFn: () => fetchInvoice(id!),
    enabled: !!id,
    refetchInterval: 2000,
  });
}

export function useStats() {
  return useQuery<Stats>({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 3000,
  });
}

export function useApprove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reasoning }: { id: string; reasoning: string }) => {
      const res = await fetch(`${API}/api/approve/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reasoning }),
      });
      if (!res.ok) throw new Error("Approval failed");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function usePay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API}/api/pay/${id}`, { method: "POST" });
      if (!res.ok) throw new Error("Payment failed");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useReject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reasoning }: { id: string; reasoning: string }) => {
      const res = await fetch(`${API}/api/reject/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reasoning }),
      });
      if (!res.ok) throw new Error("Rejection failed");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
