from dataclasses import dataclass


@dataclass
class FonteAPI:
    nome: str
    url: str
    arquivo: str


@dataclass
class ResultadoIngestao:
    fonte: str
    sucesso: bool
    arquivo: str | None = None
    erro: str | None = None


@dataclass
class ConcorrenciaTracker:
    ativos: int = 0
    pico: int = 0

    def entrar(self) -> None:

        self.ativos += 1

        self.pico = max(
            self.pico,
            self.ativos,
        )

    def sair(self) -> None:

        self.ativos -= 1