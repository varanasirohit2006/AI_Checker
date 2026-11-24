"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Users,
  Network,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  Filter,
  CheckCircle2,
  FileText,
  ShieldAlert,
} from "lucide-react";

interface ClusterNode {
  id: string;
  name: string;
  file: string;
  clusterId: number;
  aiPercent: number;
  similarityPercent: number;
}

interface ClusterGroup {
  id: number;
  name: string;
  risk: "HIGH" | "MEDIUM" | "LOW";
  avgOverlapPct: number;
  members: ClusterNode[];
  sharedSnippet: string;
}

const DEMO_CLUSTERS: ClusterGroup[] = [
  {
    id: 1,
    name: "Cluster #1: Macroeconomics Plagiarism Ring",
    risk: "HIGH",
    avgOverlapPct: 58,
    sharedSnippet:
      "The rapid deregulation of interbank overnight lending facilities precipitated systemic liquidity contraction across regional credit markets...",
    members: [
      {
        id: "sub-plag-01",
        name: "Chloe Zhao",
        file: "Macroeconomics_Term_Paper.docx",
        clusterId: 1,
        aiPercent: 12,
        similarityPercent: 68,
      },
      {
        id: "sub-plag-02",
        name: "Marcus Vance",
        file: "Econ_Paper_Final.pdf",
        clusterId: 1,
        aiPercent: 18,
        similarityPercent: 55,
      },
      {
        id: "sub-plag-03",
        name: "Alex Rivera",
        file: "Macro_Draft_v2.docx",
        clusterId: 1,
        aiPercent: 14,
        similarityPercent: 52,
      },
    ],
  },
  {
    id: 2,
    name: "Cluster #2: Lab Report Method Collision",
    risk: "MEDIUM",
    avgOverlapPct: 32,
    sharedSnippet:
      "Serial dilution of bacterial cultures was conducted in sterile phosphate-buffered saline (PBS) under laminar flow hood conditions...",
    members: [
      {
        id: "sub-lab-01",
        name: "Daniel Kim",
        file: "Bio_Lab4_Report.pdf",
        clusterId: 2,
        aiPercent: 6,
        similarityPercent: 34,
      },
      {
        id: "sub-lab-02",
        name: "Sarah Jenkins",
        file: "Microbiology_Lab4.docx",
        clusterId: 2,
        aiPercent: 8,
        similarityPercent: 30,
      },
    ],
  },
];

export default function AssignmentClusters() {
  const [clusters, setClusters] = useState<ClusterGroup[]>(DEMO_CLUSTERS);
  const [selectedClusterId, setSelectedClusterId] = useState<number>(1);
  const [selectedPair, setSelectedPair] = useState<[ClusterNode, ClusterNode] | null>(null);

  const activeCluster = clusters.find((c) => c.id === selectedClusterId) || clusters[0];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Network className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-black text-slate-900 tracking-tight">
              Dolos Assignment Overlap Clusters
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Cross-submission graph analysis detecting multi-student copy rings and collusion clusters
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
            {clusters.length} Collision Clusters Detected
          </span>
        </div>
      </div>

      {/* Cluster Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clusters.map((c) => {
          const isSelected = selectedClusterId === c.id;
          const isHigh = c.risk === "HIGH";

          return (
            <div
              key={c.id}
              onClick={() => {
                setSelectedClusterId(c.id);
                setSelectedPair(null);
              }}
              className={`p-5 rounded-xl border cursor-pointer transition ${
                isSelected
                  ? "bg-white border-indigo-600 shadow-md ring-2 ring-indigo-500/20"
                  : "bg-white border-slate-200 hover:border-slate-300 shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-slate-900">{c.name}</span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    isHigh ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {c.risk} COLLUSION RISK
                </span>
              </div>

              <div className="flex items-center space-x-4 text-xs text-slate-600 mb-3">
                <span className="flex items-center space-x-1">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  <strong>{c.members.length} Students</strong>
                </span>
                <span>&bull;</span>
                <span>Avg Overlap: <strong className="text-slate-900">{c.avgOverlapPct}%</strong></span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg text-xs font-serif text-slate-700 border border-slate-200 line-clamp-2">
                &ldquo;{c.sharedSnippet}&rdquo;
              </div>

              {/* Member pills */}
              <div className="flex flex-wrap gap-1.5 mt-3">
                {c.members.map((m) => (
                  <span
                    key={m.id}
                    className="text-[11px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-800 px-2 py-0.5 rounded transition"
                  >
                    {m.name} ({m.similarityPercent}%)
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Cluster Detail & Pairwise Visualizer */}
      {activeCluster && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{activeCluster.name}</h3>
              <p className="text-xs text-slate-500">
                Comparing overlapping passages across {activeCluster.members.length} submissions
              </p>
            </div>
            <span className="text-xs font-mono font-semibold text-rose-700 bg-rose-50 px-2.5 py-1 rounded border border-rose-200">
              Avg Mutual Similarity: {activeCluster.avgOverlapPct}%
            </span>
          </div>

          <div className="p-5 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Select Pairwise Comparison
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {activeCluster.members.map((m, idx) => {
                const nextMember = activeCluster.members[(idx + 1) % activeCluster.members.length];
                return (
                  <button
                    key={idx}
                    onClick={() => setSelectedPair([m, nextMember])}
                    className="p-3 text-left border border-slate-200 rounded-lg hover:border-indigo-500 hover:bg-indigo-50/50 transition flex items-center justify-between"
                  >
                    <div>
                      <div className="text-xs font-bold text-slate-900">{m.name}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5 flex items-center space-x-1">
                        <span>vs {nextMember.name}</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-400" />
                  </button>
                );
              })}
            </div>

            {/* Side-by-side Shared Passage Excerpt */}
            <div className="mt-4 pt-4 border-t border-slate-100">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Shared Cluster Fragment
              </h4>
              <div className="p-4 bg-rose-50 border-l-4 border-rose-600 rounded-r text-xs leading-relaxed font-serif text-rose-950 whitespace-pre-wrap">
                {activeCluster.sharedSnippet}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
