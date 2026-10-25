# Monitoramento fluvial · Presidente Getúlio

MVP acadêmico em uma página: nível público do Rio dos Índios, gatilhos indicativos configuráveis pela estação DCSC-00043, comparação das passagens Sentinel-2 mais recentes e busca de passagens por período. O episódio de novembro de 2023 aparece somente como uma curiosidade histórica em janela própria.

## O que é real

- **Nível do rio:** estação [DCSC-00043](https://monitoramento.defesacivil.sc.gov.br/estacao/DCSC-00043), reproduzida pelo [portal municipal da Defesa Civil](https://pdc.presidentegetulio.sc.gov.br/monitoramento). O painel consulta a base pública em modo somente leitura a cada minuto. O horário mostrado é o de publicação (created_at) porque o horário do sensor espelhado apresenta uma divergência de três horas. Após 30 minutos, a leitura é marcada como antiga. Esta fonte é **DCSC, não ANA**.
- **Imagens recentes:** catálogo e Process API do Copernicus Data Space Ecosystem, coleção Sentinel-2 L2A. O sistema procura passagens do tile T22JFR, órbita R038, no mesmo recorte dos rios Krauel e dos Índios. A seleção exige no máximo 10% de nuvens, sombra, neve ou pixels inválidos no recorte inteiro **e no corredor GIS dos rios**, além de água visível no processamento. O corredor vem dos eixos dos rios cartografados por [© OpenStreetMap contributors (ODbL)](https://www.openstreetmap.org/copyright), armazenados localmente no projeto. Duas cenas completas de datas diferentes são publicadas juntas, com produto, data e checksum. O worker verifica o catálogo automaticamente ao iniciar e a cada seis horas; se não houver um par novo, mantém o último par validado.
- **Transparência temporal:** o painel informa a última passagem catalogada, mesmo encoberta, e oferece um link separado para abrir sua prévia. Ela não entra na comparação. As datas das duas imagens utilizáveis mudam quando novas passagens passam pela verificação.
- **Busca pública por período e coordenadas:** informe até 60 dias e, opcionalmente, latitude/longitude. O servidor consulta Sentinel-2 L2A em um recorte de aproximadamente 2 km ao redor do ponto, incluindo até 15 dias antes e depois. Sem coordenadas, usa a área piloto. Para cada dia, prefere o produto que cobre todo o recorte e só então compara a nebulosidade do tile. Escolha até duas datas para examinar as imagens lado a lado, ampliar em 1×/2×/4× na página e baixar o PNG somente quando necessário. A inspeção informa separadamente nuvens no tile, nuvens locais, falta de dados e pixels sem leitura confiável. O limite de aceitação é 10% de pixels sem leitura confiável no recorte; na área piloto há também a verificação do corredor dos rios.
- **História de 2023:** ocorrência documentada pelo [TJSC](https://www2.tjsc.jus.br/web/tjsc/atos-normativos-e-suspensao-de-prazos-e-expediente/presidente-getulio/portaria_2023115.pdf), com cenas reais de 05/11 e 15/12/2023. As cotas do replay são **simuladas**. Nenhuma imagem representa o pico da enchente nem prova normalização hidrológica. A curiosidade funciona sem registrar um evento de demonstração no banco.

O azul das imagens recentes e pesquisadas combina observação Sentinel-2 (SCL, NDWI e MNDWI) com eixos GIS de cursos d’água. Água de alta confiança do satélite pode ser destacada em qualquer lugar; detecções espectrais fracas só entram perto de um curso d’água mapeado. A linha GIS, sozinha, não cria pixels de água. Para coordenadas pesquisadas, o servidor consulta rios e ruas nomeadas do OpenStreetMap, armazena a resposta por 30 dias e indica quando a cartografia está indisponível. Nesse caso a análise espectral ainda funciona. A classificação não é uma mancha oficial de inundação. A resolução nativa Sentinel-2 é 10–20 m; a página não emite alertas oficiais. Referências: [bandas/SCL Sentinel-2](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html), [licença OSM](https://www.openstreetmap.org/copyright).

Para atualizar os eixos GIS locais da área piloto: `PYTHONPATH=backend .venv/bin/python scripts/update_rivers.py`. O GeoJSON está em `backend/app/assets/pilot_rivers.geojson` e a licença em `backend/app/assets/PILOT_RIVERS_LICENSE.md`. Nas buscas, `GET /api/gis/area?lat=...&lon=...` retorna os cursos d’água e trechos de ruas nomeadas do recorte, com atribuição e estado da fonte.

Cada imagem aprovada pode ser ampliada **interativamente na página** e oferece download PNG original, 2× ou 4×. O botão **Focar no rio** aproxima o trecho mapeado em 2×. Nas comparações lado a lado, **Sincronizar zoom e posição** mantém as duas datas no mesmo ponto ao arrastar ou ampliar; desligado, cada uma pode ser examinada separadamente. O servidor suaviza o terreno com Lanczos e mantém o contorno da água classificada sem interpolar sua posição; o sensor não passa a ter mais detalhe. A imagem original e seu checksum permanecem intactos. Nas buscas, é possível marcar trechos de rua no mapa ou digitar uma referência local. As anotações ficam como rascunho no navegador por produto e recorte, com exportação CSV; são informação manual para verificação em campo, não detecção automática de impacto. Passagens rejeitadas não ganham download ampliado.

Ao examinar uma imagem, **Contexto Google Maps** abre a vista de satélite do mesmo local em um painel separado. A captura exibida pelo Google pode ter outra data, que a API não informa; ela serve para orientação visual, não para completar ou substituir os pixels Sentinel da passagem escolhida. O destaque de água, os registros por data e o PNG exportado continuam baseados exclusivamente no Sentinel e no GIS do sistema. Sem chave Google, o painel oferece um link para abrir o mesmo ponto no Google Maps. A integração opcional usa a [Maps Embed API](https://developers.google.com/maps/documentation/embed/embedding-map), sem copiar nem armazenar imagens Google.

## Rodar no computador

Requisitos: Python 3.12+, Node.js e npm. Na raiz do repositório:

    python3 -m venv .venv
    .venv/bin/pip install -r backend/requirements.lock
    npm --prefix frontend ci
    cp .env.example .env

No .env, configure ADMIN_EMAIL, ADMIN_PASSWORD e APP_SECRET (mínimo de 32 caracteres). Para as leituras e imagens atuais, configure PDC_SUPABASE_ANON_KEY, CDSE_CLIENT_ID e CDSE_CLIENT_SECRET. O .env local desta entrega já está configurado; preserve-o. Ele é ignorado pelo Git. Para uma publicação permanente, obtenha um meio estável de acesso à base municipal com seus responsáveis.

Para exibir o mapa Google **dentro** da página, crie uma chave em [Google Maps Platform → Credentials](https://console.cloud.google.com/google/maps-apis/credentials), ative apenas **Maps Embed API** e restrinja a chave a **Websites** com os endereços usados (`http://localhost:5173/*`, `http://localhost:5180/*`, `http://localhost:8080/*` e o domínio público) e à própria Maps Embed API. Coloque-a como `VITE_GOOGLE_MAPS_EMBED_API_KEY` no `.env` e reinicie o site. Essa chave aparece no navegador por definição; as restrições de domínio e API são necessárias. O Google exige conta de faturamento habilitada, embora [o uso da Maps Embed API seja gratuito](https://developers.google.com/maps/documentation/embed/usage-and-billing). Não habilite outras APIs nesta chave. Sem ela, o link externo continua funcional.

    .venv/bin/python scripts/run_local.py

Abra **http://localhost:5173**. O comando inicia API, worker e Vite. Ctrl+C encerra os três. O banco local é pin2.db; as imagens baixadas ficam em storage/. O worker procura automaticamente novas cenas. Para forçar uma consulta manual ao Copernicus:

Se as portas padrão estiverem ocupadas por outra cópia do projeto, escolha outras sem alterar o código: `PIN2_API_PORT=8010 PIN2_WEB_PORT=5180 .venv/bin/python scripts/run_local.py`, e abra `http://localhost:5180`.

    .venv/bin/python scripts/refresh_sentinel_latest.py

Use **Admin** na própria página para entrar com a senha configurada no servidor. A página pública dispensa login. Em 22/10/2026, o histórico local anterior de configurações, eventos, leituras, jobs e auditoria foi zerado e a configuração DCSC foi ativada como **v1**. O histórico de commits do GitHub não foi reescrito. O cenário histórico de 2023 continua disponível no pop-up.

### Gatilhos sem ANA

O Admin pode ativar a fonte **Defesa Civil DCSC-00043** sem credenciais ANA. A configuração valida duas leituras recentes e fixa o recorte do Rio dos Índios. Para uma nova configuração, o Admin deve escolher **atenção, alerta, transbordamento/inundação, emergência ou outra referência técnica** e informar o valor local em centímetros, documento/estudo de origem, responsável e data de validade. Nenhum valor é preenchido como cota oficial para Presidente Getúlio. As categorias são opções de cadastro, baseadas nas [referências de níveis descritas pela ANA](https://www.gov.br/ana/pt-br/assuntos/noticias-e-eventos/noticias/ana-atualiza-aplicativo-que-permite-acompanhar-chuvas-rios-e-reservatorios/); a [COBRADE](https://www.gov.br/mdr/pt-br/centrais-de-conteudo/publicacoes/protecao-e-defesa-civil-sedec/DOCU_cobrade2.pdf) classifica o tipo de desastre e **não** fornece a cota de uma estação. O valor de exemplo de configurações anteriores fica no histórico; a coleta continua, mas novos gatilhos baseados nesse exemplo ficam suspensos até um novo cadastro local. A coleta roda a cada cinco minutos por padrão. Na ativação, a leitura vigente vira ponto de partida, sem criar um evento retroativo. A partir de então, uma leitura abaixo seguida de **duas leituras consecutivas iguais/acima** da referência, com intervalos de até 30 minutos, cria um registro indicativo, com valor, horário de publicação, fonte e versão da configuração. Duas leituras subsequentes abaixo encerram o registro. Leituras atrasadas ou indisponíveis não criam eventos. Cenas de satélite são processadas separadamente.

**Coletar agora** antecipa a próxima consulta da estação; o worker executa a tarefa em segundo plano e a página pode ser fechada. A coleta pode inserir zero leituras novas quando a fonte ainda não publicou outro dado. O botão não cria um evento artificial: um registro aparece apenas quando as leituras satisfazem o gatilho acima. Em **Processamento**, veja a data da tarefa, a data da última tentativa, a quantidade de leituras novas, a última cota recebida e os eventos criados. Uma falha é tentada novamente até três vezes; após a terceira, a tarefa fica parada e exige **Coletar agora** ou a ativação de uma nova configuração para reiniciar. A mensagem da última falha permanece no histórico das tentativas.

Para integração com a interface: `POST /api/admin/collect` retorna `job_id`, `status`, `scheduled_for` e `already_running` imediatamente. `GET /api/admin/jobs` retorna `created_at`, `last_attempt_at`, `last_attempt_status`, `last_error` e `last_result` (quando a última tentativa teve sucesso), com `inserted`, `events_created`, `latest_observed_at`, `latest_level_cm` e `threshold_cm`. Ambos exigem autenticação de Admin. O estado recorrente `PENDENTE` após uma tentativa bem-sucedida indica que a próxima coleta foi agendada, não que a anterior falhou.

A opção ANA permanece disponível para quem tiver credenciais e cota documentada. Neste ambiente, `ANA_IDENTIFICADOR` e `ANA_SENHA` estão vazios, então só essa opção fica bloqueada. O código 83372100 no formulário ANA é didático e não foi verificado nesta instalação.

## Eventos automáticos e hospedagem

As leituras DCSC e o par recente de satélite são independentes de um evento de cheia. A seção “Eventos monitorados” recebe um registro DCSC **após o gatilho**, mesmo enquanto as imagens estão pendentes ou falharam; mostra esse estado com transparência. O fluxo de eventos usa Sentinel-1 GRD, capaz de observar sob nuvens; o par recente e a busca pública usam Sentinel-2 L2A, mais legível visualmente. Se ainda não houve cruzamento, a seção fica vazia. A configuração DCSC é indicativa e não substitui decisão ou alerta da Defesa Civil.

Para executar com PostgreSQL/PostGIS e MinIO:

    docker compose up --build -d

Configure também POSTGRES_PASSWORD, S3_ACCESS_KEY e S3_SECRET_KEY no .env. Abra **http://localhost:8080**; a documentação da API está em /api/docs. API e worker compartilham o armazenamento MinIO. Para acesso público contínuo, hospede os serviços em um servidor com domínio, HTTPS, backups do banco/objetos, supervisão dos containers e credenciais próprias. docker compose down preserva os volumes.

### Publicar gratuitamente sem manter o Codex aberto

**Roteiro completo, sem pesquisa adicional:** [GUIA_PUBLICACAO.md](GUIA_PUBLICACAO.md).

O programa **não depende do Codex**. No computador, `docker compose up --build -d` deixa API, worker e página em segundo plano; o computador e o Docker precisam permanecer ligados. Para acesso público contínuo, este repositório inclui [compose.free.yaml](compose.free.yaml), que roda API, worker, página e HTTPS/Caddy em uma VM própria, com banco SQLite e imagens em um volume persistente. O compose reinicia os processos automaticamente. A versão online parte de um banco novo: depois do primeiro acesso, entre no Admin e cadastre a cota validada para a estação DCSC-00043, com tipo, valor e fonte local. Não copie a senha local `1234` para uma publicação pública.

Uma possibilidade sem mensalidade é uma [VM Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) e um nome [DuckDNS gratuito](https://www.duckdns.org/faqs.jsp). **É necessário criar essas contas; ainda não existe uma URL pública desta instalação.** Na Oracle, escolha uma VM Ampere A1 com etiqueta *Always Free*, dentro da cota da sua conta, Ubuntu 24.04 ARM, IP público e chave SSH. A capacidade da região pode impedir a criação imediata; confira as condições atuais no painel da Oracle. Libere entrada TCP 80 e 443 na rede da VM e mantenha 22 apenas para administração. No DuckDNS, crie um subdomínio e aponte-o para o IP público da VM.

Na VM, instale Docker Engine e o plugin Compose seguindo o [guia oficial para Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Então execute:

```bash
git clone https://github.com/LuizAlberth/PIN2-Luiz-e-Thaiane.git
cd PIN2-Luiz-e-Thaiane
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Preencha `SITE_DOMAIN` com o subdomínio DuckDNS **sem** `https://`. Copie `PDC_SUPABASE_ANON_KEY` e `CDSE_CLIENT_ID` do seu `.env` local; **revogue e substitua o segredo Copernicus que apareceu na conversa**. Configure `ADMIN_EMAIL`, uma **nova senha exclusiva de pelo menos 16 caracteres** e `APP_SECRET` com pelo menos 32 caracteres; `openssl rand -hex 32` gera um segredo adequado. Nunca envie `.env.production` ao GitHub. Depois:

```bash
sudo docker compose --env-file .env.production -f compose.free.yaml up -d --build
sudo docker compose --env-file .env.production -f compose.free.yaml ps
sudo docker compose --env-file .env.production -f compose.free.yaml logs --tail=80 api worker caddy
```

Abra `https://SEU-SUBDOMINIO.duckdns.org`. O Caddy solicita e renova o certificado HTTPS automaticamente quando DNS e portas 80/443 estão corretos ([documentação](https://caddyserver.com/docs/automatic-https)). No Admin, selecione **Defesa Civil DCSC-00043**, cadastre o tipo e a cota local documentada e clique **Validar e ativar**. O worker seguirá coletando e verificando imagens sem navegador aberto. Para atualizar o programa, use `git pull --ff-only` e repita `sudo docker compose ... up -d --build`; os volumes preservam banco, imagens e certificados. `docker compose down -v` apaga esses volumes e não deve ser usado numa atualização.

Faça cópias do banco e das imagens periodicamente com `sudo ./scripts/backup_free.sh`; os arquivos aparecem em `backups/` na VM. Guarde outra cópia fora da VM. Monitore `logs` e o espaço em disco. A gratuidade depende de permanecer dentro das cotas da Oracle e de disponibilidade da VM; a Oracle informa que recursos ociosos Always Free podem ser retomados. A alternativa Render Free não serve para este fluxo contínuo: o serviço hiberna e perde arquivos locais em reinícios ([limitações oficiais](https://render.com/docs/free)).

## Validação

    (cd backend && ../.venv/bin/pytest -q)
    npm --prefix frontend run build
    SMOKE_API_PORT=8001 SMOKE_WEB_PORT=5174 .venv/bin/python scripts/smoke_local.py

O teste ponta a ponta usa banco e armazenamento temporários e não depende de contas externas. Referências técnicas: [Sentinel-2 L2A](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html), [autenticação CDSE](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html).
