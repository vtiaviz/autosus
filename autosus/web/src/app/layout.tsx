import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AutoSUS',
  description: 'Gestão do processamento de AIHs do hospital',
  icons: { icon: '/hsus/images/favicon.svg', apple: '/hsus/images/apple-touch-icon.png' },
};

// Mesmo visual do H-SUS (Prototipo H-SUS): tema admin Bootstrap 5 + clinbot.css, DM Sans e Material Symbols
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-br">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap"
        />
        <link rel="stylesheet" href="/hsus/css/vendor.bundle.base.css" />
        <link rel="stylesheet" href="/hsus/css/style.css" />
        <link rel="stylesheet" href="/hsus/css/clinbot.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
