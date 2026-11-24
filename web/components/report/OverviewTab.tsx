"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, ShieldAlert, FileText, Cpu, Copy } from "lucide-react";

interface OverviewTabProps {
  report: any;
}

export default function OverviewTab({ report }: OverviewTabProps) {
  const metadata = report?.metadata || {};
  const integrity = report?.integrity || { flags: [], is_clean: true };
  const ai = report?.ai_detection || {};
  const similarity = report?.similarity || {};
  const summary = report?.summary || {};

  const aiPercent = summary.ai_probability_pct ?? (ai.document_ai_probability ? Math.round(ai.document_ai_probability * 100) : 0);
  const simPercent = summary.similarity_pct ?? (similarity.overall_similarity ? Math.round(similarity.overall_similarity * 100) : 0);
  const flagsCount = summary.flag_count ?? integrity.flag_count ?? (integrity.flags?.length || 0);

  const aiStatus = summary.ai_status || (ai.status === "TOO_SHORT" ? "TOO SHORT" : aiPercent >= 70 ? "SUSPECTED AI" : aiPercent <= 30 ? "LIKELY HUMAN" : "UNCLEAR");

  return (
    <div className="space-y-6">
      {/* Ethical Disclaimer Alert */}
      <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg shadow-sm">
        <div className="flex items-start">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="ml-3">
            <h3 className="text-sm font-semibold text-amber-800">
              Important: Statistical Estimate Only &bull; Not Definitive Proof
            </h3>
            <p className="mt-1 text-xs text-amber-700 leading-relaxed">
              AI detection scores and similarity ratios are statistical indicators calibrated for low false-positive rates (&le; 1&ndash;2%), but they should <strong>never</strong> be used as the sole determinant for disciplinary action or academic misconduct claims. Instructors must inspect raw matched passages, context, and interview the student before drawing conclusions.
            </p>
          </div>
        </div>
      </div>

      {/* Top 3 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: AI Writing */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-sm">
              <Cpu className="w-4 h-4 text-indigo-600" />
              <span>AI Writing Probability</span>
            </div>
            <span
              className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                aiStatus === "LIKELY HUMAN"
                  ? "bg-emerald-100 text-emerald-800"
                  : aiStatus === "SUSPECTED AI"
                  ? "bg-rose-100 text-rose-800"
                  : "bg-amber-100 text-amber-800"
              }`}
            >
              {aiStatus}
            </span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-extrabold text-slate-900">{aiPercent}%</span>
            <span className="text-xs text-slate-500 font-medium">calibrated score</span>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>Guardrail Status:</span>
              <span className="font-semibold text-slate-800">{ai.status || "DONE"}</span>
            </div>
            <div className="flex justify-between">
              <span>Chunks Analyzed:</span>
              <span className="font-semibold text-slate-800">{ai.chunks_analyzed ?? 1}</span>
            </div>
            <div className="flex justify-between">
              <span>Fast-Detect GPT Signal:</span>
              <span className="font-semibold text-slate-800">
                {ai.primary_score !== undefined ? `${(ai.primary_score * 100).toFixed(1)}%` : "N/A"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Similarity Index */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-sm">
              <Copy className="w-4 h-4 text-blue-600" />
              <span>Similarity Index</span>
            </div>
            <span
              className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                simPercent > 20 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {simPercent > 20 ? "MATCHES FOUND" : "LOW OVERLAP"}
            </span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-extrabold text-slate-900">{simPercent}%</span>
            <span className="text-xs text-slate-500 font-medium">total overlap</span>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>Exact Copying (Winnow):</span>
              <span className="font-semibold text-slate-800">
                {similarity.exact_similarity !== undefined
                  ? `${(similarity.exact_similarity * 100).toFixed(1)}%`
                  : "0.0%"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Semantic Paraphrase:</span>
              <span className="font-semibold text-slate-800">
                {similarity.semantic_similarity !== undefined
                  ? `${(similarity.semantic_similarity * 100).toFixed(1)}%`
                  : "0.0%"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Matched Sources:</span>
              <span className="font-semibold text-slate-800">
                {similarity.matched_sources?.length || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Tamper & Integrity */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-sm">
              <ShieldAlert className="w-4 h-4 text-rose-600" />
              <span>Integrity &amp; Evasion</span>
            </div>
            <span
              className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                flagsCount > 0 ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {flagsCount > 0 ? `${flagsCount} RED FLAGS` : "VERIFIED CLEAN"}
            </span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className={`text-4xl font-extrabold ${flagsCount > 0 ? "text-rose-600" : "text-emerald-600"}`}>
              {flagsCount}
            </span>
            <span className="text-xs text-slate-500 font-medium">anomalies detected</span>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>Document Cleanliness:</span>
              <span className="font-semibold text-slate-800">
                {integrity.is_clean ? "100% Clean" : "Tamper Alterations Found"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Sanitization Applied:</span>
              <span className="font-semibold text-slate-800">
                {integrity.sanitized ? "Yes (Safe Text Extracted)" : "None"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Homoglyph Substitutions:</span>
              <span className="font-semibold text-slate-800">
                {integrity.flags?.filter((f: any) => f.flag_type?.includes("HOMOGLYPH")).length || 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Document Overview Metadata */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center space-x-2">
          <FileText className="w-4 h-4 text-indigo-600" />
          <span>Document &amp; Ingestion Profile</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500 block">Clean Word Count</span>
            <span className="text-base font-bold text-slate-900 mt-0.5 block">
              {metadata.clean_word_count || 0}
            </span>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500 block">Raw Word Count</span>
            <span className="text-base font-bold text-slate-900 mt-0.5 block">
              {metadata.raw_word_count || 0}
            </span>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500 block">Parser Confidence</span>
            <span className="text-base font-bold text-slate-900 mt-0.5 block">
              {metadata.parse_confidence ? `${Math.round(metadata.parse_confidence * 100)}%` : "100%"}
            </span>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500 block">Detected Language</span>
            <span className="text-base font-bold text-slate-900 mt-0.5 block">
              {metadata.detected_language ? metadata.detected_language.toUpperCase() : "EN"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
