import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TopNav } from "@/components/TopNav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app"),
  title: {
    default: "VaniGuard — AI Voice Cloning Defense",
    template: "%s | VaniGuard",
  },
  description:
    "Real-time AI-generated voice detection for Hindi, Tamil, and Telugu. Powered by MobileNetV2 and Log-Mel Spectrograms.",
  keywords: [
    "AI voice detection",
    "voice cloning",
    "deepfake audio",
    "VaniGuard",
    "speech authentication",
    "Hindi Tamil Telugu",
  ],
  authors: [{ name: "VaniGuard Team" }],
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    url: "https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app",
    siteName: "VaniGuard",
    title: "VaniGuard — AI Voice Cloning Defense",
    description:
      "Real-time AI-generated voice detection. Upload audio to instantly detect cloned or synthetic voices.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "VaniGuard Dashboard" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "VaniGuard — AI Voice Cloning Defense",
    description: "Real-time AI-generated voice detection for South Asian languages.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen flex flex-col bg-[#090D16] text-slate-100 antialiased`}
      >
        <TopNav />
        <main className="flex-1 flex flex-col">{children}</main>
      </body>
    </html>
  );
}
