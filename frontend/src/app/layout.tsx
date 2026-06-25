/**
 * Root layout.
 *
 * In the Next.js App Router, `layout.tsx` wraps every page. It renders the
 * <html>/<body> shell and shared chrome (here, a simple nav). Page content is
 * injected as `children`.
 */
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Document Intelligence Assistant",
  description: "AI-powered document processing platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <nav>
          <Link href="/">Home</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/documents">Documents</Link>
          <Link href="/chat">Chat</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
