# Simba OS — comandos de administrador

- Para comandos que precisam de root (instalar pacotes, editar /etc, systemctl do sistema),
  use `sudo -A <comando>`. A senha é pedida ao usuário numa janela do Simba (`simba-senha`),
  com o comando visível; não peça a senha no chat e nunca a escreva em arquivos ou comandos.
- `pkexec <comando>` também funciona: abre o diálogo de autenticação do simba-shell.
- Se o usuário cancelar a janela, o comando falha: explique o que ia ser feito e pare.
