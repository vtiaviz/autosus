import { apresentacao, competenciaPadrao, PADRAO_COMPETENCIA, rotulo } from './competencia';

describe('competência', () => {
  it('apresentação é o mês seguinte, virando o ano', () => {
    expect(apresentacao('202608')).toBe('202609');
    expect(apresentacao('202612')).toBe('202701');
  });

  it('competência padrão é o mês anterior', () => {
    expect(competenciaPadrao(new Date(2026, 10, 7))).toBe('202610');
    expect(competenciaPadrao(new Date(2027, 0, 15))).toBe('202612');
  });

  it('valida AAAAMM', () => {
    expect(PADRAO_COMPETENCIA.test('202610')).toBe(true);
    expect(PADRAO_COMPETENCIA.test('202613')).toBe(false);
    expect(PADRAO_COMPETENCIA.test('2026-10')).toBe(false);
  });

  it('rótulo MM/AAAA', () => expect(rotulo('202610')).toBe('10/2026'));
});
