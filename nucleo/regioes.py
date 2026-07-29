"""Tabela fixa de estados e regiões do Brasil (não vem do Metabase) — usada
pela auditoria de volume para filtrar "perdidos" pela cobertura geográfica
do cliente."""

ESTADOS = [
    ("Acre", "AC", "Norte"),
    ("Amapá", "AP", "Norte"),
    ("Amazonas", "AM", "Norte"),
    ("Pará", "PA", "Norte"),
    ("Rondônia", "RO", "Norte"),
    ("Roraima", "RR", "Norte"),
    ("Tocantins", "TO", "Norte"),
    ("Alagoas", "AL", "Nordeste"),
    ("Bahia", "BA", "Nordeste"),
    ("Ceará", "CE", "Nordeste"),
    ("Maranhão", "MA", "Nordeste"),
    ("Paraíba", "PB", "Nordeste"),
    ("Pernambuco", "PE", "Nordeste"),
    ("Piauí", "PI", "Nordeste"),
    ("Rio Grande do Norte", "RN", "Nordeste"),
    ("Sergipe", "SE", "Nordeste"),
    ("Distrito Federal", "DF", "Centro-Oeste"),
    ("Goiás", "GO", "Centro-Oeste"),
    ("Mato Grosso", "MT", "Centro-Oeste"),
    ("Mato Grosso do Sul", "MS", "Centro-Oeste"),
    ("Espírito Santo", "ES", "Sudeste"),
    ("Minas Gerais", "MG", "Sudeste"),
    ("Rio de Janeiro", "RJ", "Sudeste"),
    ("São Paulo", "SP", "Sudeste"),
    ("Paraná", "PR", "Sul"),
    ("Rio Grande do Sul", "RS", "Sul"),
    ("Santa Catarina", "SC", "Sul"),
]
REGIOES_ORDEM = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
NACIONAL = "Nacional"

OPCOES_REGIAO = (
    [NACIONAL]
    + REGIOES_ORDEM
    + [nome for nome, _sigla, _regiao in sorted(ESTADOS, key=lambda e: e[0])]
)


def resolver_ufs(selecionados: list):
    """Converte o que foi marcado na tela (Nacional/Região/Estado, por
    extenso) num conjunto de siglas de UF pra filtrar. Devolve None quando
    não deve filtrar nada (Nacional selecionado, ou nada selecionado)."""
    if not selecionados or NACIONAL in selecionados:
        return None
    ufs = set()
    for escolha in selecionados:
        if escolha in REGIOES_ORDEM:
            ufs.update(sigla for _nome, sigla, regiao in ESTADOS if regiao == escolha)
        else:
            match = next((sigla for nome, sigla, _regiao in ESTADOS if nome == escolha), None)
            if match:
                ufs.add(match)
    return ufs
