# Mancha de Inundação · MVP PIN2

Piloto de Presidente Getúlio, SC. Painel React, API FastAPI, worker com fila persistente, comparação lado a lado/sobreposição, administração e rastreabilidade.

O visual usa azul escuro e laranja com símbolo de proteção. O painel apresenta o objetivo do sistema e atalhos para acompanhar níveis, comparar imagens e consultar evidências.

O painel identifica a estação oficial [DCSC-00043 — SDC-SC Presidente Getúlio](https://monitoramento.defesacivil.sc.gov.br/estacao/DCSC-00043), da bacia SC - Rio Itajaí, e liga às leituras atuais publicadas pela Defesa Civil SC. O código e os metadados são reais; o MVP ainda não possui um serviço autorizado de coleta automática dessa estação. O gráfico do caso de 2023 usa somente cotas simuladas, identificadas como tal. A [cessão da área para instalação da estação na Rua Niterói Atlântico](https://portal.doe.sea.sc.gov.br/repositorio/2024/20241023/Jornal/22381.pdf) foi publicada em outubro de 2024; portanto não atribuímos ao sensor medições do episódio de 2023.

## Apresentação sem acesso ANA

O cenário representa as **enchentes de 16 e 17 de novembro de 2023**, documentadas na [Portaria 115 do TJSC](https://www2.tjsc.jus.br/web/tjsc/atos-normativos-e-suspensao-de-prazos-e-expediente/presidente-getulio/portaria_2023115.pdf). Usa **níveis e cota simulados** (300 cm, gatilho de 308 cm em 16/11/2023). As imagens são **reais do Sentinel-2 L2A**, obtidas via OAuth, Catalog e Process API do Copernicus:

- Antes: 05/11/2023; depois: 15/12/2023. As duas imagens têm 0% de nuvens na área de comparação, medidos pelo SCL. Mesmo tile T22JFR/órbita R038, área, resolução de saída e processamento.
- Recorte de cerca de 2,2 × 2,2 km na confluência dos rios Krauel e dos Índios.
- **Água destacada**: cor natural com ganho 3,5 e destaque azul por SCL=6 ou NDWI>0 com NIR<0,15, excluindo sombras/nuvens. **Cor natural**: mesmas cenas, sem destaque.
- Resolução nativa de 10–20 m. A saída de 1024 × 1024 amplia a visualização, sem acrescentar detalhe ao sensor. Trechos estreitos podem desaparecer; há falsos positivos. O azul não representa uma mancha oficial de inundação.
- O episódio é real, mas as cenas mostram referências de antes e depois, **não o pico da enchente**. As passagens de 15/11 e 20/11/2023 têm 100% de nuvens no tile T22JFR no catálogo. A referência posterior não certifica normalidade hidrológica: não há medições oficiais ANA. A interface mostra uma linha do tempo e as fontes oficiais.

As quatro imagens e o `manifest.json` ficam em `backend/app/assets/sentinel-2023/`, com os produtos reais, metadados retornados, evalscript e SHA-256. O par foi baixado e inspecionado visualmente. A demonstração funciona sem internet e sem novas chamadas ao Copernicus. Não há fallback para cenas artificiais. Imagens brancas, uniformes, transparentes ou arquivos com checksum divergente são rejeitados.

### Iniciar localmente

Com Python 3.12+ e Node, instale as dependências se necessário:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
npm --prefix frontend ci
```

Configure `.env` a partir de `.env.example`, preenchendo `ADMIN_EMAIL`, `ADMIN_PASSWORD` (mínimo 4 caracteres no MVP local) e `APP_SECRET` (mínimo 32). No ambiente já configurado, preserve o `.env` existente. As credenciais ficam apenas no servidor e o arquivo é ignorado pelo Git. API e worker carregam esse arquivo automaticamente no uso local.

```bash
.venv/bin/python scripts/run_local.py
```

Abra **http://localhost:5173**. Em **Admin**, digite apenas a senha individual `ADMIN_PASSWORD` do `.env`; o e-mail fica configurado no servidor. O acesso é mantido enquanto a sessão da aba estiver válida. O hash administrativo acompanha a senha configurada no próximo início da API. Depois, clique **Iniciar demonstração**. Após o worker concluir os dois jobs, abra **Eventos → Demonstrações → Ver comparação**. Use **Água destacada / Cor natural**, **Lado a lado / Sobrepor** ou **Ampliar imagem**. O reprocessamento preserva as versões anteriores.

O banco local fica em `pin2.db` na raiz e as imagens publicadas em `storage/`. Ctrl+C encerra os três serviços. Eventos são listados pela criação, para que o replay recém-criado apareça antes dos registros antigos. Demonstrações antigas com imagens artificiais permanecem no histórico identificadas como ilustrações legadas; crie uma demonstração nova para o par real.

### Atualizar o par diretamente no Sentinel

Preencha `CDSE_CLIENT_ID` e `CDSE_CLIENT_SECRET` no `.env` e execute:

```bash
.venv/bin/python scripts/prepare_sentinel_demo.py
```

O comando consulta e processa as duas datas de referência, confere os identificadores de produto devolvidos pelo processamento e só publica o manifesto após validar o par completo. As imagens ficam prontas para os próximos eventos. ANA não participa dessa operação. Crédito das imagens: Copernicus Sentinel data 2023, processado pelo Sentinel Hub / Copernicus Data Space Ecosystem.

## Fontes reais e Docker

O fluxo ANA + Sentinel-1 GRD permanece disponível em separado. Para ativá-lo, configure `ANA_IDENTIFICADOR`, `ANA_SENHA` e as credenciais CDSE, valide a estação em Admin e registre uma cota com fonte oficial, validade e responsável. A validação exige estação fluviométrica operante, área contendo a estação e cota válida medida nas últimas 48 horas. Sem essas condições, somente a demonstração é usada. Uma demonstração não desativa uma configuração ANA ativa.

```bash
docker compose up --build -d
```

O `.env` também precisa conter as senhas PostgreSQL/MinIO. Abra **http://localhost:8080**; documentação em `/api/docs`; console MinIO em `http://localhost:9001`. PostgreSQL/PostGIS e MinIO persistem em volumes. Encerre com `docker compose down`, preservando os volumes. Docker não foi exercitado nesta correção.

O worker registra tentativas, aplica espera crescente, retoma leases vencidos e permite reprocessar eventos. As imagens têm checksum e versões. Horários ANA sem fuso são interpretados como America/Sao_Paulo. O acesso ANA e a coleta hidrométrica real não foram validados, pois não há credenciais ANA disponíveis.

## Validação

```bash
(cd backend && ../.venv/bin/pytest -q)
npm --prefix frontend run build
SMOKE_API_PORT=8001 SMOKE_WEB_PORT=5174 .venv/bin/python scripts/smoke_local.py
```

O smoke test usa banco e armazenamento temporários, inicia os três serviços, testa login, demonstração, publicação, imagens e reprocessamento e encerra seus processos. Não depende de contas externas.

Referências: [Sentinel-2 L2A](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html), [autenticação CDSE](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html), [Sentinel-1 GRD](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html).
