# Leilões de imóveis — site com atualização diária

Este repositório publica o app de leilões como site e o atualiza sozinho todo dia às 5h (horário de MS).

## Como funciona

1. Todo dia o GitHub Actions roda `coleta/rodar.py`.
2. O script coleta as quatro fontes: lista oficial da Caixa, Portal Zuk, Mega Leilões e Leilão Imóvel (bancos, PGFN e leiloeiras).
3. Ele normaliza os dados, tira os lotes vencidos, junta os destaques analisados (`analise/destaques.json`) e gera `site/dados/`.
4. O conteúdo de `site/` é publicado no GitHub Pages.

Se uma fonte falhar num dia, o site continua com a última coleta boa daquela fonte. O topo da página mostra, para cada fonte, se os dados são de hoje ou de qual dia. Na primeira execução, as coletas de 14/10/2026 em `brutos-iniciais/` servem de ponto de partida.

## Fontes automáticas e manuais

- **Zuk e Mega Leilões:** coletadas automaticamente todo dia.
- **Caixa e Leilão Imóvel (bancos e leiloeiras):** os dois sites bloqueiam acesso automático vindo de servidores (Caixa com CAPTCHA da Radware, Leilão Imóvel com desafio da Cloudflare). Não contornamos esses bloqueios. Essas fontes são atualizadas por coleta manual, feita pelo navegador do app do Claude, que grava o arquivo em `manuais/` e a data em `manuais/datas.json`. Na execução seguinte, o site passa a usar essa coleta.

## Instalação (uma vez, uns 10 minutos)

1. Crie uma conta em github.com, se ainda não tiver.
2. Crie um repositório novo, **público**, chamado `leiloes`. O GitHub Pages gratuito exige repositório público.
3. Envie os arquivos desta pasta para o repositório (com `git push` ou pelo site: **Add file → Upload files**; num repositório vazio, use o link *uploading an existing file*).
4. **Settings → Pages**: em *Build and deployment → Source*, escolha **GitHub Actions**.
5. **Settings → Actions → General**: em *Workflow permissions*, marque **Read and write permissions** e salve.
6. Aba **Actions → Atualizar imóveis → Run workflow**:
   - rode primeiro com **teste**, que confere em 2 a 3 minutos se cada fonte responde;
   - depois rode com **completo**, que leva de 40 a 90 minutos na primeira vez.
7. O site fica em `https://SEU-USUARIO.github.io/leiloes/`.

Daí em diante ele roda sozinho todo dia. Para forçar uma atualização, use **Run workflow** de novo.

## Arquivos

| Caminho | O que é |
|---|---|
| `site/index.html` | O app (busca, melhores ofertas, destaques, favoritos, fichas e assistente jurídico) |
| `coleta/fontes.py` | Coletores de cada fonte |
| `coleta/rodar.py` | Orquestra a coleta, a normalização e a geração dos dados do site |
| `coleta/normalizar.py` | Padroniza as fontes, remove vencidos e duplicados |
| `coleta/montar_painel.py` | Gera `site/dados/imoveis.js` e `detalhes.js` |
| `analise/destaques.json` | Análise de mercado dos destaques (preço do m² do bairro, riscos) |
| `brutos-iniciais/` | Primeira coleta, usada só na primeira execução |
| `.github/workflows/atualizar.yml` | O agendamento diário |

## Rodar no próprio computador

```
pip install -r coleta/requirements.txt
python coleta/rodar.py            # coleta tudo e gera site/dados
python coleta/rodar.py --teste    # só confere se as fontes respondem
python -m http.server -d site     # abre em http://localhost:8000
```

## Observações

- **Assistente jurídico:** neste site ele ainda não analisa editais, porque depende do Claude, que só está disponível na versão publicada dentro do Claude. Ligar o assistente aqui exige um servidor com chave da API da Anthropic (próxima etapa).
- **Termos de uso:** antes de divulgar o site ou cobrar por ele, confira os termos de uso de cada fonte.
- **Repositório parado:** o GitHub desliga agendamentos de repositórios sem nenhuma atividade por 60 dias. A própria rotina grava `ultima-atualizacao.js` a cada execução, o que mantém o repositório ativo.
