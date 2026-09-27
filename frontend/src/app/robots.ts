import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: "https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app/sitemap.xml",
  };
}
