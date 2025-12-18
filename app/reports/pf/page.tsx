"use client";

import React, { useState } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

export default function ReportPFPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!file) {
      setError("Selecione um PDF primeiro.");
      return;
    }

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(
        `${BACKEND_URL}/reports/mind7-to-delta-html`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Erro ao gerar relatório.");
      }

      const html = await res.text();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch (err: any) {
      setError(err.message || "Erro inesperado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-zinc-100 flex flex-col items-center pt-10">
      <h1 className="text-2xl font-semibold mb-2">
        Relatório PF (Delta) – PDF MIND-7
      </h1>
      <p className="text-sm text-zinc-400 mb-6 max-w-xl text-center">
        Envie o PDF da consulta. O sistema converte para o padrão de relatório
        Delta Trace (sem INTERESSES) e abre em uma nova aba para impressão.
      </p>

      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md border border-zinc-800 rounded-xl p-4 flex flex-col gap-4 bg-slate-900"
      >
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="text-sm"
        />

        <button
          type="submit"
          disabled={loading}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-md py-2 text-sm font-medium"
        >
          {loading ? "Gerando relatório..." : "Gerar Relatório Delta"}
        </button>

        {error && (
          <p className="text-xs text-red-400 mt-2">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
