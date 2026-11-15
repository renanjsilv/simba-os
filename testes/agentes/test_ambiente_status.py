#!/usr/bin/env python3
"""Testes de verificação de login e atualizações de agentes."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "pacotes/simba-apps/raiz/usr/share/simba-apps/idiomas"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "pacotes/simba-apps/raiz/usr/bin"))

from importlib.machinery import SourceFileLoader
import motor as M

ag_path = Path(__file__).resolve().parent.parent.parent / "pacotes/simba-apps/raiz/usr/bin/agentes"
AG = SourceFileLoader("agentes", str(ag_path)).load_module()


class TestAmbienteStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.orig_home = M.HOME
        M.HOME = self.tmp_path
        AG.HOME = self.tmp_path

    def tearDown(self):
        M.HOME = self.orig_home
        AG.HOME = self.orig_home
        self.tmp.cleanup()

    def test_status_login_claude_expirando(self):
        claude_dir = self.tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        # Expira em 4 dias
        exp_ms = int((time.time() + 4 * 86400) * 1000)
        creds = {"claudeAiOauth": {"accessToken": "tok", "refreshTokenExpiresAt": exp_ms}}
        (claude_dir / ".credentials.json").write_text(json.dumps(creds))

        st = M.status_login("claude")
        self.assertTrue(st["conectado"])
        self.assertTrue(st["expirando"])
        self.assertFalse(st["expirado"])
        self.assertIn("4 dias", st["texto"])

    def test_status_login_claude_expirado(self):
        claude_dir = self.tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        # Expirado há 1 hora
        exp_ms = int((time.time() - 3600) * 1000)
        creds = {"claudeAiOauth": {"accessToken": "tok", "refreshTokenExpiresAt": exp_ms}}
        (claude_dir / ".credentials.json").write_text(json.dumps(creds))

        st = M.status_login("claude")
        self.assertFalse(st["conectado"])
        self.assertTrue(st["expirando"])
        self.assertTrue(st["expirado"])
        self.assertIn("expirado", st["texto"].lower())

    def test_status_login_claude_valido(self):
        claude_dir = self.tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        # Expira em 20 dias
        exp_ms = int((time.time() + 20 * 86400) * 1000)
        creds = {"claudeAiOauth": {"accessToken": "tok", "refreshTokenExpiresAt": exp_ms}}
        (claude_dir / ".credentials.json").write_text(json.dumps(creds))

        st = M.status_login("claude")
        self.assertTrue(st["conectado"])
        self.assertFalse(st["expirando"])
        self.assertFalse(st["expirado"])
        self.assertIn("Conectado", st["texto"])

    def test_status_login_sem_conta(self):
        st = M.status_login("claude")
        self.assertFalse(st["conectado"])
        self.assertFalse(st["expirando"])
        self.assertIn("Sem conta", st["texto"])

    @patch("motor._achar", return_value="/usr/bin/claude")
    @patch("motor.versao_instalada", return_value="2.1.325")
    @patch("motor._versao_recente_remota", return_value="2.1.326")
    def test_verificar_atualizacao_pendente(self, mock_remota, mock_inst, mock_achar):
        M.CACHE_ATUALIZACOES = self.tmp_path / "atualizacoes.json"
        up = M.verificar_atualizacao("claude", forcar=True)
        self.assertTrue(up["pendente"])
        self.assertEqual(up["versao_atual"], "2.1.325")
        self.assertEqual(up["versao_nova"], "2.1.326")
        self.assertIn("2.1.325 → 2.1.326", up["texto"])

    @patch("motor._achar", return_value="/usr/bin/claude")
    @patch("motor.versao_instalada", return_value="2.1.325")
    @patch("motor._versao_recente_remota", return_value="2.1.325")
    def test_verificar_atualizacao_em_dia(self, mock_remota, mock_inst, mock_achar):
        M.CACHE_ATUALIZACOES = self.tmp_path / "atualizacoes.json"
        up = M.verificar_atualizacao("claude", forcar=True)
        self.assertFalse(up["pendente"])
        self.assertEqual(up["versao_atual"], "2.1.325")
        self.assertIn("em dia", up["texto"])

    def test_agentes_estado_inclui_campos_novos(self):
        AG.CONFIG = self.tmp_path / "config.json"
        AG.ESTADO = self.tmp_path / "estado"
        st = AG.estado()
        self.assertIn("agentes", st)
        for a in st["agentes"]:
            self.assertIn("versao", a)
            self.assertIn("atualizacao", a)
            self.assertIn("loginStatus", a)
            self.assertIn("atualizando", a)


if __name__ == "__main__":
    unittest.main()
