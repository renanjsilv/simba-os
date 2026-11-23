"""simba-remoto [--servidor] [--aceitar-tudo] [--sem-lan] [-v] [CODIGO]"""
import sys


def main():
    args = sys.argv[1:]
    if "--servidor" in args or "--aceitar-tudo" in args:
        import asyncio
        import logging
        from .host import Servidor
        logging.basicConfig(level=logging.DEBUG if "-v" in args else logging.INFO,
                            format="%(asctime)s %(name)s %(message)s")
        for n in ("aioice", "aiortc"):
            logging.getLogger(n).setLevel(logging.WARNING)

        async def aprovar(nome, sas):
            return "--aceitar-tudo" in args

        async def rodar():
            s = Servidor(aprovar=aprovar)
            print("Código deste PC:", s.cfg["codigo"], flush=True)
            await s.iniciar()
            if "--sem-lan" in args and getattr(s, "lan", None):
                s.lan.fechar()
            await asyncio.Event().wait()
        asyncio.run(rodar())
    else:
        from .app import main as app_main
        alvo = None
        for a in args:
            digitos = "".join(c for c in a if c.isdigit())
            if len(digitos) == 9:
                alvo = digitos
                break
        app_main(codigo_alvo=alvo)


if __name__ == "__main__":
    main()
