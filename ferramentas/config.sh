# Configuração do repositório de atualizações do Simba OS (lida pelas ferramentas)
GH_USER="${SIMBA_GH_USER:-}"          # preenchido por `ferramentas/publicar` na primeira vez (gh api user)
GH_REPO="simba-os"
REPO_NOME="simba-os"                  # nome da seção no pacman.conf e do banco (simba-os.db)
RELEASE_TAG="repo"                    # release "rolante" que guarda os pacotes
CHAVE=""                              # impressão digital da chave de assinatura (ferramentas/criar-chave)
PACOTES=(simba simba-apps simba-draco simba-keyring)
