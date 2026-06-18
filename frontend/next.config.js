/** @type {import('next').NextConfig} */
const isExport = process.env.NEXT_OUTPUT === 'export';

const nextConfig = {
  output: isExport ? 'export' : 'standalone',
  trailingSlash: isExport,
  ...(isExport ? {} : {
    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"}/api/:path*`,
        },
      ];
    },
  }),
};

module.exports = nextConfig;
