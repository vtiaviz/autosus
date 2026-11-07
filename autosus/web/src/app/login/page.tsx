'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';
import { api, ErroApi } from '@/lib/api';
import './login.css';

const LEMBRAR = 'autosus:emailLembrado';
const FUNDOS = Array.from(
  { length: 12 },
  (_, i) => `/hsus/images/login/fundo-${String(i + 1).padStart(2, '0')}.jpg`,
);
const POSICAO: Record<string, string> = { 'fundo-04.jpg': '75% center', 'fundo-11.jpg': '70% center' };

// mesma regra do H-SUS: uma foto por hora, andando 5 fotos por dia
function fundoDaHora(d = new Date()) {
  const dia = Math.floor((d.getTime() - new Date(d.getFullYear(), 0, 1).getTime()) / 86400000);
  return FUNDOS[(d.getHours() + dia * 5) % FUNDOS.length];
}

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [mostrar, setMostrar] = useState(false);
  const [lembrar, setLembrar] = useState(true);
  const [erro, setErro] = useState<{ msg: string; campos: string[] } | null>(null);
  const [entrando, setEntrando] = useState(false);
  const [fundo, setFundo] = useState<string | null>(null);

  useEffect(() => {
    try {
      setEmail(localStorage.getItem(LEMBRAR) ?? '');
    } catch {
      /* sem armazenamento local */
    }
    const img = new Image();
    const src = fundoDaHora();
    img.onload = () => setFundo(src);
    img.src = src;
  }, []);

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    const vazios = [!email.trim() && 'email', !senha && 'senha'].filter(Boolean) as string[];
    if (vazios.length) return setErro({ msg: 'Informe e-mail e senha.', campos: vazios });
    setEntrando(true);
    try {
      await api('/auth/entrar', { method: 'POST', body: JSON.stringify({ email: email.trim(), senha }) });
      try {
        if (lembrar) localStorage.setItem(LEMBRAR, email.trim());
        else localStorage.removeItem(LEMBRAR);
      } catch {
        /* segue sem lembrar */
      }
      router.replace('/');
    } catch (err) {
      setEntrando(false);
      const msg =
        err instanceof ErroApi && err.status === 401
          ? 'E-mail ou senha incorretos.'
          : `Não foi possível entrar: ${(err as Error).message}`;
      setErro({ msg, campos: ['email', 'senha'] });
    }
  }

  const avisar = (msg: string) => setErro({ msg, campos: [] });

  return (
    <div className="tela-login">
      <div className="bg" aria-hidden="true">
        <div
          className={`bg-foto${fundo ? ' ativa' : ''}`}
          style={fundo ? { backgroundImage: `url("${fundo}")`, backgroundPosition: POSICAO[fundo.split('/').pop()!] } : {}}
        />
      </div>

      <main className="login-card">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/hsus/images/logo.png" alt="H-SUS" />
        </div>
        <h1>AutoSUS</h1>
        <p className="subtitle">Acesse para acompanhar as atualizações e o processamento das AIHs do hospital.</p>

        <form onSubmit={entrar} noValidate>
          <div className={`field${erro?.campos.includes('email') ? ' error' : ''}`}>
            <label className="sr-only" htmlFor="email">E-mail</label>
            <input
              id="email"
              type="email"
              placeholder="E-mail"
              autoComplete="username"
              value={email}
              autoFocus
              onChange={(e) => {
                setEmail(e.target.value);
                setErro(null);
              }}
            />
            <span className="material-symbols-outlined field-icon" aria-hidden="true">person</span>
          </div>

          <div className={`field${erro?.campos.includes('senha') ? ' error' : ''}`}>
            <label className="sr-only" htmlFor="senha">Senha</label>
            <input
              id="senha"
              type={mostrar ? 'text' : 'password'}
              placeholder="Senha"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => {
                setSenha(e.target.value);
                setErro(null);
              }}
            />
            <button
              type="button"
              className="toggle-pass"
              aria-label={mostrar ? 'Ocultar senha' : 'Mostrar senha'}
              onClick={() => setMostrar(!mostrar)}
            >
              <span className="material-symbols-outlined">{mostrar ? 'visibility' : 'visibility_off'}</span>
            </button>
          </div>

          {erro && (
            <div className="login-error" role="alert">
              <span className="material-symbols-outlined">error</span>
              <span>{erro.msg}</span>
            </div>
          )}

          <div className="options">
            <label className="remember">
              <input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} /> Lembrar de mim
            </label>
            <button
              type="button"
              className="forgot"
              onClick={() => avisar('Para redefinir a senha, procure o administrador do sistema.')}
            >
              Esqueceu a senha?
            </button>
          </div>

          <button type="submit" className="btn-login" disabled={entrando}>
            {entrando ? (
              <>
                <span className="material-symbols-outlined spin">progress_activity</span> Entrando...
              </>
            ) : (
              'Entrar'
            )}
          </button>
        </form>
      </main>

      <p className="page-footer">Desenvolvido por Victor Aviz © 2026 - Todos os direitos reservados.</p>
    </div>
  );
}
