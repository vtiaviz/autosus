'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { api, dataHoraBR, rotuloCompetencia, tamanho } from '@/lib/api';
import {
  Competencia,
  PainelProcessamento,
  Processamento,
  ROTULO_ETAPA,
  ROTULO_SISTEMA,
  Servidor,
} from '@/lib/tipos';

const FINAIS = ['concluido', 'falhou', 'aguardando_decisao', 'cancelado', 'interrompido'];
const MODO = 'autosus:modoEnvio';

function competenciaPadrao() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function Selo({ situacao }: { situacao: string }) {
  const [rotulo, classe] = ROTULO_SISTEMA[situacao] ?? [situacao, 'neutra'];
  return <span className={`situacao ${classe}`}>{rotulo}</span>;
}

/** Log do job em andamento, lido aos pedaços (o Server_SUS devolve a partir do byte "desde"). */
function Log({ jobId, ativo }: { jobId: string; ativo: boolean }) {
  const [texto, setTexto] = useState('');
  const desde = useRef(0);
  const caixa = useRef<HTMLPreElement>(null);
  useEffect(() => {
    desde.current = 0;
    setTexto('');
    let parar = false;
    const ler = async () => {
      try {
        const r = await api<{ texto: string; proximo: number }>(`/processamento/jobs/${jobId}/log?desde=${desde.current}`);
        if (parar) return;
        desde.current = r.proximo;
        // linhas repetidas de espera ("aguardando o agente") não ajudam a acompanhar
        const novo = r.texto.split('\n').filter((l) => !l.includes('aguardando o agente')).join('\n');
        if (novo.trim()) setTexto((t) => (t + novo).slice(-60_000));
      } catch {
        /* tenta de novo no próximo ciclo */
      }
    };
    void ler();
    const t = ativo ? setInterval(() => void ler(), 4000) : undefined;
    return () => {
      parar = true;
      if (t) clearInterval(t);
    };
  }, [jobId, ativo]);
  useEffect(() => {
    if (caixa.current) caixa.current.scrollTop = caixa.current.scrollHeight;
  }, [texto]);
  return <pre className="log-saida" ref={caixa} style={{ maxHeight: 320 }}>{texto || '(sem saída ainda)'}</pre>;
}

function Job({ p, progresso, aoCancelar }: { p: Processamento; progresso: string | null; aoCancelar: () => void }) {
  const ativo = !FINAIS.includes(p.situacao);
  return (
    <div className="cad-card" style={{ marginTop: 20 }}>
      <div className="cad-card-head">
        <h5>
          <span className="material-symbols-outlined">{ativo ? 'progress_activity' : 'task_alt'}</span>
          {ativo ? 'Em andamento' : 'Último processamento'}: {p.etapas.map((e) => ROTULO_ETAPA[e] ?? e).join(' → ')}
        </h5>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Selo situacao={p.situacao} />
          {p.modoEnvio === 'automatico' && <span className="situacao aberta">envio automático</span>}
          {ativo && (
            <button className="btn-new" style={{ background: 'var(--danger)' }} onClick={aoCancelar}>
              <span className="material-symbols-outlined">stop_circle</span> Cancelar
            </button>
          )}
        </div>
      </div>
      <div className="cad-card-body" style={{ paddingBottom: 18 }}>
        {p.mensagem && <div className={p.situacao === 'concluido' ? 'texto-suave' : 'aviso-erro'}>{p.mensagem}</div>}
        {ativo && progresso && <p className="texto-suave">Agente: {progresso}</p>}
        <table className="sus-table" style={{ marginBottom: 14 }}>
          <thead><tr><th>Etapa</th><th>Comando do robô</th><th>Situação</th><th>Início</th><th>Fim</th></tr></thead>
          <tbody>
            {p.passos.map((passo, i) => (
              <tr key={i}>
                <td className="cod">{ROTULO_ETAPA[passo.etapa] ?? passo.etapa}</td>
                <td><code>{passo.args.join(' ')}</code></td>
                <td><Selo situacao={passo.situacao} /></td>
                <td>{dataHoraBR(passo.inicio)}</td>
                <td>{dataHoraBR(passo.fim)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Log jobId={p.jobId} ativo={ativo} />
        {p.imagens.length > 0 && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
            {p.imagens.slice(-6).map((nome) => (
              <a key={nome} href={`/api/processamento/jobs/${p.jobId}/imagens/${nome}`} target="_blank" rel="noreferrer" title={nome}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/processamento/jobs/${p.jobId}/imagens/${nome}`} alt={nome}
                  style={{ height: 90, border: '1px solid var(--border)', borderRadius: 8 }} />
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Pagina() {
  const params = useSearchParams();
  const [aaaamm, setAaaamm] = useState(params.get('competencia') ?? competenciaPadrao());
  const [competencias, setCompetencias] = useState<Competencia[]>([]);
  const [painel, setPainel] = useState<PainelProcessamento | null>(null);
  const [servidor, setServidor] = useState<Servidor | null>(null);
  const [modo, setModo] = useState<'manual' | 'automatico'>('manual');
  const [erro, setErro] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [confirmacao, setConfirmacao] = useState('');

  const carregar = useCallback(async () => {
    const [p, s] = await Promise.all([
      api<PainelProcessamento>(`/processamento/${aaaamm}`).catch((e: Error) => { setErro(e.message); return null; }),
      api<Servidor>('/processamento/servidor').catch(() => null),
    ]);
    if (p) setPainel(p);
    if (s) setServidor(s);
  }, [aaaamm]);

  useEffect(() => {
    api<Competencia[]>('/competencias').then(setCompetencias).catch(() => undefined);
    try {
      const m = localStorage.getItem(MODO);
      if (m === 'automatico' || m === 'manual') setModo(m);
    } catch {
      /* sem armazenamento local */
    }
  }, []);
  useEffect(() => {
    setPainel(null);
    void carregar();
  }, [carregar]);

  const ativo = painel?.processamentos.find((p) => !FINAIS.includes(p.situacao));
  useEffect(() => {
    const t = setInterval(() => void carregar(), ativo ? 5000 : 20000);
    return () => clearInterval(t);
  }, [ativo, carregar]);

  function trocarModo(m: 'manual' | 'automatico') {
    setModo(m);
    try {
      localStorage.setItem(MODO, m);
    } catch {
      /* segue sem lembrar */
    }
  }

  async function acao(fn: () => Promise<unknown>, ok?: string) {
    setErro('');
    setAviso('');
    setOcupado(true);
    try {
      await fn();
      if (ok) setAviso(ok);
      await carregar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  const processar = (etapas: string[], ok: string) =>
    acao(() => api(`/processamento/${aaaamm}`, { method: 'POST', body: JSON.stringify({ etapas, modoEnvio: modo }) }), ok);

  const opcoes = Array.from(new Set([competenciaPadrao(), aaaamm, ...competencias.map((c) => c.aaaamm)]))
    .filter((c) => c <= competenciaPadrao())
    .sort()
    .reverse()
    .slice(0, 12);
  const temDts = painel?.saidas?.arquivos.some((a) => a.nome.toUpperCase().endsWith(`${aaaamm}.DTS`));
  const vm = servidor?.vm;
  const bloqueado = ocupado || !!ativo || !servidor?.online;
  const ultimo = ativo ?? painel?.processamentos[0];

  const BOTOES: [string, string, string[], string][] = [
    ['system_update_alt', 'Atualizar sistemas', ['iniciar', 'atualizar'], 'Atualização dos sistemas na fila.'],
    ['description', 'SISAIH01', ['iniciar', 'sisaih01'], 'SISAIH01 na fila.'],
    ['payments', 'FPO', ['iniciar', 'fpo'], 'FPO na fila.'],
    ['fact_check', 'SIHD2', ['iniciar', 'sihd'], 'SIHD2 na fila (leva de 4 a 5 horas).'],
    ['wifi_tethering', 'Testar conexão', ['iniciar', 'transmissor_testar'], 'Teste de conexão do Transmissor na fila.'],
  ];

  return (
    <>
      <div className="pagina-cabecalho">
        <div>
          <h3>Processamento AIH da competência {rotuloCompetencia(aaaamm)}</h3>
          <p>Tudo roda no Server_SUS, um processamento por vez</p>
        </div>
        <select className="seletor-competencia" value={aaaamm} onChange={(e) => setAaaamm(e.target.value)} aria-label="Competência">
          {opcoes.map((c) => <option key={c} value={c}>{rotuloCompetencia(c)}</option>)}
        </select>
      </div>

      {erro && <div className="aviso-erro">{erro}</div>}
      {aviso && <div className="cad-card" style={{ padding: '10px 14px', marginBottom: 16 }}>{aviso}</div>}

      <div className="stats-strip">
        <div className="stat-card">
          <div className={`stat-icon ${servidor?.online ? 'green' : 'red'}`}><span className="material-symbols-outlined">dns</span></div>
          <div className="stat-info"><p>Server_SUS</p><h4 style={{ fontSize: '1rem' }}>{servidor ? (servidor.online ? 'No ar' : 'Fora do ar') : '...'}</h4></div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${vm?.estado === 'running' ? 'green' : 'yellow'}`}><span className="material-symbols-outlined">computer</span></div>
          <div className="stat-info"><p>VM dos sistemas</p><h4 style={{ fontSize: '1rem' }}>{vm ? (vm.estado === 'running' ? 'Ligada' : vm.estado === 'paused' ? 'Pausada' : 'Desligada') : '-'}</h4></div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${servidor?.agente?.vivo ? 'green' : 'yellow'}`}><span className="material-symbols-outlined">smart_toy</span></div>
          <div className="stat-info"><p>Agente</p><h4 style={{ fontSize: '1rem' }}>{servidor?.agente ? (servidor.agente.vivo ? `Ativo ${servidor.agente.versao ?? ''}` : 'Sem sinal') : '-'}</h4></div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${vm && vm.espaco_livre_disco_vm_gb < 10 ? 'red' : 'blue'}`}><span className="material-symbols-outlined">hard_drive</span></div>
          <div className="stat-info"><p>Livre no disco da VM</p><h4 style={{ fontSize: '1rem' }}>{vm ? `${vm.espaco_livre_disco_vm_gb} GB (${vm.disco_vm})` : '-'}</h4></div>
        </div>
      </div>
      {servidor && !servidor.online && <div className="aviso-erro" style={{ marginTop: 16 }}>{servidor.erro}</div>}

      <div className="grade-2">
        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">play_circle</span> Processar</h5>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center', fontSize: '.85rem' }}>
              <span className="texto-suave">Envio:</span>
              <label><input type="radio" checked={modo === 'manual'} onChange={() => trocarModo('manual')} /> Manual</label>
              <label><input type="radio" checked={modo === 'automatico'} onChange={() => trocarModo('automatico')} /> Automático</label>
            </div>
          </div>
          <div className="cad-card-body" style={{ paddingBottom: 18 }}>
            <p className="texto-suave" style={{ marginTop: 0 }}>
              {modo === 'automatico'
                ? 'Automático: no SIHD2 (e no Processar tudo), o .DTS é transmitido sozinho se o SIHD2 terminar sem nenhuma crítica. Com crítica, nada é enviado, o envio passa para manual e chega um aviso por e-mail.'
                : 'Manual: o SIHD2 libera as AIHs bloqueadas e para no .DTS; a transmissão só acontece pelo botão Transmitir.'}
            </p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn-new" disabled={ocupado || !servidor?.online} onClick={() => acao(() => api('/processamento/servidor/ligar', { method: 'POST' }), 'VM ligando; o agente responde em cerca de 1 minuto.')}>
                <span className="material-symbols-outlined">power_settings_new</span> Ligar servidor
              </button>
              {BOTOES.map(([icone, titulo, etapas, ok]) => (
                <button key={titulo} className="btn-new" disabled={bloqueado} onClick={() => processar(etapas, ok)}>
                  <span className="material-symbols-outlined">{icone}</span> {titulo}
                </button>
              ))}
              <button className="btn-new" disabled={bloqueado || !temDts} title={temDts ? '' : 'Ainda não há .DTS desta competência'}
                style={{ background: 'var(--danger)' }} onClick={() => { setConfirmacao(''); setConfirmando(true); }}>
                <span className="material-symbols-outlined">send</span> Transmitir
              </button>
            </div>
            <div style={{ marginTop: 14 }}>
              <button className="btn-new" disabled={bloqueado} style={{ background: 'var(--accent)' }}
                onClick={() => processar(['iniciar', 'atualizar', 'sisaih01', 'fpo', 'sihd'], modo === 'automatico'
                  ? 'Processamento completo na fila; o envio é automático se o SIHD2 terminar sem críticas.'
                  : 'Processamento completo na fila; ele para no .DTS, e o envio fica para o botão Transmitir.')}>
                <span className="material-symbols-outlined">rocket_launch</span> Processar tudo
              </button>
            </div>

            {confirmando && (
              <div className="aviso-erro" style={{ marginTop: 16 }}>
                <strong>Transmitir a produção {rotuloCompetencia(aaaamm)} ao DATASUS.</strong> Isto envia o .DTS de verdade e não pode ser desfeito.
                Para confirmar, digite <strong>{rotuloCompetencia(aaaamm)}</strong>:
                <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                  <input className="field-input" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} placeholder="MM/AAAA" style={{ maxWidth: 140 }} autoFocus />
                  <button className="btn-new" style={{ background: 'var(--danger)' }} disabled={confirmacao !== rotuloCompetencia(aaaamm) || ocupado}
                    onClick={() => acao(async () => {
                      await api(`/processamento/${aaaamm}/transmitir`, { method: 'POST', body: JSON.stringify({ confirmacao }) });
                      setConfirmando(false);
                    }, 'Transmissão na fila.')}>
                    Confirmar envio
                  </button>
                  <button className="btn-new" style={{ background: '#8a9ab5' }} onClick={() => setConfirmando(false)}>Desistir</button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">monitoring</span> Sistemas</h5>
          </div>
          <table className="sus-table">
            <thead><tr><th>Sistema</th><th>Situação</th><th>Quando</th><th>Versão na VM</th></tr></thead>
            <tbody>
              {(painel?.sistemas ?? []).map((s) => (
                <tr key={s.sistema}>
                  <td className="cod">{s.sistema}</td>
                  <td><Selo situacao={s.situacao} /></td>
                  <td>{dataHoraBR(s.quando)}</td>
                  <td>{vm?.versoes_instaladas?.[s.sistema.toUpperCase()] ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {ultimo && <Job p={ultimo} progresso={painel?.progresso ?? null} aoCancelar={() => acao(() => api(`/processamento/jobs/${ultimo.jobId}/cancelar`, { method: 'POST' }), 'Cancelamento pedido; o agente para no próximo passo.')} />}

      <div className="grade-2">
        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">inventory_2</span> Arquivos no Server_SUS</h5>
            <button className="btn-new" disabled={ocupado || !servidor?.online} onClick={() => acao(async () => {
              const r = await api<{ itens: { situacao: string }[] }>(`/processamento/${aaaamm}/arquivos`, { method: 'POST' });
              const erros = r.itens.filter((i) => i.situacao === 'erro').length;
              setAviso(`${r.itens.length - erros} arquivo(s) conferidos no servidor${erros ? `, ${erros} com erro` : ''}.`);
            })}>
              <span className="material-symbols-outlined">upload</span> Enviar downloads
            </button>
          </div>
          <table className="sus-table">
            <thead><tr><th>Item</th><th>Arquivo</th><th>Tamanho</th></tr></thead>
            <tbody>
              {(painel?.entrada?.itens ?? []).map((i) => (
                <tr key={i.item}>
                  <td className="cod">{i.item}</td>
                  <td>{i.arquivo ? i.arquivo.nome : <span className="situacao pendente">Falta</span>}</td>
                  <td className="num">{i.arquivo ? tamanho(i.arquivo.tamanho) : '-'}</td>
                </tr>
              ))}
              {!painel?.entrada && <tr><td colSpan={3} className="texto-suave">Server_SUS fora do ar.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="cad-card">
          <div className="cad-card-head">
            <h5><span className="material-symbols-outlined">output</span> Arquivos gerados (competência {rotuloCompetencia(aaaamm)})</h5>
          </div>
          <table className="sus-table">
            <thead><tr><th>Arquivo</th><th>Gerado em</th><th>Tamanho</th></tr></thead>
            <tbody>
              {(painel?.saidas?.arquivos ?? []).map((a) => (
                <tr key={a.nome}><td className="cod">{a.nome}</td><td>{dataHoraBR(a.modificado)}</td><td className="num">{tamanho(a.tamanho)}</td></tr>
              ))}
              {painel?.saidas && painel.saidas.arquivos.length === 0 && <tr><td colSpan={3} className="texto-suave">Nada gerado ainda.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {painel && painel.processamentos.length > 1 && (
        <div className="cad-card" style={{ marginTop: 20 }}>
          <div className="cad-card-head"><h5><span className="material-symbols-outlined">history</span> Histórico</h5></div>
          <table className="sus-table">
            <thead><tr><th>Pedido em</th><th>Etapas</th><th>Envio</th><th>Situação</th><th>Mensagem</th></tr></thead>
            <tbody>
              {painel.processamentos.map((p) => (
                <tr key={p.id}>
                  <td>{dataHoraBR(p.criadoEm)}</td>
                  <td>{p.etapas.map((e) => ROTULO_ETAPA[e] ?? e).join(', ')}</td>
                  <td>{p.modoEnvio === 'automatico' ? 'Automático' : 'Manual'}</td>
                  <td><Selo situacao={p.situacao} /></td>
                  <td className="texto-suave">{p.mensagem ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export default function ProcessamentoPagina() {
  return (
    <Suspense>
      <Pagina />
    </Suspense>
  );
}
