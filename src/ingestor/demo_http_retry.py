import asyncio
import json
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from ingestor.exceptions import EsperaExcedeOrcamento

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | %(message)s"
    ),
    datefmt="%H:%M:%S",
)

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

async def testar_cenario(
        status_planejados, 
        chamadas_esperadas, 
        deve_falhar: bool, 
        excecao_esperada=None,
        esperas_esperadas=None,
        retry_after="10",
        ):

    chamadas_planejadas = iter(status_planejados)
    chamadas_realizadas = []
    esperas_realizadas =[]

    def escolher_limite_superior(minimo, maximo):
        return maximo

    async def simular_espera(segundos):
        esperas_realizadas.append(segundos)

        logger.info(
            "ESPERA SIMULADA | segundos=%.2f",
            segundos,
        )

    def relogio_fixo():
        return datetime(
            2026, 11, 1, 14, 59, 40,
            tzinfo=UTC,
        )

    def simular_api(
            request: httpx.Request,
    ) -> httpx.Response:
        status = next(chamadas_planejadas)
        chamadas_realizadas.append(status)
        headers = {}

        
        logger.info(
            "CONSULTA SIMULADA | method=%s | endpoint=%s",
            request.method,
            request.url.path,
        )

        if retry_after is not None:
            headers["Retry-After"] = retry_after

        if status == "connect_timeout":
            raise httpx.ConnectTimeout(
                "Tempo limite de conexão simulado",
                request=request,
            )

        if status == "read_timeout":
            raise httpx.ReadTimeout(
                "Tempo limite de leitura simulado",
                request=request,
            )

        if status == "json_invalido":
            return httpx.Response(
                status_code=200,
                headers=headers,
                text="Serviço em manutencao",
            )        

        if status == 200:
            return httpx.Response(
            status_code=200,
            json={"transacoes": [102, 103]},
        )

        if status not in STATUS_RETRY:
            return httpx.Response(
                status_code=status,
                json={"erro": "ainda nao sei qual é mas é para teste"},
            )

        if status in STATUS_RETRY:
            if status == 429:
                return httpx.Response(
                    status_code=429,
                    headers=headers,
                    json={"erro": "Muitas consultas em pouco tempo"},
                )

            if status == 503:
                return httpx.Response(
                    status_code=503,
                    headers=headers,
                    json={"message": "Servidor temporariamente indisponivel"},
                )
            else:
                return httpx.Response(
                status_code=status,
                json={"erro": "ainda nao sei qual é mas é para teste"},
            )

    transporte = httpx.MockTransport(simular_api)

    async with httpx.AsyncClient(transport=transporte) as client:
        try:
            dados = await extrair_com_retry(
                client, 
                "https://api.exemplo.test/transacoes",
                aguardar=simular_espera,
                sortear=escolher_limite_superior,
                relogio=relogio_fixo,
            )
            logger.info(
                "CONSULTAS CONCLUIDAS | dados=%s",
                dados,
            )
        except httpx.HTTPStatusError as erro:

            if not deve_falhar:
                raise

            assert excecao_esperada is not None, "Informe a excecao esperada"
            assert isinstance(erro, excecao_esperada), "Excecao diferente do esperado"

            logger.error(
                "FALHA HTTP ESPERADA RECEBIDA | excecao_esperada=%s | deve_falhar=%s",
                excecao_esperada,
                deve_falhar,
            )

        except json.JSONDecodeError as erro:
            if not deve_falhar:
                raise

            assert excecao_esperada is not None, "Informe a excecao esperada"
            assert isinstance(erro, excecao_esperada), "Excecao diferente do esperado"

            logger.info("FALHA ESPERADA RECEBIDA | motivo=JSON inválido")

        except EsperaExcedeOrcamento as erro:
            if not deve_falhar:
                raise

            assert excecao_esperada is not None, "Informe a excecao esperada"
            assert isinstance(erro, excecao_esperada), "Excecao diferente do esperado"

            logger.info(
                "FALHA ESPERADA RECEBIDA | motivo=%s",
                erro,
            )

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as erro:
            if not deve_falhar:
                raise

            assert excecao_esperada is not None, "Informe a excecao esperada"
            assert isinstance(erro, excecao_esperada), "Excecao diferente do esperado"

            logger.info(
                "FALHA ESPERADA RECEBIDA | motivo=%s",
                erro,
            )
        else:
            assert not deve_falhar, "Esperavamos falha, mas tivemos dados"
            assert dados == {"transacoes": [102, 103]}, "dados inconsistentes"

        assert chamadas_realizadas == chamadas_esperadas, "chamadas realizadas não condizentes com o planejado"


        if esperas_esperadas is not None:
            assert esperas_realizadas == esperas_esperadas, (
                f"Esperas diferentes: esperado={esperas_esperadas}, "
                f"recebido={esperas_realizadas}"
            )

        logger.info(
            "VERIFICACAO PASSOU."
        )


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



async def main() -> None:
    
    await testar_cenario(
        status_planejados=[429, 200],
        chamadas_esperadas=[429, 200],
        deve_falhar=False,
        retry_after="Sun, 01 Nov 2026 15:00:00 GMT",
        esperas_esperadas=[20.0],
    )

    await testar_cenario(
        status_planejados=[429, 200],
        chamadas_esperadas=[429, 200],
        deve_falhar=False,
        retry_after="Sun, 01 Nov 2026 14:55:00 GMT",
        esperas_esperadas=[1.0],
    )

    await testar_cenario(
        status_planejados=[429, 200],
        chamadas_esperadas=[429],
        deve_falhar=True,
        excecao_esperada= EsperaExcedeOrcamento,
        retry_after="601",
        esperas_esperadas=[],
    )

    await testar_cenario(
        status_planejados=[429, 200],
        chamadas_esperadas=[429, 200],
        deve_falhar=False,
        retry_after="600",
        esperas_esperadas=[600.0],
    )


if __name__=="__main__":
    asyncio.run(main())