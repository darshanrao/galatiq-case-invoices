import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import Link from "next/link";

const geist = Geist({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Galatiq Invoice Dashboard",
  description: "AI-powered invoice processing pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geist.className} bg-zinc-900 min-h-screen text-gray-100`}>
        <Providers>
          <header className="bg-zinc-800/80 border-b border-zinc-700 sticky top-0 z-40 backdrop-blur-sm">
            <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-blue-400 font-black text-xl tracking-tight">Galatiq</span>
                <span className="text-gray-500 text-sm">Invoice AI</span>
              </div>
              <nav className="flex items-center gap-6 text-sm font-medium">
                <Link href="/" className="text-gray-300 hover:text-blue-400 transition-colors">
                  Dashboard
                </Link>
                <Link
                  href="/approval"
                  className="text-gray-300 hover:text-blue-400 transition-colors"
                >
                  Approval Queue
                </Link>
              </nav>
            </div>
          </header>
          <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
