"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Upload,
  Search,
  Filter,
  CheckCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
  Plus,
  RefreshCw,
  Cpu,
  Copy,
  ShieldAlert,
} from "lucide-react";
import { getAssignments, getToken } from "../../lib/api";

interface SubmissionRow {
  id: string;
  studentName: string;
  filename: string;
  submittedAt: string;
  aiPercent: number;
  aiStatus: string;
  similarityPercent: number;
  flagsCount: number;
  status: "queued" | "processing" | "done" | "failed";
}

const DEMO_SUBMISSIONS: SubmissionRow[] = [
  {
    id: "sub-human-01",
    studentName: "Emily Davis",
    filename: "Philosophy_of_Ethics_Final.docx",
    submittedAt: "Today, 10:14 AM",
    aiPercent: 4,
    aiStatus: "LIKELY HUMAN",
    similarityPercent: 3,
    flagsCount: 0,
    status: "done",
  },
  {
    id: "sub-ai-02",
    studentName: "Marcus Vance",
    filename: "AI_and_Future_Society.pdf",
    submittedAt: "Today, 09:42 AM",
    aiPercent: 96,
    aiStatus: "SUSPECTED AI",
    similarityPercent: 5,
    flagsCount: 0,
    status: "done",
  },
  {
    id: "sub-plag-03",
    studentName: "Chloe Zhao",
    filename: "Macroeconomics_Term_Paper.docx",
    submittedAt: "Yesterday, 4:20 PM",
    aiPercent: 12,
    aiStatus: "LIKELY HUMAN",
    similarityPercent: 68,
    flagsCount: 0,
    status: "done",
  },
  {
    id: "sub-tamper-04",
    studentName: "Julian Reed",
    filename: "World_History_Essay_Revised.docx",
    submittedAt: "Yesterday, 2:15 PM",
    aiPercent: 88,
    aiStatus: "SUSPECTED AI",
    similarityPercent: 24,
    flagsCount: 4,
    status: "done",
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<SubmissionRow[]>(DEMO_SUBMISSIONS);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check auth or fetch real data
    const token = getToken();
    if (!token) {
      router.push("/login");
    }
  }, [router]);

  const filtered = submissions.filter(
    (s) =>
      s.studentName.toLowerCase().includes(search.toLowerCase()) ||
      s.filename.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Instructor Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Overview of student submissions, originality scores, and evasion flags
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/upload"
            className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm shadow transition"
          >
            <Upload className="w-4 h-4" />
            <span>Upload New Essay</span>
          </Link>
        </div>
      </div>

      {/* Top Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase block">Submissions</span>
          <span className="text-2xl font-black text-slate-900 mt-1 block">{submissions.length}</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 uppercase">
            <Cpu className="w-3.5 h-3.5 text-indigo-600" />
            <span>Avg AI Probability</span>
          </div>
          <span className="text-2xl font-black text-indigo-600 mt-1 block">50%</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 uppercase">
            <Copy className="w-3.5 h-3.5 text-blue-600" />
            <span>Avg Similarity</span>
          </div>
          <span className="text-2xl font-black text-blue-600 mt-1 block">25%</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 uppercase">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
            <span>Tamper Alterations</span>
          </div>
          <span className="text-2xl font-black text-rose-600 mt-1 block">4</span>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search by student name or filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="text-xs text-slate-500 font-medium">
          Showing {filtered.length} of {submissions.length} essays
        </div>
      </div>

      {/* Submissions Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Student &amp; Document</th>
                <th className="py-3 px-4">Submission Date</th>
                <th className="py-3 px-4 text-center">AI Probability</th>
                <th className="py-3 px-4 text-center">Similarity</th>
                <th className="py-3 px-4 text-center">Tamper Flags</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filtered.map((sub) => {
                const isHuman = sub.aiPercent <= 30;
                const isAI = sub.aiPercent >= 70;

                return (
                  <tr key={sub.id} className="hover:bg-slate-50 transition">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900">{sub.studentName}</div>
                      <div className="text-xs text-slate-500 flex items-center space-x-1 mt-0.5">
                        <FileText className="w-3 h-3 text-slate-400" />
                        <span>{sub.filename}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-xs text-slate-500">
                      {sub.submittedAt}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold ${
                          isHuman
                            ? "bg-emerald-100 text-emerald-800"
                            : isAI
                            ? "bg-rose-100 text-rose-800"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {sub.aiPercent}%
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold ${
                          sub.similarityPercent > 20
                            ? "bg-rose-100 text-rose-800"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {sub.similarityPercent}%
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      {sub.flagsCount > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-700 border border-rose-200">
                          {sub.flagsCount} Flags
                        </span>
                      ) : (
                        <span className="text-xs text-emerald-600 font-semibold">&bull; Clean</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Done
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/report/${sub.id}`}
                        className="inline-flex items-center space-x-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-md transition"
                      >
                        <span>View Report</span>
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
