import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import DemoTokenInjector from "./demo-injector";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    template: "%s — FixFlow",
    default: "FixFlow — Autonomous Self-Healing Codebase Platform",
  },
  description:
    "AI reliability layer that detects deployment failures, identifies root causes, proposes verified patches, and prepares recovery workflows.",
  keywords: ["DevOps", "AI", "self-healing", "deployment", "incident response", "GitHub", "Vercel"],
  authors: [{ name: "FixFlow" }],
  robots: "noindex, nofollow", // Private platform — no public indexing
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#000000",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="antialiased">
        <DemoTokenInjector />
        {children}
      </body>
    </html>
  );
}
