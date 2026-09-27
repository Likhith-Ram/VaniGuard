import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Enable modern WebP/AVIF output for all images
    formats: ["image/avif", "image/webp"],
    // Compress images aggressively
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
    // Restrict to trusted domains (add more as needed)
    remotePatterns: [],
  },
  // Compress gzip for all JS/CSS/HTML outputs
  compress: true,
};

export default nextConfig;
