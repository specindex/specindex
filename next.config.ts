import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  // Default is 60s. GitHub Actions' shared runners are slower/more
  // contended than local hardware, and at 27K+ project pages some
  // individual page fetches were exceeding 60s there (though not
  // locally), failing the build after 3 retries.
  staticPageGenerationTimeout: 180,
};

export default nextConfig;
