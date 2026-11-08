import type { NextConfig } from 'next';

// A API (NestJS) roda só em 127.0.0.1; o navegador fala com ela pelo próprio Next.js (/api/*),
// assim o cookie da sessão fica no mesmo endereço do site.
const API = process.env.AUTOSUS_API ?? 'http://127.0.0.1:3001';

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: '/api/:caminho*', destination: `${API}/api/:caminho*` }];
  },
};

export default nextConfig;
