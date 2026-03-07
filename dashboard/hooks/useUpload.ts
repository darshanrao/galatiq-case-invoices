"use client";

import { useState } from "react";
import { UploadResponse, BatchUploadResponse } from "@/types/invoice";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface UploadState {
  uploading: boolean;
  progress: number;
  error: string | null;
}

export function useUpload() {
  const [state, setState] = useState<UploadState>({
    uploading: false,
    progress: 0,
    error: null,
  });

  async function uploadSingle(file: File): Promise<UploadResponse> {
    setState({ uploading: true, progress: 0, error: null });
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Upload failed");
      }
      setState({ uploading: false, progress: 100, error: null });
      return res.json();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setState({ uploading: false, progress: 0, error: msg });
      throw err;
    }
  }

  async function uploadBatch(files: File[]): Promise<BatchUploadResponse> {
    setState({ uploading: true, progress: 0, error: null });
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    try {
      const res = await fetch(`${API}/api/upload/batch`, { method: "POST", body: form });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Batch upload failed");
      }
      setState({ uploading: false, progress: 100, error: null });
      return res.json();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setState({ uploading: false, progress: 0, error: msg });
      throw err;
    }
  }

  return { ...state, uploadSingle, uploadBatch };
}
