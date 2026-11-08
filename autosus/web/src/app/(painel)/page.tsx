'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, dataBR, rotuloCompetencia } from '@/lib/api';
import { Competencia, ROTULO_SITUACAO_COMPETENCIA } from '@/lib/tipos';

const SISTEMAS = ['SISAIH01', 'FPO', 'SIHD2', 'Transmissor'];

export default function Dashboard() {
  const [lista, setLista] = useState<Competencia[] | null>(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    api<Competencia[]>('/competencias').then(setLista).catch((e: Error) => setErro(e.message));
  }, []);

  const hoje = new Date().toISOString().slice(0, 10);
  const aberta = lista?.find((c) => c.situacao === 'aberta');
  const comItens = (lista ?? []).filter((c) => c.arquivos.baixados + c.arquivos.pendentes + c.programas.baixados + c.programas.pendentes > 0);
  // cronograma: da competência aberta (ou a mais recente encerrada) até as duas próximas
  const cronograma = (lista ?? [])
    .filter((c) => c.fechamento && c.fechamento >= hoje.slice(0, 8) + '01')
    .sort((a, b) => a.aaaamm.localeCompare(b.aaaamm))
    .slice(0, 4);
  const pendentes = aberta ? aberta.arquivos.pendentes + aberta.programas.pendentes : 0;

  return (
    <>
      {erro && <div className="aviso-erro">Não foi possível carregar: {erro}</div>}

      <div className="stats-strip">
        <div className="stat-card">
          <div className="stat-icon blue"><span className="material-symbols-outlined">calendar_month</span></div>
          <div className="stat-info"><p>Competência aberta</p><h4>{aberta ? rotuloCompetencia(aberta.aaaamm) : '-'}</h4></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green"><span className="material-symbols-outlined">event_available</span></div>
          <div className="stat-info"><p>Abertura</p><h4>{dataBR(aberta?.abertura)}</h4></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon red"><span className="material-symbols-outlined">event_busy</span></div>
          <div className="stat-info"><p>Fechamento (envio SIH)</p><h4>{dataBR(aberta?.fechamento)}</h4></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon yellow"><span className="material-symbols-outlined">pending_actions</span></div>
          <div className="stat-info"><p>Itens pendentes</p><h4>{aberta ? pendentes : '-'}</h4></div>
        </div>
      </div>

      <div className="grade-2">
        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">cloud_download</span> Atualizações por competência</h5>
            <Link className="btn-new" href="/atualizacoes"><span className="material-symbols-outlined">open_in_new</span> Ver</Link>
          </div>
          <div className="tabela-rolagem">
            <table className="sus-table">
              <thead>
                <tr><th>Competência</th><th>Arquivos baixados</th><th>Arquivos pendentes</th><th>Programas baixados</th><th>Programas pendentes</th></tr>
              </thead>
              <tbody>
                {comItens.slice(0, 6).map((c) => (
                  <tr key={c.aaaamm}>
                    <td className="cod"><Link href={`/atualizacoes?competencia=${c.aaaamm}`}>{rotuloCompetencia(c.aaaamm)}</Link></td>
                    <td className="num">{c.arquivos.baixados}</td>
                    <td className="num">{c.arquivos.pendentes ? <span className="situacao pendente">{c.arquivos.pendentes}</span> : 0}</td>
                    <td className="num">{c.programas.baixados}</td>
                    <td className="num">{c.programas.pendentes ? <span className="situacao pendente">{c.programas.pendentes}</span> : 0}</td>
                  </tr>
                ))}
                {lista && comItens.length === 0 && (
                  <tr><td colSpan={5} className="texto-suave">Nenhuma verificação ainda. Abra Atualizações e clique em Verificar agora.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">event_note</span> Competências</h5>
            <span className="texto-suave">Cronograma do CNES</span>
          </div>
          <div className="tabela-rolagem">
            <table className="sus-table">
              <thead>
                <tr><th>Competência</th><th>Abertura</th><th>Fechamento</th><th>Situação</th></tr>
              </thead>
              <tbody>
                {cronograma.map((c) => {
                  const [rotulo, classe] = ROTULO_SITUACAO_COMPETENCIA[c.situacao];
                  return (
                    <tr key={c.aaaamm}>
                      <td className="cod">{rotuloCompetencia(c.aaaamm)}</td>
                      <td>{dataBR(c.abertura)}</td>
                      <td>{dataBR(c.fechamento)}</td>
                      <td><span className={`situacao ${classe}`}>{rotulo}</span></td>
                    </tr>
                  );
                })}
                {lista && cronograma.length === 0 && (
                  <tr><td colSpan={4} className="texto-suave">Cronograma ainda não lido.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="cad-card" style={{ marginTop: 20 }}>
        <div className="cad-card-head">
          <h5><span className="material-symbols-outlined">memory</span> Processamentos {aberta ? `da competência ${rotuloCompetencia(aberta.aaaamm)}` : ''}</h5>
          <span className="texto-suave">Disponível na etapa 5</span>
        </div>
        <div className="tabela-rolagem">
          <table className="sus-table">
            <thead><tr>{SISTEMAS.map((s) => <th key={s}>{s}</th>)}</tr></thead>
            <tbody>
              <tr>{SISTEMAS.map((s) => <td key={s}><span className="situacao neutra">Não iniciado</span></td>)}</tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
