"use client";

import React from "react";
import { CheckCircle2, AlertOctagon, Info, EyeOff, Shuffle, Terminal } from "lucide-react";

interface FlagsTabProps {
  report: any;
}

export default function FlagsTab({ report }: FlagsTabProps) {
  const integrity = report?.integrity || {};
  const flags = integrity.flags || [];

  if (flags.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
        <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold text-slate-900">Document Verified Clean</h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
          No white text, zero-width characters, homoglyph substitutions, or formatting-based evasion techniques were detected in this submission.
        </p>
      </div>
    );
  }

  // Group flags by type
  const hiddenCount = flags.filter((f: any) => f.flag_type?.includes("HIDDEN")).length;
  const homoglyphCount = flags.filter((f: any) => f.flag_type?.includes("HOMOGLYPH")).length;
  const zeroWidthCount = flags.filter((f: any) => f.flag_type?.includes("ZERO_WIDTH")).length;
  const otherCount = flags.length - (hiddenCount + homoglyphCount + zeroWidthCount);

  return (
    <div className="space-y-6">
      {/* Alert Banner */}
      <div className="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-lg shadow-sm">
        <div className="flex items-start">
          <AlertOctagon className="h-5 w-5 text-rose-600 mt-0.5 flex-shrink-0" />
          <div className="ml-3">
            <h3 className="text-sm font-semibold text-rose-800">
              Evasion &amp; Tampering Techniques Detected ({flags.length})
            </h3>
            <p className="mt-1 text-xs text-rose-700 leading-relaxed">
              The submission contains artificial alterations often used to deceive automated word counters or bypass AI classifiers. The pipeline automatically sanitized these characters to compute reliable AI and similarity metrics.
            </p>
          </div>
        </div>
      </div>

      {/* Summary Counts */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-600 mb-1">
            <EyeOff className="w-3.5 h-3.5 text-rose-500" />
            <span>Hidden Text</span>
          </div>
          <span className="text-2xl font-bold text-slate-900">{hiddenCount}</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-600 mb-1">
            <Shuffle className="w-3.5 h-3.5 text-amber-500" />
            <span>Homoglyphs</span>
          </div>
          <span className="text-2xl font-bold text-slate-900">{homoglyphCount}</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-600 mb-1">
            <Terminal className="w-3.5 h-3.5 text-indigo-500" />
            <span>Zero-Width Chars</span>
          </div>
          <span className="text-2xl font-bold text-slate-900">{zeroWidthCount}</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-600 mb-1">
            <Info className="w-3.5 h-3.5 text-slate-500" />
            <span>Other Anomalies</span>
          </div>
          <span className="text-2xl font-bold text-slate-900">{otherCount}</span>
        </div>
      </div>

      {/* Flags List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100 overflow-hidden">
        <div className="px-5 py-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Detected Anomaly Breakdown
          </h4>
          <span className="text-xs text-slate-500 font-medium">
            Total {flags.length} incidents
          </span>
        </div>

        {flags.map((flag: any, idx: number) => {
          const isCritical = flag.severity === "CRITICAL" || flag.flag_type?.includes("HIDDEN");
          return (
            <div key={idx} className="p-5 hover:bg-slate-50 transition">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        isCritical
                          ? "bg-rose-100 text-rose-800 border border-rose-300"
                          : "bg-amber-100 text-amber-800 border border-amber-300"
                      }`}
                    >
                      {flag.flag_type || "TAMPER_DETECTED"}
                    </span>
                    <span className="text-xs text-slate-500">
                      Offset: {flag.start_char ?? flag.offset ?? 0} - {flag.end_char ?? (flag.offset ? flag.offset + 10 : 0)}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-slate-800 pt-1">
                    {flag.details || flag.description || "Suspicious character manipulation detected."}
                  </p>
                </div>
                <span className="text-xs font-semibold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  {flag.severity || "HIGH"}
                </span>
              </div>

              {flag.snippet && (
                <div className="mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200 font-mono text-xs text-slate-700">
                  <span className="text-slate-400 select-none mr-2 font-sans font-semibold">
                    Snippet context:
                  </span>
                  <span className="border border-rose-500 bg-rose-50 text-rose-900 px-1.5 py-0.5 rounded">
                    {flag.snippet}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
