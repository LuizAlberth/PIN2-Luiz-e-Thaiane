# Publicação gratuita: roteiro completo

Este projeto usa **uma única VM**, sem balanceador, autoscaling ou criação automática de outra VM. API, worker, site e Caddy são quatro contêineres na mesma máquina. O arquivo [compose.free.yaml](compose.free.yaml) limita memória e CPU dos contêineres. Sob carga excessiva, o site pode ficar lento ou indisponível; a aplicação não compra capacidade automaticamente.

## 1. Entenda a cobrança antes de criar a conta

Crie uma conta **Oracle Free Tier** e **não clique em Upgrade/Pay As You Go**. A [Oracle informa](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) que o cartão não é cobrado sem upgrade. Durante o teste grátis, serviços fora do Always Free podem consumir os créditos promocionais; selecione somente recursos com o selo **Always Free Eligible**. Na conta paga, o que excede as cotas gratuitas pode ser cobrado. [Orçamentos são alertas, não bloqueios de gastos](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/create-budget.htm).

No [cadastro Oracle Free Tier](https://www.oracle.com/cloud/free/), escolha com cuidado a **região principal**. A VM Always Free deve ficar nessa região. Se não houver capacidade A1 nela, tente outro domínio de disponibilidade ou aguarde; a Oracle não garante disponibilidade imediata.

## 2. Crie uma VM

No Console Oracle: **Compute → Instances → Create instance**. Use:

- Nome: `pin2-mancha`.
- Imagem: **Ubuntu 24.04**, arquitetura ARM.
- Shape: **VM.Standard.A1.Flex**, selo **Always Free Eligible**, **2 OCPU e 12 GB RAM** no total.
- Disco de inicialização: padrão, cerca de **50 GB**, também com selo Always Free.
- Rede: VCN/sub-rede **pública**, atribuir **IPv4 público**.
- SSH: gere e **baixe a chave privada**. Guarde-a no seu computador; não a envie pelo chat nem a coloque no GitHub.

O limite da A1 para conta Always Free é 2 OCPU/12 GB no total; outras VMs e discos consomem a mesma cota ([limites oficiais](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)). Anote o **IP público** da instância.

Na Oracle, abra **Networking → Virtual Cloud Networks → sua VCN → Security Lists → lista da sub-rede pública → Add Ingress Rules**. Crie duas regras *stateful*, origem `0.0.0.0/0`, protocolo TCP, portas de destino **80** e **443**. Deixe a porta 22 apenas para SSH. Não abra 8000, 5432 ou 9000; API e armazenamento ficam internos.

## 3. Crie o endereço gratuito

Em [DuckDNS](https://www.duckdns.org/), entre na conta, crie um subdomínio (por exemplo `pin2-getulio`) e defina o **IPv4 público** da VM. O endereço será `pin2-getulio.duckdns.org`. Se o IP da VM mudar após parada/recriação, atualize-o no DuckDNS. DNS pode levar alguns minutos para propagar.

## 4. Entre na VM pelo terminal do seu computador

No Linux/macOS, substitua o nome da chave e o IP pelos seus:

```bash
chmod 600 ~/Downloads/SUA_CHAVE.key
ssh -i ~/Downloads/SUA_CHAVE.key ubuntu@SEU_IP_PUBLICO
```

No Windows, use PowerShell com a chave baixada: `ssh -i "C:\caminho\SUA_CHAVE.key" ubuntu@SEU_IP_PUBLICO`. O usuário da imagem Ubuntu Oracle costuma ser `ubuntu`; confirme no detalhe da imagem se o Console mostrar outro.

## 5. Instale Docker na VM

Execute **na VM**. Estes são os comandos da [documentação oficial do Docker para Ubuntu](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

## 6. Configure e inicie o sistema

Ainda na VM:

```bash
git clone https://github.com/LuizAlberth/PIN2-Luiz-e-Thaiane.git
cd PIN2-Luiz-e-Thaiane
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Preencha **todas** as linhas do arquivo, sem aspas:

```dotenv
SITE_DOMAIN=SEU_SUBDOMINIO.duckdns.org
ADMIN_EMAIL=SEU_EMAIL
ADMIN_PASSWORD=UMA_SENHA_NOVA_COM_PELO_MENOS_16_CARACTERES
APP_SECRET=SEGREDO_ALEATORIO_COM_PELO_MENOS_32_CARACTERES
PDC_SUPABASE_ANON_KEY=VALOR_DO_ENV_LOCAL
CDSE_CLIENT_ID=VALOR_DO_ENV_LOCAL
CDSE_CLIENT_SECRET=SEGREDO_NOVO_DO_COPERNICUS
```

`PDC_SUPABASE_ANON_KEY` e `CDSE_CLIENT_ID` estão no `.env` do seu computador. O segredo Copernicus anterior foi compartilhado na conversa: **revogue-o no portal Copernicus, gere outro e use apenas o novo**. Não publique nenhum desses valores. Gere `APP_SECRET` na VM com `openssl rand -hex 32` e copie o resultado para o arquivo. A senha `1234` não serve para publicação. Salve no nano com `Ctrl+O`, `Enter`, `Ctrl+X`.

```bash
sudo docker compose --env-file .env.production -f compose.free.yaml up -d --build
sudo docker compose --env-file .env.production -f compose.free.yaml ps
```

Abra `https://SEU_SUBDOMINIO.duckdns.org`. Caddy obtém o certificado automaticamente quando DNS e portas 80/443 funcionam. A primeira compilação pode demorar alguns minutos. No painel **Admin**, entre com sua senha e ative a fonte DCSC-00043, depois de revisar o limiar experimental com a equipe.

## 7. Operação sem o Codex

O Docker sobe após reiniciar a VM, e os contêineres têm `restart: unless-stopped`. O worker coleta as leituras e verifica novas passagens automaticamente. Para verificar:

```bash
cd ~/PIN2-Luiz-e-Thaiane
sudo docker compose --env-file .env.production -f compose.free.yaml ps
sudo docker compose --env-file .env.production -f compose.free.yaml logs --tail=80 api worker caddy
```

Para atualizar o código após novos commits:

```bash
cd ~/PIN2-Luiz-e-Thaiane
git pull --ff-only
sudo docker compose --env-file .env.production -f compose.free.yaml up -d --build
```

Para salvar banco e imagens:

```bash
cd ~/PIN2-Luiz-e-Thaiane
sudo ./scripts/backup_free.sh
```

Copie também a pasta `backups/` para outro computador: se a VM ou o disco forem perdidos, um backup na própria VM não basta. Nunca use `docker compose down -v` para atualizar: `-v` apaga os volumes persistentes.

Se o site não abrir: confirme que a VM está **Running**, que o DNS aponta para o IP atual, que as portas 80/443 estão liberadas e consulte os `logs` acima. Se a Oracle não liberar uma A1 Always Free na região, não faça upgrade por impulso: espere capacidade ou use o sistema localmente enquanto decide outra hospedagem.
