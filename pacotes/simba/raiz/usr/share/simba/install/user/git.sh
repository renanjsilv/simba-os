# Set identification from install inputs
if [[ -n ${SIMBA_USER_NAME//[[:space:]]/} ]]; then
  git config --global user.name "$SIMBA_USER_NAME"
fi

if [[ -n ${SIMBA_USER_EMAIL//[[:space:]]/} ]]; then
  git config --global user.email "$SIMBA_USER_EMAIL"
fi
