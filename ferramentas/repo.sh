# repo.sh — envio de um repositório pacman para um release do GitHub (lido por publicar e promover).
#
# Canais:  [simba-os-testing] → release "repo-testing"   (publicar)
#          [simba-os]         → release "repo"           (promover, ou publicar --direto)

TESTE_TAG="repo-testing"
TESTE_NOME="simba-os-testing"

checar_gh() {
  command -v gh >/dev/null || { echo "instale o GitHub CLI: sudo pacman -S github-cli" >&2; exit 1; }
  gh auth status >/dev/null 2>&1 || { echo "entre no GitHub antes: gh auth login" >&2; exit 1; }
  [[ -n $CHAVE ]] || { echo "crie a chave de assinatura antes: ferramentas/criar-chave" >&2; exit 1; }
}

# enviar_repo <tag> <nome do banco> <pasta com os pacotes assinados>
enviar_repo() {
  local tag=$1 nome=$2 pasta=$3
  (
    cd "$pasta"
    rm -f "$nome".db* "$nome".files*
    # o GitHub troca ":" por "." no nome dos arquivos (época, ex.: brave-bin-1:1.2-1): renomeia
    # antes do repo-add, para o banco já apontar para o nome que o GitHub vai guardar
    for f in *:*.pkg.tar.zst *:*.pkg.tar.zst.sig; do [[ -e $f ]] && mv -f "$f" "${f//:/.}"; done
    # só a versão mais nova de cada pacote entra no banco
    local mais_novos p f
    mais_novos=$(for p in "${PACOTES[@]}" "${PUBLICAR_AUR[@]}"; do
      ls "$p"-[0-9]*.pkg.tar.zst 2>/dev/null | grep -v -- '-debug-' | sort -V | tail -1; done)
    for f in $mais_novos; do [[ -s $f.sig ]] || { echo "sem assinatura: $f" >&2; exit 1; }; done
    # trava: nunca publicar (nem limpar o release) com uma lista incompleta
    local esperados=$(( ${#PACOTES[@]} + ${#PUBLICAR_AUR[@]} ))
    [[ $(wc -w <<<"$mais_novos") -eq $esperados ]] || {
      echo "lista de pacotes incompleta ($(wc -w <<<"$mais_novos") de $esperados): nada foi enviado" >&2; exit 1; }
    repo-add -s -k "$CHAVE" "$nome.db.tar.zst" $mais_novos
    # o GitHub não guarda links: troca os links .db/.files por cópias
    for f in "$nome".db "$nome".files "$nome".db.sig "$nome".files.sig; do
      [[ -L $f ]] && cp --remove-destination "$(readlink -f "$f")" "$f"
    done
    if ! gh release view "$tag" -R "$GH_USER/$GH_REPO" >/dev/null 2>&1; then
      if [[ $tag == "$TESTE_TAG" ]]; then
        gh release create "$tag" -R "$GH_USER/$GH_REPO" --title "Repositório de pacotes (teste)" --prerelease \
          --notes "Canal de teste do Simba OS: atualizações antes de irem para todo mundo. Só para quem testa (simba-canal teste)." --latest=false
      else
        gh release create "$tag" -R "$GH_USER/$GH_REPO" --title "Repositório de pacotes" \
          --notes "Pacotes do Simba OS para o pacman. Não baixe à mão: use a seção [$nome] do pacman.conf." --latest=false
      fi
    fi
    local arquivos=($mais_novos $(for f in $mais_novos; do echo "$f.sig"; done) "$nome".db "$nome".db.sig "$nome".files "$nome".files.sig)
    gh release upload "$tag" -R "$GH_USER/$GH_REPO" --clobber "${arquivos[@]}"
    # tira do release pacotes de versões antigas
    local a
    for a in $(gh release view "$tag" -R "$GH_USER/$GH_REPO" --json assets -q '.assets[].name'); do
      [[ $a == *.pkg.tar.zst* ]] || continue
      printf '%s\n' "${arquivos[@]}" | grep -qxF "$a" || gh release delete-asset "$tag" "$a" -R "$GH_USER/$GH_REPO" -y
    done
    echo "✓ [$nome] publicado: https://github.com/$GH_USER/$GH_REPO/releases/tag/$tag"
  )
}
