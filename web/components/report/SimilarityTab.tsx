"use client";

import React, { useState } from "react";
import { CheckCircle2, Copy, BookOpen, ExternalLink, ArrowRight } from "lucide-react";

interface SimilarityTabProps {
  report: any;
}

export default function SimilarityTab({ report }: SimilarityTabProps) {
  const similarity = report?.similarity || {};
  const matches = similarity.matches || similarity.matched_sources || [];
  const [selectedMatchIdx, setSelectedMatchIdx] = useState<number>(0);

  const overallPct = Math.round((similarity.overall_similarity || 0) * 100);
  const exactPct = Math.round((similarity.exact_similarity || 0) * 100);
  const semanticPct = Math.round((similarity.semantic_similarity || 0) * 100);

  if (matches.length === 0 || overallPct === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
        <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold text-slate-900">Originality Verified &bull; 0% Archive Overlap</h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
          No matching word sequences, paraphrased passages, or cross-student copy patterns were found in the institutional repository.
        </p>
      </div>
    );
  }

  const activeMatch = matches[selectedMatchIdx] || matches[0];

  return (
    <div className="space-y-6">
      {/* Overview Metric Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Copy className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">
              Dolos-Style Dual Passage Comparison
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Synchronized side-by-side view showing exact n-gram winnowing and semantic paraphrase matches
          </p>
        </div>

        <div className="flex items-center space-x-6 text-sm">
          <div>
            <span className="text-slate-400 block text-xs">Total Overlap</span>
            <span className="text-2xl font-black text-blue-600">{overallPct}%</span>
          </div>
          <div className="border-l border-slate-200 pl-4">
            <span className="text-slate-400 block text-xs">Exact Matches</span>
            <span className="text-lg font-bold text-slate-800">{exactPct}%</span>
          </div>
          <div className="border-l border-slate-200 pl-4">
            <span className="text-slate-400 block text-xs">Paraphrased</span>
            <span className="text-lg font-bold text-slate-800">{semanticPct}%</span>
          </div>
        </div>
      </div>

      {/* Match Source Selector Pills */}
      <div>
        <span className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-2">
          Matched Archive Sources ({matches.length})
        </span>
        <div className="flex items-center space-x-2 overflow-x-auto pb-2">
          {matches.map((m: any, idx: number) => {
            const isSelected = selectedMatchIdx === idx;
            const isExact = m.match_type === "exact";
            const scorePct = Math.round((m.similarity || 0.85) * 100);

            return (
              <button
                key={idx}
                onClick={() => setSelectedMatchIdx(idx)}
                className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2 flex-shrink-0 transition ${
                  isSelected
                    ? "bg-blue-600 text-white shadow"
                    : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span>{m.source_title || m.source_id || `Source #${idx + 1}`}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    isSelected
                      ? "bg-blue-700 text-white"
                      : isExact
                      ? "bg-rose-100 text-rose-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {scorePct}% {isExact ? "Exact" : "Paraphrase"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Side-by-Side Dual Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Pane: Student Submission */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Student Submitted Text
              </h4>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              Char {activeMatch?.student_span?.start ?? 0} &ndash; {activeMatch?.student_span?.end ?? 100}
            </span>
          </div>

          <div className="p-5 flex-1 bg-white text-sm leading-relaxed text-slate-800 overflow-y-auto max-h-[420px]">
            <div className="p-3 bg-blue-50 border-l-4 border-blue-600 rounded-r text-blue-950 font-serif whitespace-pre-wrap">
              {activeMatch?.student_span?.text ||
                activeMatch?.student_text ||
                activeMatch?.snippet ||
                "Selected matching passage from student text is highlighted here."}
            </div>
          </div>
        </div>

        {/* Right Pane: Matched Source Document */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-slate-600" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 truncate max-w-[200px]">
                {activeMatch?.source_title || activeMatch?.source_id || "Archive Reference"}
              </h4>
            </div>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
              {activeMatch?.match_type === "exact" ? "Exact Fingerprint Match" : "Semantic Paraphrase"}
            </span>
          </div>

          <div className="p-5 flex-1 bg-white text-sm leading-relaxed text-slate-800 overflow-y-auto max-h-[420px]">
            <div className="p-3 bg-slate-50 border-l-4 border-slate-400 rounded-r text-slate-900 font-serif whitespace-pre-wrap">
              {activeMatch?.source_span?.text ||
                activeMatch?.source_text ||
                "Corresponding matched passage from institutional archive or student repository."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
