import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Originality & Integrity Platform",
  description: "Academic Integrity, AI Detection, Plagiarism Similarity & Evasion Tamper Analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased">
        <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/dashboard" className="flex items-center space-x-2">
                <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                  O
                </div>
                <div>
                  <span className="text-lg font-bold tracking-tight text-slate-900">
                    Originality<span className="text-indigo-600">Checker</span>
                  </span>
                  <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-xs font-medium rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    MVP
                  </span>
                </div>
              </Link>
            </div>

            <nav className="flex items-center space-x-4">
              <Link
                href="/dashboard"
                className="text-sm font-medium text-slate-600 hover:text-indigo-600 px-3 py-1.5 rounded-md hover:bg-slate-100 transition"
              >
                Dashboard
              </Link>
              <Link
                href="/upload"
                className="text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-3.5 py-1.5 rounded-md shadow-sm transition"
              >
                + Submit Essay
              </Link>
              <Link
                href="/login"
                className="text-sm font-medium text-slate-500 hover:text-slate-800 px-2 py-1.5 transition"
              >
                Account
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>

        <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
          <div className="max-w-7xl mx-auto px-4">
            <p className="font-medium text-slate-600">
              Originality &amp; Integrity Checker &bull; Multi-Signal AI Detection, Dolos Similarity &amp; Anti-Tamper Engine
            </p>
            <p className="mt-1 text-slate-400">
              Disclaimer: AI detection scores are probabilistic estimates and should never serve as the sole ground for disciplinary action.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
