import { BadRequestException, ConflictException } from '@nestjs/common';
import { ProcessamentoService } from './processamento.service';

// as dependências reais leem o .env (@nestjs/config, só ESM): aqui entram objetos de mentira
jest.mock('../atualizacoes/atualizacoes.service', () => ({ AtualizacoesService: class {} }));
jest.mock('../servidor/servidor.service', () => ({ ServidorService: class {} }));

/** Monta o serviço com banco e Server_SUS de mentira e guarda o que foi pedido ao Server_SUS. */
function montar(ativo: object | null = null, saidas: string[] = []) {
  const pedidos: { caminho: string; corpo?: Record<string, unknown> }[] = [];
  const servidor = {
    json: jest.fn((caminho: string, init?: RequestInit) => {
      pedidos.push({ caminho, corpo: init?.body ? JSON.parse(init.body as string) : undefined });
      if (caminho.endsWith('/saidas')) return Promise.resolve({ arquivos: saidas.map((nome) => ({ nome })) });
      return Promise.resolve({ id: 'job1', situacao: 'na_fila', passos: [] });
    }),
  };
  const prisma = {
    processamento: {
      findFirst: jest.fn().mockResolvedValue(ativo),
      create: jest.fn(({ data }: { data: object }) => Promise.resolve({ id: 1, ...data })),
    },
  };
  const svc = new ProcessamentoService(prisma as never, servidor as never, {} as never);
  return { svc, pedidos, prisma };
}

describe('ProcessamentoService.iniciar', () => {
  it('manual: SIHD2 libera as bloqueadas e não transmite', async () => {
    const { svc, pedidos } = montar();
    const p = await svc.iniciar('202610', ['iniciar', 'sihd'], 'manual');
    expect(pedidos[0].corpo).toEqual({ competencia: '202610', etapas: ['iniciar', 'sihd'] });
    expect(p).toMatchObject({ modoEnvio: 'manual', etapas: ['iniciar', 'sihd'] });
  });

  it('automático: SIHD2 para nas críticas e o envio vem logo depois, no mesmo job', async () => {
    const { svc, pedidos } = montar();
    const p = await svc.iniciar('202610', ['iniciar', 'atualizar', 'sisaih01', 'fpo', 'sihd'], 'automatico');
    expect(pedidos[0].corpo).toEqual({
      competencia: '202610',
      etapas: ['iniciar', 'atualizar', 'sisaih01', 'fpo', 'sihd', 'transmissor_enviar'],
      sihd_manual: true,
      confirmar_envio: true,
    });
    expect(p).toMatchObject({ modoEnvio: 'automatico' });
  });

  it('automático sem SIHD2 não transmite nada', async () => {
    const { svc, pedidos } = montar();
    await svc.iniciar('202610', ['iniciar', 'fpo'], 'automatico');
    expect(pedidos[0].corpo).toEqual({ competencia: '202610', etapas: ['iniciar', 'fpo'] });
  });

  it('não aceita transmitir por aqui nem etapa desconhecida', async () => {
    const { svc } = montar();
    await expect(svc.iniciar('202610', ['transmissor_enviar'], 'manual')).rejects.toBeInstanceOf(BadRequestException);
    await expect(svc.iniciar('202610', ['formatar'], 'manual')).rejects.toBeInstanceOf(BadRequestException);
  });

  it('um processamento por vez', async () => {
    const { svc, pedidos } = montar({ aaaamm: '202609' });
    await expect(svc.iniciar('202610', ['fpo'], 'manual')).rejects.toBeInstanceOf(ConflictException);
    expect(pedidos).toHaveLength(0);
  });
});

describe('ProcessamentoService.transmitir', () => {
  it('exige digitar a competência', async () => {
    const { svc, pedidos } = montar(null, ['HM15017501N202610.DTS']);
    await expect(svc.transmitir('202610', '10/2025')).rejects.toBeInstanceOf(BadRequestException);
    expect(pedidos).toHaveLength(0);
  });

  it('exige o .DTS no Server_SUS', async () => {
    const { svc } = montar(null, ['Valores_202610.VTP']);
    await expect(svc.transmitir('202610', '10/2026')).rejects.toBeInstanceOf(ConflictException);
  });

  it('com confirmação e .DTS, pede o envio', async () => {
    const { svc, pedidos } = montar(null, ['HM15017501N202610.DTS']);
    await svc.transmitir('202610', '10/2026');
    expect(pedidos[1].corpo).toEqual({
      competencia: '202610',
      etapas: ['iniciar', 'transmissor_enviar'],
      confirmar_envio: true,
    });
  });
});

describe('ProcessamentoService.liberar', () => {
  const parada = { aaaamm: '202609', jobId: 'jobD', situacao: 'aguardando_decisao', etapas: ['iniciar', 'sihd'] };
  const bloqueadas = [{ aih: '152610159490-8' }, { aih: '152610159526-0' }];

  function comDecisao() {
    const m = montar();
    // 1ª consulta: a última parada (decisão); 2ª: nenhum processamento ativo
    m.prisma.processamento.findFirst.mockResolvedValueOnce(parada).mockResolvedValueOnce(null);
    m.svc['servidor'].json = jest.fn((caminho: string, init?: RequestInit) => {
      m.pedidos.push({ caminho, corpo: init?.body ? JSON.parse(init.body as string) : undefined });
      if (caminho === '/jobs/jobD') return Promise.resolve({ id: 'jobD', bloqueadas });
      return Promise.resolve({ id: 'job2', situacao: 'na_fila', passos: [] });
    }) as never;
    return m;
  }

  it('libera só as aprovadas e continua o SIHD2 da crítica, sem transmitir', async () => {
    const { svc, pedidos } = comDecisao();
    await svc.liberar('202609', ['152610159490-8']);
    expect(pedidos[1].corpo).toEqual({
      competencia: '202609',
      etapas: ['iniciar', 'sihd_liberar', 'sihd'],
      aihs_liberar: ['152610159490-8'],
      sihd_manual: true,
      sihd_a_partir_de: 'criticar',
    });
  });

  it('não aceita AIH fora da lista', async () => {
    const { svc } = comDecisao();
    await expect(svc.liberar('202609', ['999999999999-9'])).rejects.toBeInstanceOf(BadRequestException);
  });

  it('sem parada esperando decisão, recusa', async () => {
    const { svc } = montar();
    await expect(svc.liberar('202609', [])).rejects.toBeInstanceOf(ConflictException);
  });
});