"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Loader2 } from "lucide-react";
import { useUpload } from "@/hooks/useUpload";
import { BatchUploadResponse, UploadResponse } from "@/types/invoice";

interface Props {
  onUploaded?: (ids: string[]) => void;
  onBatchStart?: (response: BatchUploadResponse) => void;
}

export function UploadZone({ onUploaded, onBatchStart }: Props) {
  const { uploading, uploadSingle, uploadBatch } = useUpload();
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      setError(null);
      try {
        if (files.length === 1) {
          const res: UploadResponse = await uploadSingle(files[0]);
          onUploaded?.([res.invoice_id]);
        } else {
          const res: BatchUploadResponse = await uploadBatch(files);
          onBatchStart?.(res);
          onUploaded?.(res.invoice_ids);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    },
    [uploadSingle, uploadBatch, onUploaded, onBatchStart]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/plain": [".txt"],
      "application/pdf": [".pdf"],
      "application/json": [".json"],
    },
    disabled: uploading,
  });

  return (
    <div className="mb-8">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-900/40" : "border-zinc-600 hover:border-blue-500 hover:bg-zinc-800/50"}
          ${uploading ? "opacity-60 cursor-not-allowed" : ""}
        `}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center gap-2 text-gray-400">
            <Loader2 size={36} className="animate-spin text-blue-500" />
            <p className="font-medium">Uploading…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-400">
            <Upload size={36} className={isDragActive ? "text-blue-400" : "text-gray-500"} />
            <p className="font-medium text-gray-300">
              {isDragActive ? "Drop invoices here" : "Drag & drop invoices, or click to browse"}
            </p>
            <p className="text-sm text-gray-500">Supports .txt, .pdf, .json · Single or batch upload</p>
          </div>
        )}
      </div>
      {error && (
        <p className="mt-2 text-sm text-red-400 bg-red-900/40 border border-red-700/50 rounded px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
