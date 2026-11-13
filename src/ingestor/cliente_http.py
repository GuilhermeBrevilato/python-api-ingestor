import json
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from ingestor.exceptions import EsperaExcedeOrcamento

logger = logging.getLogger(
    __name__,
)

STATUS_RETRY = {
    429,
    503,
}

def calcular_espera_retry_after_data(valor, agora):

    instante_retry = interpretar_retry_after_data(valor)

    if instante_retry is None:
        return None

    segundos_restantes = (instante_retry - agora).total_seconds()

    # Data vencida ou igual a agora: o valor não é confiável; usa backoff com jitter.
    if segundos_restantes <= 0:
        return None

    return segundos_restantes

def interpretar_retry_after_data(valor):
    if valor is None:
        return None

    try:
        instante_retry = parsedate_to_datetime(valor)
    except (ValueError, TypeError, OverflowError):
        return None

    return instante_retry

def interpretar_retry_after_segundos(valor):

    if valor is None:
        return None

    try:
        segundos = int(valor)
    except ValueError:
        return None

    if segundos < 0:
        return None

    return segundos

def interpretar_retry_after(
        valor: str,
        agora: datetime,
) -> int | float | None:
    segundos = interpretar_retry_after_segundos(valor)

    if segundos is not None:
        return segundos

    return calcular_espera_retry_after_data(valor, agora)

def agora_utc():
    return datetime.now(UTC)

async def extrair_com_retry(
        client: httpx.AsyncClient,
        url: str,
        aguardar,
        sortear,
        relogio=agora_utc,
        orcamento_espera=600,
    ) -> dict | list:
    total_tentativas = 3
    pausa_inicial = 1
    espera_maxima = 1.5

    for tentativa in range(total_tentativas):
        numero_tentativa = tentativa + 1
        espera_calculada = pausa_inicial * (2 ** tentativa)
        espera_limitada = min(espera_calculada, espera_maxima)
        espera = sortear(0.0, espera_limitada)

        assert 0.0 <= espera <= espera_limitada, (
            "Espera fora do intervalo permitido"
        )

        try:
            resposta = await client.get(url)
            resposta.raise_for_status()
            dados = resposta.json()

            return dados
        except httpx.HTTPStatusError as erro:
            status = erro.response.status_code

            if status not in STATUS_RETRY:
                logger.error(
                    "STATUS NAO RETENTAVEL| status=%d",
                    erro.response.status_code,
                )
                raise 

            elif tentativa == total_tentativas - 1:
                logger.error(
                    "TENTATIVAS ESGOTADAS | tentativa=%d/%d | status=%d",
                    numero_tentativa,
                    total_tentativas,
                    erro.response.status_code,
                )
                raise


            logger.warning(
                "RETRY ACIONADO | status=%d | tentativa=%d/%d",
                erro.response.status_code,
                numero_tentativa,
                total_tentativas,
            )

            valor = erro.response.headers.get("Retry-After")
            agora = relogio()
            segundos = interpretar_retry_after(valor, agora)

            if segundos is not None:

                if segundos > orcamento_espera:
                    logger.error(
                        "ESPERA SOLICITADA EXCEDE O LIMITE INTERNO | espera_solicitada=%.2f | limite_interno=%d",
                        segundos,
                        orcamento_espera,
                    )

                    raise EsperaExcedeOrcamento(
                        f"Servidor pediu {segundos:.2f} s de espera; "
                        f"orçamento é {orcamento_espera} s",
                        source=url,
                    ) from erro

                espera = segundos
                origem = "Retry-After"
            else:
                origem = "backoff_com_jitter"

            logger.info(
                "AGUARDANDO RETRY | origem=%s | espera=%.2f segundos",
                origem,
                espera,
            )

            await aguardar(espera)

        except json.JSONDecodeError:
            logger.error(
                "EXTRAÇÃO INTERROMPIADA | motivo=JSON INVÁLIDO",
            )
            raise

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as erro:
            if tentativa == total_tentativas - 1:
                logger.error(
                        "TENTATIVAS ESGOTADAS | motivo=%s | tentativa=%d/%d",
                        erro,
                        numero_tentativa,
                        total_tentativas,
                    )
                raise

            logger.warning(
                "RETRY ACIONADO | motivo=%s | tentativa=%d/%d",
                erro,
                numero_tentativa,
                total_tentativas,
            )

            logger.info(
                "AGUARDANDO RETRY | calculada=%.1f | limitada=%.1f | sorteada=%.2f segundos",
                espera_calculada,
                espera_limitada,
                espera,
            )

            await aguardar(espera)
