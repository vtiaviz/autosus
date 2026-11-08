'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { api, dataHoraBR, rotuloCompetencia, tamanho } from '@/lib/api';
import { Atualizacoes, Competencia, ItemAtualizacao, rotuloItem } from '@/lib/tipos';

// Como na sugestão do Victor: o BDSIA aparece entre os programas (é um instalador .exe)
const NA_LISTA_DE_PROGRAMAS = new Set(['BDSIA']);

function competenciaPadrao() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function Tabela({ titulo, icone, itens }: { titulo: string; icone: string; itens: ItemAtualizacao[] }) {
  const pendentes = itens.filter((i) => rotuloItem(i.situacao)[1] !== 'ok').length;
  return (
    <div className="cad-card">
      <div className="cad-card-head">
        <h5><span className="material-symbols-outlined">{icone}</span> {titulo}</h5>
        <span className="count-badge">{itens.length - pendentes} de {itens.length} baixados</span>
      </div>
      <div className="tabela-rolagem">
        <table className="sus-table">
          <thead>
            <tr><th>Item</th><th>Arquivo</th><th>Situação</th><th>Tamanho</th></tr>
          </thead>
          <tbody>
            {itens.map((i) => {
              const [rotulo, classe] = rotuloItem(i.situacao);
              return (
                <tr key={i.nome}>
                  <td className="cod">{i.nome}</td>
                  <td>
                    {i.arquivo || '-'}
                    {i.revisaoNova && <span className="situacao aberta" style={{ marginLeft: 6 }}>nova</span>}
                    {i.detalhe && <div className="texto-suave">{i.detalhe}</div>}
                  </td>
                  <td><span className={`situacao ${classe}`}>{rotulo}</span></td>
                  <td className="num">{tamanho(i.tamanho)}</td>
                </tr>
              );
            })}
            {itens.length === 0 && (
              <tr><td colSpan={4} className="texto-suave">Nenhuma verificação desta competência ainda.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Pagina() {
  const params = useSearchParams();
  const [competencias, setCompetencias] = useState<Competencia[]>([]);
  const [aaaamm, setAaaamm] = useState(params.get('competencia') ?? competenciaPadrao());
  const [dados, setDados] = useState<Atualizacoes | null>(null);
  const [erro, setErro] = useState('');
  const [verLog, setVerLog] = useState(false);

  const carregar = useCallback(
    () => api<Atualizacoes>(`/atualizacoes/${aaaamm}`).then(setDados).catch((e: Error) => setErro(e.message)),
    [aaaamm],
  );

  useEffect(() => {
    api<Competencia[]>('/competencias').then(setCompetencias).catch(() => undefined);
  }, []);
  useEffect(() => {
    setDados(null);
    setErro('');
    void carregar();
  }, [carregar]);

  const rodando = !!dados?.execucao?.emAndamento;
  useEffect(() => {
    if (!rodando) return;
    const t = setInterval(() => void carregar(), 5000);
    return () => clearInterval(t);
  }, [rodando, carregar]);

  async function verificar() {
    setErro('');
    try {
      await api(`/atualizacoes/${aaaamm}/verificar`, { method: 'POST' });
      await carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  // até 12 competências para trás, mais as do cronograma
  const opcoes = Array.from(
    new Set([competenciaPadrao(), aaaamm, ...competencias.map((c) => c.aaaamm)]),
  )
    .filter((c) => c <= competenciaPadrao())
    .sort()
    .reverse()
    .slice(0, 12);

  const todos = [...(dados?.arquivos ?? []), ...(dados?.programas ?? [])];
  const arquivos = todos.filter((i) => i.tipo === 'arquivo' && !NA_LISTA_DE_PROGRAMAS.has(i.nome));
  const programas = todos.filter((i) => i.tipo === 'programa' || NA_LISTA_DE_PROGRAMAS.has(i.nome));
  const exec = dados?.execucao;

  return (
    <>
      <div className="pagina-cabecalho">
        <div>
          <h3>Atualizações da competência {rotuloCompetencia(aaaamm)}</h3>
          <p>
            Última verificação: {dataHoraBR(dados?.verificadoEm as string | null)}
            {dados?.pasta && <> · pasta {dados.pasta}</>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select className="seletor-competencia" value={aaaamm} onChange={(e) => setAaaamm(e.target.value)} aria-label="Competência">
            {opcoes.map((c) => <option key={c} value={c}>{rotuloCompetencia(c)}</option>)}
          </select>
          <button className="btn-new" onClick={verificar} disabled={rodando}>
            <span className={`material-symbols-outlined${rodando ? ' spin' : ''}`}>{rodando ? 'progress_activity' : 'sync'}</span>
            {rodando ? 'Verificando...' : 'Verificar agora'}
          </button>
        </div>
      </div>

      {erro && <div className="aviso-erro">{erro}</div>}

      <div className="grade-2" style={{ marginTop: 0 }}>
        <Tabela titulo="Arquivos" icone="folder_zip" itens={arquivos} />
        <Tabela titulo="Programas" icone="install_desktop" itens={programas} />
      </div>

      {exec && (
        <div className="cad-card" style={{ marginTop: 20 }}>
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">terminal</span> Última verificação pelo AutoSUS</h5>
            <span className="texto-suave">
              {dataHoraBR(exec.inicio)}
              {exec.emAndamento ? ' · em andamento' : exec.codigo === 0 ? ' · concluída' : ` · terminou com código ${exec.codigo}`}
              {' · '}
              <a href="#" onClick={(e) => { e.preventDefault(); setVerLog(!verLog); }}>{verLog ? 'ocultar saída' : 'ver saída'}</a>
            </span>
          </div>
          {verLog && <div className="cad-card-body" style={{ paddingBottom: 18 }}><pre className="log-saida">{exec.saida || '(sem saída ainda)'}</pre></div>}
        </div>
      )}
    </>
  );
}

export default function AtualizacoesPagina() {
  return (
    <Suspense>
      <Pagina />
    </Suspense>
  );
}
