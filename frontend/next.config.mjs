/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  },
  webpack: (config) => {
    // wagmi/viem pull in optional native deps that aren't needed in the browser
    config.externals.push("pino-pretty", "lokijs", "encoding");
    // MetaMask SDK optionally imports a React Native storage module; stub it on web.
    config.resolve = config.resolve || {};
    config.resolve.fallback = {
      ...(config.resolve.fallback || {}),
      "@react-native-async-storage/async-storage": false,
    };
    return config;
  },
};

export default nextConfig;
