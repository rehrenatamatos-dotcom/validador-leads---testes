"""Classificação de leads por IA (Cerebras, Groq, SambaNova ou Gemini —
todos com API compatível com OpenAI). Usado pelo validador de foco (leads
recebidos) e pela auditoria de volume (leads não recebidos, pra saber quais
deles seriam de fato aproveitados)."""
import json
import time

import requests

from nucleo.metabase import secret

PROVEDORES = {
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "chave": "CEREBRAS_API_KEY",
        "modelos": ["llama-3.3-70b", "llama3.1-8b", "gpt-oss-120b"],
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "chave": "GROQ_API_KEY",
        "modelos": ["openai/gpt-oss-20b", "llama-3.1-8b-instant",
                    "llama-3.3-70b-versatile", "openai/gpt-oss-120b"],
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "chave": "SAMBANOVA_API_KEY",
        "modelos": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct", "Qwen2.5-72B-Instruct"],
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "chave": "GEMINI_API_KEY",
        "modelos": ["gemini-2.0-flash", "gemini-1.5-flash"],
    },
}

MODELOS_ESCOLHA = {
    "Automático (recomendado)": None,
    "Rápido · Cerebras Llama 3.1 8B": ("cerebras", "llama3.1-8b"),
    "Rápido · Groq GPT-OSS 20B": ("groq", "openai/gpt-oss-20b"),
    "Equilíbrio · Cerebras Llama 3.3 70B": ("cerebras", "llama-3.3-70b"),
    "Equilíbrio · Groq Llama 3.3 70B": ("groq", "llama-3.3-70b-versatile"),
    "Preciso · Groq GPT-OSS 120B": ("groq", "openai/gpt-oss-120b"),
    "Equilíbrio · SambaNova Llama 3.3 70B": ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
    "Rápido · Gemini 2.0 Flash": ("gemini", "gemini-2.0-flash"),
}

TAMANHO_LOTE = 20
MAX_TENTATIVAS = 5
STATUS_VALIDOS = {"Dentro do foco", "Fora do foco", "Aberto"}

PROMPT_SISTEMA = """Você é um analista de qualidade de leads de uma plataforma de geração de leads B2B.
Sua tarefa: para cada lead abaixo, decidir se ele está DENTRO ou FORA do foco do cliente descrito no perfil, ou se está ABERTO (mensagem sem informação suficiente para avaliar).

ANTES DE CLASSIFICAR: identifique no perfil O QUE o cliente vende — um PRODUTO (ex. máquinas, equipamentos) ou um SERVIÇO (ex. corte sob medida, usinagem para terceiros). Essa distinção é o critério mais importante.

Critérios (avalie em conjunto, nenhum sozinho decide):
1. Produto vs. serviço. Se o cliente VENDE MÁQUINAS e o lead quer CONTRATAR o serviço (ex. "preciso cortar 50 chapas", "orçamento para corte de peças"), é "Fora do foco" — mesmo que a mensagem seja tecnicamente detalhada (material, medidas, CNPJ). Especificidade técnica NÃO transforma um pedido de serviço em lead de máquina. O inverso também vale (cliente presta serviço e lead quer comprar máquina). Salvo se o perfil disser que o cliente atende ambos.
2. Produto da mensagem vs. anúncios do cliente. Você tem DUAS fontes sobre os anúncios do cliente: (i) o campo "Anúncio do cliente" da própria linha, no "Contexto extra" de cada lead (o anúncio ao qual a plataforma vinculou aquele lead específico) e (ii) a lista "ANÚNCIOS ATIVOS DO CLIENTE" no perfil (todos os anúncios que o cliente roda atualmente). Use SEMPRE o valor de "Anúncio do cliente" DAQUELA linha especificamente — nunca um produto "padrão"/mais comum do cliente de memória, e nunca o anúncio de outra linha; citar o anúncio errado no motivo é o erro mais comum aqui. Depois:
   a) Se a mensagem NOMEIA um produto/pedido específico e ele corresponde ao "Anúncio do cliente" da própria linha OU a qualquer um dos "ANÚNCIOS ATIVOS DO CLIENTE" (mesmo termo ou sinônimo/mesma família — ex.: "rosca helicoidal" ~ "rosca transportadora"; "quadro de comando" ~ "quadro elétrico" ~ "painel elétrico" ~ "armário elétrico" são a mesma coisa), classifique "Dentro do foco" — mesmo que o anúncio vinculado a ESSA cotação específica seja outro, desde que o produto pedido bata com algum anúncio ativo do cliente.
   b) Se a mensagem é vaga e NÃO nomeia nenhum produto (ex.: "quero comprar", "gostaria de saber o valor", "me manda os dados"), nenhum anúncio decide sozinho — continua "Aberto".
   c) Se o produto pedido claramente não tem nada a ver com o que o cliente trabalha (não bate com o "Anúncio do cliente" da linha, nem com nenhum "ANÚNCIO ATIVO DO CLIENTE", nem com o restante do perfil), ou está excluído pelas observações do projeto, classifique "Fora do foco".
   d) Ignore o campo "anúncio de origem do Orçamento" (e "satélite de origem") para esta avaliação — eles são o site/anúncio de terceiros onde o lead teve origem antes de ser casado com o cliente, não o que o cliente vende.
3. Modalidade compatível. Pedidos de assistência técnica/manutenção, aluguel de máquina, ou peças/componentes avulsos são "Fora do foco" quando o cliente vende equipamentos novos — salvo indicação contrária no perfil ou nas regras específicas.
4. Material/produto compatível com o portfólio do cliente. Se o cliente trabalha metal e o lead pede madeira/tecido/PVC, é forte sinal de "Fora do foco", mesmo que o serviço seja o mesmo.
5. B2B vs. uso pessoal. Pedidos claramente domésticos/pontuais de pessoa física pesam para "Fora do foco" quando o cliente atende indústria/B2B.
6. Especificidade técnica. Medidas, normas, quantidade definida, nome de empresa/CNPJ pesam para "Dentro do foco" — mas SOMENTE quando o pedido é da modalidade certa (ver critério 1).
7. Sinais de ruído. Teste interno (QA, e-mails de qualidade), spam, concorrente se oferecendo, marca/modelo que o cliente não vende, ou lead avisando que já comprou em outro lugar = "Fora do foco" independente do produto.
8. Mensagem inteiramente em inglês. Se a mensagem do lead estiver totalmente escrita em inglês (ex. "Dear Sir/Madam, we are interested in your products..."), classifique como "Fora do foco" — são tipicamente bots ou contatos genéricos internacionais fora do público-alvo. Isso vale mesmo que a mensagem pareça pedir um produto do cliente. NÃO se aplica a mensagens em português que contenham apenas termos técnicos ou nomes de produto em inglês (ex. "máquina laser CO2", "new laser nli390") — essas continuam sendo avaliadas normalmente.
9. Regras específicas do cliente (se fornecidas no perfil) têm prioridade sobre os critérios gerais.

Regras de saída:
- STATUS deve ser EXATAMENTE um destes: "Dentro do foco", "Fora do foco", "Aberto".
- MOTIVO: uma frase objetiva em português citando a evidência da própria mensagem. O motivo deve justificar o STATUS escolhido, não outro.
- Mensagens vagas demais para julgar (ex. apenas "aço inox", apenas "me manda o e-mail", uma palavra solta sem contexto de compra) = "Aberto". NUNCA marque "Dentro do foco" sem evidência de interesse na modalidade certa (compra do produto que o cliente vende) — o vínculo com um "Anúncio do cliente", sozinho, sem a mensagem nomear o produto, não é evidência suficiente (ver critério 2b).
- Peças, componentes e insumos avulsos (ex. fonte, tubo de laser, lentes) = "Fora do foco" quando o cliente vende máquinas completas, salvo indicação contrária no perfil.
- Mensagens idênticas ou quase idênticas (mesmo texto em vários leads) DEVEM receber exatamente a mesma classificação e o mesmo motivo — revise antes de responder.
- Mensagem inteiramente em inglês = "Fora do foco" (ver critério 8), com motivo indicando que é mensagem em inglês / provável bot.
- Responda SOMENTE com um objeto JSON: {"resultados": [{"id": "...", "status": "...", "motivo": "..."}]} — um item por lead, na mesma ordem."""


def provedores_ativos() -> list:
    """Retorna a lista de provedores com chave configurada (Cerebras primeiro)."""
    return [n for n in ("cerebras", "groq", "sambanova", "gemini") if secret(PROVEDORES[n]["chave"])]


def _extrair_lista(parsed):
    if isinstance(parsed, list):
        return parsed
    for v in parsed.values():
        if isinstance(v, list):
            return v
    raise ValueError("Resposta sem lista de resultados.")


def _tentar_modelo(url, api_key, modelo, conteudo_user):
    """Uma chamada a um modelo específico. Retorna (lista, None) em sucesso,
    ('404', None) se o modelo não existe, ('cota', horas) se a cota diária estourou,
    (None, excecao) em outros erros."""
    corpo = {
        "model": modelo,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": conteudo_user},
        ],
    }
    ultima = None
    limite_estourado = False
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            r = requests.post(url, json=corpo, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)
            if r.status_code in (400, 404):
                return "404", None                      # modelo indisponível: tenta o próximo
            if r.status_code in (401, 403):
                return "auth", None                     # chave inválida/não autorizada: não adianta repetir
            if r.status_code == 429 or r.status_code >= 500:
                limite_estourado = r.status_code == 429  # 429 = limite/cota do provedor estourou
                try:
                    espera = float(r.headers.get("retry-after", 0))
                except (TypeError, ValueError):
                    espera = 0
                if espera > 300:
                    return "cota", espera
                time.sleep(min(60, espera + 1) if espera else min(30, 5 * tentativa))
                continue
            r.raise_for_status()
            texto = r.json()["choices"][0]["message"]["content"]
            return _extrair_lista(json.loads(texto)), None
        except Exception as e:
            ultima = e
            time.sleep(2)
    if limite_estourado:
        return "cota", 0                                # esgotou as tentativas em 429: trata como cota
    return None, ultima


def chamar_ia(perfil, lote, ordem, modelo_forcado=None):
    """Tenta os provedores em ordem; dentro de cada um, tenta a lista de modelos candidatos
    (começando pelo escolhido). Pula modelos indisponíveis (404) e troca de provedor na cota."""
    leads_texto = "\n\n".join(
        f"LEAD id={l['id']}\nMensagem: {l['mensagem']}\nContexto extra: {l['extra']}"
        for l in lote
    )
    conteudo_user = f"PERFIL DO CLIENTE:\n{perfil}\n\nLEADS A CLASSIFICAR:\n{leads_texto}"
    ultima = None
    esgotados = []
    sem_autorizacao = []
    for i, nome in enumerate(ordem):
        cfg = PROVEDORES[nome]
        api_key = secret(cfg["chave"])
        modelos = list(cfg["modelos"])
        if modelo_forcado and i == 0 and modelo_forcado in modelos:
            modelos.remove(modelo_forcado)
            modelos.insert(0, modelo_forcado)
        elif modelo_forcado and i == 0:
            modelos.insert(0, modelo_forcado)

        cota_estourou = False
        for modelo in modelos:
            resultado, err = _tentar_modelo(cfg["url"], api_key, modelo, conteudo_user)
            if isinstance(resultado, list):
                return resultado
            if resultado == "404":
                continue
            if resultado == "auth":
                sem_autorizacao.append(nome)
                break
            if resultado == "cota":
                esgotados.append(nome)
                cota_estourou = True
                break
            ultima = err
        if cota_estourou:
            continue
    if sem_autorizacao and set(esgotados) | set(sem_autorizacao) >= set(ordem):
        raise RuntimeError(
            "Chave de IA inválida ou não autorizada em: "
            f"{', '.join(sorted(set(sem_autorizacao)))} (erro 401/403). Confira/atualize essa "
            "chave nos Secrets (CEREBRAS_API_KEY, GROQ_API_KEY, SAMBANOVA_API_KEY ou GEMINI_API_KEY)."
        )
    if esgotados and len(esgotados) == len(ordem):
        raise RuntimeError(
            "Cota diária esgotada em todos os provedores de IA configurados "
            f"({', '.join(esgotados)}). Renova às 21h (horário de Brasília), ou adicione "
            "outra chave (CEREBRAS_API_KEY, GROQ_API_KEY, SAMBANOVA_API_KEY ou GEMINI_API_KEY) "
            "nos Secrets para continuar agora."
        )
    if ultima:
        raise ultima
    raise RuntimeError(
        "Nenhum modelo respondeu nos provedores configurados. "
        "Confira se as chaves de IA nos Secrets estão corretas e ativas."
    )


def classificar_lote(perfil, leads, ordem_ia, modelo_forcado=None, tamanho_lote=TAMANHO_LOTE,
                      progresso_callback=None):
    """Roda chamar_ia() em lotes sobre uma lista de leads ({"id","mensagem","extra"}),
    com re-tentativas em lotes cada vez menores para os que falharem — mesma
    estratégia usada pelo validador de foco. Devolve dict {id: {"status","motivo"}}.
    progresso_callback(feito, total), se informado, é chamado a cada lote."""
    classificacoes = {}

    def processar(lista, tam):
        total_lotes = (len(lista) + tam - 1) // tam
        for n in range(total_lotes):
            lote = lista[n * tam:(n + 1) * tam]
            try:
                resultado = chamar_ia(perfil, lote, ordem_ia, modelo_forcado)
            except RuntimeError:
                raise                        # cota/config: deixa subir pra quem chamou tratar
            except Exception:
                resultado = []               # erro pontual (HTTP, timeout): pula o lote
            for item in resultado:
                status = str(item.get("status", "")).strip()
                if status not in STATUS_VALIDOS:
                    status = "Aberto"
                classificacoes[str(item.get("id", "")).strip()] = {
                    "status": status, "motivo": str(item.get("motivo", "")).strip(),
                }
            if progresso_callback:
                progresso_callback(min((n + 1) * tam, len(lista)), len(lista))
            if n + 1 < total_lotes:
                time.sleep(1)

    processar(leads, tamanho_lote)
    pendentes = [l for l in leads if l["id"] not in classificacoes]
    if pendentes:
        time.sleep(3)
        processar(pendentes, max(1, tamanho_lote // 4))
    pendentes = [l for l in leads if l["id"] not in classificacoes]
    if pendentes:
        time.sleep(3)
        processar(pendentes, 1)
    return classificacoes
