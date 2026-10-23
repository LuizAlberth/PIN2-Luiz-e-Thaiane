# Monitoramento fluvial · Presidente Getúlio

MVP acadêmico em uma página: nível público do Rio dos Índios, gatilhos indicativos configuráveis pela estação DCSC-00043, comparação das passagens Sentinel-2 mais recentes e busca de passagens por período. O episódio de novembro de 2023 aparece somente como uma curiosidade histórica em janela própria.

## O que é real

- **Nível do rio:** estação [DCSC-00043](https://monitoramento.defesacivil.sc.gov.br/estacao/DCSC-00043), reproduzida pelo [portal municipal da Defesa Civil](https://pdc.presidentegetulio.sc.gov.br/monitoramento). O painel consulta a base pública em modo somente leitura a cada minuto. O horário mostrado é o de publicação (created_at) porque o horário do sensor espelhado apresenta uma divergência de três horas. Após 30 minutos, a leitura é marcada como antiga. Esta fonte é **DCSC, não ANA**.
- **Imagens recentes:** catálogo e Process API do Copernicus Data Space Ecosystem, coleção Sentinel-2 L2A. O sistema procura passagens do tile T22JFR, órbita R038, no mesmo recorte dos rios Krauel e dos Índios. A seleção exige no máximo 10% de nuvens, sombra, neve ou pixels inválidos no recorte inteiro **e no corredor do rio**, além de água visível no processamento. Duas cenas completas de datas diferentes são publicadas juntas, com produto, data e checksum. O worker verifica o catálogo automaticamente ao iniciar e a cada seis horas; se não houver um par novo, mantém o último par validado.
- **Transparência temporal:** o painel informa também a última passagem catalogada, mesmo que esteja encoberta, e oferece um link separado para abrir sua prévia. Essa prévia nunca entra na comparação. Na verificação de 22/10/2026, a passagem mais recente era de 20/10 (89,9% de nuvens no tile e 100% do recorte encoberto); as duas imagens utilizáveis mais recentes eram de 09/07 e 19/07/2026. Essas datas mudam quando uma passagem nova atender à validação.
- **Busca pública por período:** informe datas de até 60 dias. O servidor consulta o catálogo Sentinel-2 L2A para o recorte fixo e inclui até 15 dias antes e depois. Ele mostra a data, a proximidade ao período e as nuvens do **tile inteiro**. Ao abrir a prévia, o servidor processa a imagem e verifica até 10% de pixels encobertos no recorte e no corredor do rio, além de água visível; uma cena rejeitada não aparece como imagem utilizável. A primeira prévia pode levar alguns segundos. O resultado não prova inundação.
- **História de 2023:** ocorrência documentada pelo [TJSC](https://www2.tjsc.jus.br/web/tjsc/atos-normativos-e-suspensao-de-prazos-e-expediente/presidente-getulio/portaria_2023115.pdf), com cenas reais de 05/11 e 15/12/2023. As cotas do replay são **simuladas**. Nenhuma imagem representa o pico da enchente nem prova normalização hidrológica. A curiosidade funciona sem registrar um evento de demonstração no banco.

O azul das imagens é um destaque de possível água por SCL/NDWI, não uma mancha oficial de inundação. A resolução nativa do Sentinel-2 é de 10–20 m: o arquivo exibido em 1024 × 1024 não acrescenta detalhes ao sensor. A página não emite alertas oficiais.

## Rodar no computador

Requisitos: Python 3.12+, Node.js e npm. Na raiz do repositório:

    python3 -m venv .venv
    .venv/bin/pip install -r backend/requirements.lock
    npm --prefix frontend ci
    cp .env.example .env

No .env, configure ADMIN_EMAIL, ADMIN_PASSWORD e APP_SECRET (mínimo de 32 caracteres). Para as leituras e imagens atuais, configure PDC_SUPABASE_ANON_KEY, CDSE_CLIENT_ID e CDSE_CLIENT_SECRET. O .env local desta entrega já está configurado; preserve-o. Ele é ignorado pelo Git. Para uma publicação permanente, obtenha um meio estável de acesso à base municipal com seus responsáveis.

    .venv/bin/python scripts/run_local.py

Abra **http://localhost:5173**. O comando inicia API, worker e Vite. Ctrl+C encerra os três. O banco local é pin2.db; as imagens baixadas ficam em storage/. O worker procura automaticamente novas cenas. Para forçar uma consulta manual ao Copernicus:

Se as portas padrão estiverem ocupadas por outra cópia do projeto, escolha outras sem alterar o código: `PIN2_API_PORT=8010 PIN2_WEB_PORT=5180 .venv/bin/python scripts/run_local.py`, e abra `http://localhost:5180`.

    .venv/bin/python scripts/refresh_sentinel_latest.py

Use **Admin** na própria página para entrar com a senha configurada no servidor. A página pública dispensa login. Em 22/10/2026, o histórico local anterior de configurações, eventos, leituras, jobs e auditoria foi zerado e a configuração DCSC foi ativada como **v1**. O histórico de commits do GitHub não foi reescrito. O cenário histórico de 2023 continua disponível no pop-up.

### Gatilhos sem ANA

O Admin pode ativar a fonte **Defesa Civil DCSC-00043** sem credenciais ANA. A configuração valida duas leituras recentes e fixa o recorte do Rio dos Índios. O exemplo local usa **300 cm**, descritos explicitamente como **parâmetro experimental do projeto**; não é uma cota oficial de alerta. O Admin pode alterar essa referência com a equipe responsável. A coleta roda a cada cinco minutos por padrão. Na ativação, a leitura vigente vira ponto de partida, sem criar um evento retroativo. A partir de então, uma leitura abaixo seguida de **duas leituras consecutivas iguais/acima** da referência, com intervalos de até 30 minutos, cria um registro indicativo, com valor, horário de publicação, fonte e versão da configuração. Duas leituras subsequentes abaixo encerram o registro. Leituras atrasadas ou indisponíveis não criam eventos. O worker volta a tentar a coleta após falhas; cenas de satélite são processadas separadamente.

A opção ANA permanece disponível para quem tiver credenciais e cota documentada. Neste ambiente, `ANA_IDENTIFICADOR` e `ANA_SENHA` estão vazios, então só essa opção fica bloqueada. O código 83372100 no formulário ANA é didático e não foi verificado nesta instalação.

## Eventos automáticos e hospedagem

As leituras DCSC e o par recente de satélite são independentes de um evento de cheia. A seção “Eventos monitorados” recebe um registro DCSC **após o gatilho**, mesmo enquanto as imagens estão pendentes ou falharam; mostra esse estado com transparência. O fluxo de eventos usa Sentinel-1 GRD, capaz de observar sob nuvens; o par recente e a busca pública usam Sentinel-2 L2A, mais legível visualmente. Se ainda não houve cruzamento, a seção fica vazia. A configuração DCSC é indicativa e não substitui decisão ou alerta da Defesa Civil.

Para executar com PostgreSQL/PostGIS e MinIO:

    docker compose up --build -d

Configure também POSTGRES_PASSWORD, S3_ACCESS_KEY e S3_SECRET_KEY no .env. Abra **http://localhost:8080**; a documentação da API está em /api/docs. API e worker compartilham o armazenamento MinIO. Para acesso público contínuo, hospede os serviços em um servidor com domínio, HTTPS, backups do banco/objetos, supervisão dos containers e credenciais próprias. docker compose down preserva os volumes.

## Validação

    (cd backend && ../.venv/bin/pytest -q)
    npm --prefix frontend run build
    SMOKE_API_PORT=8001 SMOKE_WEB_PORT=5174 .venv/bin/python scripts/smoke_local.py

O teste ponta a ponta usa banco e armazenamento temporários e não depende de contas externas. Referências técnicas: [Sentinel-2 L2A](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html), [autenticação CDSE](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html).
