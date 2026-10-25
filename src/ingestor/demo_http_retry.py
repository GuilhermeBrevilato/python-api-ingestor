import asyncio
import json
import logging
import random

import httpx

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

async def testar_cenario(
        status_planejados, 
        chamadas_esperadas, 
        deve_falhar: bool, 
        excecao_esperada=None,
        quantidade_esperas_esperadas=None,
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

    def simular_api(
            request: httpx.Request,
    ) -> httpx.Response:
        status = next(chamadas_planejadas)
        chamadas_realizadas.append(status)

        logger.info(
            "CONSULTA SIMULADA | method=%s | endpoint=%s",
            request.method,
            request.url.path,
        )

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
            if status == 503:
                return httpx.Response(
                    status_code=503,
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

        if quantidade_esperas_esperadas is not None:
            assert len(esperas_realizadas) == quantidade_esperas_esperadas, "Quantidade de esperas diferente do esperado"

        logger.info(
            "VERIFICACAO PASSOU."
        )


async def extrair_com_retry(
        client: httpx.AsyncClient,
        url: str,
        aguardar,
        sortear,
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

            logger.info(
                "AGUARDANDO RETRY | calculada=%.1f | limitada=%.1f | sorteada=%.2f segundos",
                espera_calculada,
                espera_limitada,
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
        ["connect_timeout", "connect_timeout", "connect_timeout"],
        ["connect_timeout", "connect_timeout", "connect_timeout"],
        True,
        httpx.ConnectTimeout,
        quantidade_esperas_esperadas=2,
    )

    await testar_cenario(
        [404, 200],
        [404],
        True,
        httpx.HTTPStatusError,
        quantidade_esperas_esperadas=0,
    )

    await testar_cenario(
        [503, 503, 200],
        [503, 503, 200],
        False,
        quantidade_esperas_esperadas=2,
    )

if __name__=="__main__":
    asyncio.run(main())