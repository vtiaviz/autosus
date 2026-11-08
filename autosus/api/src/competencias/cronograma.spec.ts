import { lerCronograma, situacao } from './cronograma';

// mesma estrutura da página do wiki do CNES (tabela "wikitable", cabeçalho, uma linha por mês)
const PAGINA = `
<table class="wikitable">
<tr><td colspan="10"><b><span>CRONOGRAMA 2026</span></b>
</td></tr>
<tr><th>COMPETÊNCIA
</th><th>DISPONIBILIZAÇÃO DA COMPETÊNCIA DO SIGTAP
</th><th>DISPONIBILIZAÇÃO DOS APLICATIVOS DE PROCESSAMENTO
</th><th>ENVIO DA REMESSA DO SIA/SIH
</th><th>DISSEMINAÇÃO TABNET/TABWIN***
</th></tr>
<tr><td align="left">MARÇO
</td><td>03/03/2026
</td><td>07/04/2026
</td><td>30/04/2026
</td><td>10/05/2026
</td></tr>
<tr><td align="left">DEZEMBRO
</td><td>02/12/2026
</td><td>07/01/2027
</td><td>29/01/2027
</td><td>10/02/2027
</td></tr>
</table>
<table class="wikitable"><tr><td>Notas</td></tr></table>`;

describe('lerCronograma', () => {
  const linhas = lerCronograma(PAGINA);

  it('lê uma linha por mês, com acento e virada de ano', () => {
    expect(linhas.map((l) => l.aaaamm)).toEqual(['202603', '202612']);
  });

  it('separa abertura e fechamento', () => {
    expect(linhas[0].abertura).toBe('2026-04-07');
    expect(linhas[0].fechamento).toBe('2026-04-30');
    expect(linhas[1].fechamento).toBe('2027-01-29');
  });

  it('guarda todas as datas com o rótulo sem asteriscos', () => {
    expect(linhas[0].datas).toHaveLength(4);
    expect(linhas[0].datas[3]).toEqual({
      rotulo: 'DISSEMINAÇÃO TABNET/TABWIN',
      data: '2026-05-10',
    });
  });

  it('ignora página sem cronograma', () => {
    expect(lerCronograma('<html><body>fora do ar</body></html>')).toEqual([]);
  });
});

describe('situacao', () => {
  const abertura = new Date('2026-11-06');
  const fechamento = new Date('2026-11-30');
  it.each([
    ['2026-11-05', 'aguardando'],
    ['2026-11-06', 'aberta'],
    ['2026-11-30', 'aberta'],
    ['2026-12-01', 'encerrada'],
  ])('%s → %s', (dia, esperado) => {
    expect(situacao(abertura, fechamento, new Date(`${dia}T12:00:00Z`))).toBe(esperado);
  });
  it('sem datas', () => expect(situacao(null, null)).toBe('sem_datas'));
});
