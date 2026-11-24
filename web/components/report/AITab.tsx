"use client";

import React, { useState } from "react";
import { Cpu, AlertCircle, Info, Sparkles, Filter } from "lucide-react";

interface AITabProps {
  report: any;
}

export default function AITab({ report }: AITabProps) {
  const ai = report?.ai_detection || {};
  const chunks = ai.chunks || [];
  const [selectedChunkIdx, setSelectedChunkIdx] = useState(0);

  const isTooShort = ai.status === "TOO_SHORT";
  const currentChunk = chunks[selectedChunkIdx] || chunks[0] || null;

  // GLTR distribution statistics
  const gltrSummary = currentChunk?.gltr_summary || ai.gltr_summary || {
    top10_pct: 0.65,
    top100_pct: 0.22,
    top1000_pct: 0.08,
    rest_pct: 0.05,
  };

  const tokens = currentChunk?.gltr_tokens || [];

  return (
    <div className="space-y-6">
      {/* Short Essay Guardrail Alert */}
      {isTooShort && (
        <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg shadow-sm">
          <div className="flex items-start">
            <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="ml-3">
              <h3 className="text-sm font-semibold text-amber-800">
                Minimum Length Guardrail Triggered (&lt; 150 Words)
              </h3>
              <p className="mt-1 text-xs text-amber-700 leading-relaxed">
                This document contains fewer than 150 words. Likelihood-curvature and log-rank statistics are unreliable on short samples. The AI probability score is suppressed to prevent false accusations.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Top AI Score & GLTR Distribution Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-900">
                Multi-Signal AI Writing Analysis
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Ensemble calibration of Fast-DetectGPT curvature + GLTR predictive token rankings
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <div className="text-right">
              <span className="text-xs text-slate-400 block font-medium">Confidence Score</span>
              <span className="text-2xl font-black text-indigo-600">
                {ai.document_ai_probability !== undefined
                  ? `${Math.round(ai.document_ai_probability * 100)}%`
                  : "0%"}
              </span>
            </div>
          </div>
        </div>

        {/* GLTR Legend & Distribution Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              GLTR Token Predictive Rank Distribution
            </span>
            <span className="text-xs text-slate-400 font-medium">
              Higher green indicates predictable / AI-generated language
            </span>
          </div>

          {/* Color Bar */}
          <div className="w-full h-3 rounded-full flex overflow-hidden shadow-inner bg-slate-100">
            <div
              style={{ width: `${(gltrSummary.top10_pct || 0) * 100}%` }}
              className="bg-emerald-500 transition-all"
              title={`Top 10: ${(gltrSummary.top10_pct * 100).toFixed(1)}%`}
            />
            <div
              style={{ width: `${(gltrSummary.top100_pct || 0) * 100}%` }}
              className="bg-amber-400 transition-all"
              title={`Top 100: ${(gltrSummary.top100_pct * 100).toFixed(1)}%`}
            />
            <div
              style={{ width: `${(gltrSummary.top1000_pct || 0) * 100}%` }}
              className="bg-rose-500 transition-all"
              title={`Top 1000: ${(gltrSummary.top1000_pct * 100).toFixed(1)}%`}
            />
            <div
              style={{ width: `${(gltrSummary.rest_pct || 0) * 100}%` }}
              className="bg-purple-500 transition-all"
              title={`Rest: ${(gltrSummary.rest_pct * 100).toFixed(1)}%`}
            />
          </div>

          {/* Legend Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-xs">
            <div className="flex items-center space-x-2 p-2 rounded bg-emerald-50 border border-emerald-200">
              <span className="w-3 h-3 rounded-sm bg-emerald-500 flex-shrink-0" />
              <div>
                <span className="font-semibold text-emerald-950 block">Top 10</span>
                <span className="text-[11px] text-emerald-800">
                  {Math.round((gltrSummary.top10_pct || 0) * 100)}% of words
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-2 p-2 rounded bg-amber-50 border border-amber-200">
              <span className="w-3 h-3 rounded-sm bg-amber-400 flex-shrink-0" />
              <div>
                <span className="font-semibold text-amber-950 block">Top 100</span>
                <span className="text-[11px] text-amber-800">
                  {Math.round((gltrSummary.top100_pct || 0) * 100)}% of words
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-2 p-2 rounded bg-rose-50 border border-rose-200">
              <span className="w-3 h-3 rounded-sm bg-rose-500 flex-shrink-0" />
              <div>
                <span className="font-semibold text-rose-950 block">Top 1000</span>
                <span className="text-[11px] text-rose-800">
                  {Math.round((gltrSummary.top1000_pct || 0) * 100)}% of words
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-2 p-2 rounded bg-purple-50 border border-purple-200">
              <span className="w-3 h-3 rounded-sm bg-purple-500 flex-shrink-0" />
              <div>
                <span className="font-semibold text-purple-950 block">Rest (Rare)</span>
                <span className="text-[11px] text-purple-800">
                  {Math.round((gltrSummary.rest_pct || 0) * 100)}% of words
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chunk Selector (if document was split into multiple passages) */}
      {chunks.length > 1 && (
        <div className="flex items-center space-x-2 overflow-x-auto pb-1">
          <span className="text-xs font-bold text-slate-500 uppercase flex items-center space-x-1">
            <Filter className="w-3 h-3" />
            <span>Passages:</span>
          </span>
          {chunks.map((c: any, i: number) => (
            <button
              key={i}
              onClick={() => setSelectedChunkIdx(i)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition ${
                selectedChunkIdx === i
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
              }`}
            >
              Chunk {i + 1} ({Math.round((c.probability || 0) * 100)}% AI)
            </button>
          ))}
        </div>
      )}

      {/* Passage Forensic Word Highlighting View */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-indigo-500" />
            <h4 className="text-sm font-bold text-slate-800">
              GLTR Word-Level Forensic Token Map
            </h4>
          </div>
          <span className="text-xs text-slate-400">
            Hover over any word to inspect predictive rank
          </span>
        </div>

        {/* Text Container */}
        <div className="leading-relaxed text-sm text-slate-800 font-serif whitespace-pre-wrap p-4 bg-slate-50 rounded-lg border border-slate-200 max-h-[500px] overflow-y-auto">
          {tokens.length > 0 ? (
            tokens.map((t: any, idx: number) => {
              const rank = t.rank ?? 5;
              let colorClass = "bg-emerald-100 text-emerald-900 border-b-2 border-emerald-400";
              let label = "Top 10";

              if (t.category === "top100" || (rank > 10 && rank <= 100)) {
                colorClass = "bg-amber-100 text-amber-900 border-b-2 border-amber-400";
                label = "Top 100";
              } else if (t.category === "top1000" || (rank > 100 && rank <= 1000)) {
                colorClass = "bg-rose-100 text-rose-900 border-b-2 border-rose-400";
                label = "Top 1000";
              } else if (t.category === "rest" || rank > 1000) {
                colorClass = "bg-purple-100 text-purple-900 border-b-2 border-purple-400";
                label = "Rest (Rare)";
              }

              return (
                <span
                  key={idx}
                  title={`Word: "${t.token}" | Rank: ${rank} (${label})`}
                  className={`inline-block px-1 py-0.5 mx-0.5 rounded cursor-help transition hover:opacity-80 font-sans text-xs ${colorClass}`}
                >
                  {t.token}{" "}
                </span>
              );
            })
          ) : (
            <p className="text-slate-600 font-sans text-sm">
              {currentChunk?.text || report?.metadata?.text_preview || "No passage text available for rendering."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
