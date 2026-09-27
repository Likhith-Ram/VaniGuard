import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app";
  const now = new Date("2026-09-27");
  return [
    { url: `${base}/`, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${base}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.5 },
    { url: `${base}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.5 },
  ];
}
