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
        <div className="site-shell">
          <nav className="top-nav" aria-label="Main navigation">
            <Link href="/">Home</Link>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/documents">Documents</Link>
            <Link href="/search">Search</Link>
            <Link href="/chat">Chat</Link>
          </nav>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
