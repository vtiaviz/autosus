'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface Usuario {
  nome: string;
  email: string;
  perfil: string;
}

// Menu sugerido pelo Victor; "Sair" fica no fim, como no H-SUS
const MENU = [
  { href: '/', icone: 'dashboard', titulo: 'Dashboard', sub: 'Atualizações, processamentos e competências' },
  { href: '/atualizacoes', icone: 'cloud_download', titulo: 'Atualizações', sub: 'Arquivos e programas por competência' },
  { href: '/processamento', icone: 'memory', titulo: 'Processamento AIH', sub: 'Servidor, sistemas do SUS e envio' },
];

function saudacao(h = new Date().getHours()) {
  return h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite';
}

function Relogio() {
  const [agora, setAgora] = useState<Date | null>(null);
  useEffect(() => {
    setAgora(new Date());
    const t = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!agora) return null;
  return (
    <div className="navbar-clock" title="Data e hora atual">
      <span className="material-symbols-outlined">schedule</span>
      <span>{agora.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })}</span>
      <span className="clock-sep" />
      <span>{agora.toLocaleTimeString('pt-BR')}</span>
    </div>
  );
}

export default function Painel({ children }: { children: React.ReactNode }) {
  const caminho = usePathname();
  const router = useRouter();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [menuPerfil, setMenuPerfil] = useState(false);
  const [menuCelular, setMenuCelular] = useState(false);

  useEffect(() => {
    api<Usuario>('/auth/eu').then(setUsuario).catch(() => undefined);
  }, []);
  useEffect(() => setMenuCelular(false), [caminho]);

  const atual = MENU.find((m) => (m.href === '/' ? caminho === '/' : caminho.startsWith(m.href))) ?? MENU[0];

  async function sair() {
    await api('/auth/sair', { method: 'POST' }).catch(() => undefined);
    router.replace('/login');
  }

  return (
    <div className="container-scroller">
      <nav className="navbar default-layout col-lg-12 col-12 p-0 fixed-top d-flex align-items-top flex-row">
        <div className="text-center navbar-brand-wrapper d-flex align-items-center justify-content-start">
          <div className="me-3">
            <button
              className="navbar-toggler navbar-toggler align-self-center"
              type="button"
              aria-label="Recolher menu"
              onClick={() => document.body.classList.toggle('sidebar-icon-only')}
            >
              <i className="material-symbols-outlined menu-icon">menu</i>
            </button>
          </div>
          <div>
            <Link className="navbar-brand brand-logo" href="/">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/hsus/images/logo.png" alt="AutoSUS" />
            </Link>
            <Link className="navbar-brand brand-logo-mini" href="/">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/hsus/images/logo-mini.png" alt="AutoSUS" />
            </Link>
          </div>
        </div>
        <div className="navbar-menu-wrapper d-flex align-items-top">
          <ul className="navbar-nav">
            <li className="nav-item fw-semibold d-none d-md-block ms-0">
              <h2 className="welcome-text mb-3">
                {saudacao()}, <span className="text-black fw-bold">{usuario?.nome.split(' ')[0] ?? ''}</span>
              </h2>
              <h5 className="welcome-sub-text">{atual.sub}</h5>
            </li>
          </ul>
          <ul className="navbar-nav ms-auto">
            <li className="nav-item d-none d-lg-block">
              <Relogio />
            </li>
            <li className="nav-item dropdown d-none d-lg-block user-dropdown">
              <a
                className="nav-link"
                href="#"
                aria-expanded={menuPerfil}
                onClick={(e) => {
                  e.preventDefault();
                  setMenuPerfil(!menuPerfil);
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img className="img-xs rounded-circle" src="/hsus/images/person.svg" alt="Perfil" />
              </a>
              <div
                className={`dropdown-menu dropdown-menu-right navbar-dropdown${menuPerfil ? ' show' : ''}`}
                style={menuPerfil ? { right: 0, left: 'auto' } : undefined}
              >
                <div className="dropdown-header text-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img className="img-md rounded-circle" src="/hsus/images/person.svg" alt="Perfil" />
                  <p className="mb-1 mt-3 fw-semibold">{usuario?.nome}</p>
                  <p className="fw-light text-muted mb-0">{usuario?.email}</p>
                </div>
                <a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); void sair(); }}>
                  <i className="material-symbols-outlined menu-icon p-2">power_settings_new</i>Sair
                </a>
              </div>
            </li>
          </ul>
          <button
            className="navbar-toggler navbar-toggler-right d-lg-none align-self-center"
            type="button"
            aria-label="Abrir menu"
            onClick={() => setMenuCelular(!menuCelular)}
          >
            <i className="material-symbols-outlined">menu</i>
          </button>
        </div>
      </nav>

      <div className="container-fluid page-body-wrapper">
        <nav className={`sidebar sidebar-offcanvas${menuCelular ? ' active' : ''}`} id="sidebar">
          <ul className="nav">
            <li className="nav-item nav-category pt-0">AutoSUS</li>
            {MENU.map((m) => (
              <li key={m.href} className={`nav-item${m === atual ? ' active' : ''}`}>
                <Link className="nav-link" href={m.href}>
                  <i className="material-symbols-outlined menu-icon">{m.icone}</i>
                  <span className="menu-title">{m.titulo}</span>
                </Link>
              </li>
            ))}
            <li className="nav-item nav-category pt-2">Conta</li>
            <li className="nav-item">
              <a className="nav-link" href="#" onClick={(e) => { e.preventDefault(); void sair(); }}>
                <i className="material-symbols-outlined menu-icon">logout</i>
                <span className="menu-title">Sair</span>
              </a>
            </li>
          </ul>
        </nav>

        <div className="main-panel">
          <div className="content-wrapper">
            <div className="page-wrapper">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
