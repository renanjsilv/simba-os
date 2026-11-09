# Configuração do repositório de atualizações do Simba OS (lida pelas ferramentas)
GH_USER="${SIMBA_GH_USER:-renanjsilv}"
GH_REPO="simba-os"
REPO_NOME="simba-os"                  # nome da seção no pacman.conf e do banco (simba-os.db)
RELEASE_TAG="repo"                    # release "rolante" que guarda os pacotes
CHAVE="1B07ADB55D27A3406FF4E06A45C5AC8F8327CD6B"                              # impressão digital da chave de assinatura
PACOTES=(simba simba-apps simba-draco simba-keyring)
