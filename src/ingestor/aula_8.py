import asyncio
import json
import logging

import httpx

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(message)s | %(levelname)s"
    ),
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(
    __name__,
)

STATUS_RETRY = {429, 502, 503, 504}



async def testar_cenario(status_planejado, chamadas_esperadas, deve_falhar: bool):
    respostas_planejadas = iter(status_planejado)
    chamadas_realizadas = []

    def simular_api(request: httpx.Request) -> httpx.Response:
        status = next(respostas_planejadas)
        chamadas_realizadas.append(status)

        logger.info(
            "CONSULTA SIMULADA | método=%s | caminho=%s",
            request.method,
            request.url.path,
        )

        if status == 503:
            return httpx.Response(
                status_code=503,
                json={"erro": "Servidor Temporariamente Indisponível"},
            )

        return httpx.Response(
            status_code=200,
            json={"transacoes": [102, 103]}
        )

    transporte = httpx.MockTransport(simular_api)

    async with httpx.AsyncClient(transport=transporte) as client:
        try:
            dados = await extrair_com_retry(
                client,
                "https://api.exemplo.test/transacoes",
            )
        except httpx.HTTPStatusError:
            if not deve_falhar:
                raise

            logger.info("FALHA ESPERADA RECEBIDA")

        else:
            assert not deve_falhar, "Esperávamos falha, mas recebemos dados."
            assert dados == {"transacoes": [102, 103]}, "Dados diferentes do esperado"

    assert chamadas_realizadas == chamadas_esperadas, "Chamadas diferentes do esperado"

    logger.info(
        "VERIFICAÇÃO PASSOU | chamadas=%s",
        chamadas_realizadas,
    )

async def extrair_com_retry(
        client: httpx.AsyncClient,
        url: str,
):
    total_tentativas = 2

    for tentativa in range(total_tentativas):
        try:
            resposta = await client.get(url)
            resposta.raise_for_status()
            dados = resposta.json()

            return dados
        except httpx.HTTPStatusError as erro:
            ultima_tentativa = tentativa == total_tentativas - 1

            logger.warning(
            "TENTATIVA FALHOU | status=%d | tentativa=%d/%d",
            erro.response.status_code,
            tentativa + 1,
            total_tentativas,
            )

            if erro.response.status_code not in STATUS_RETRY or ultima_tentativa:
                raise


            await asyncio.sleep(1)

        except json.JSONDecodeError:
            logger.error(
                "EXTRAÇÃO INTERROMPIDA | motivo: JSON INVÁLIDO"
            )
            raise

async def main():
    await testar_cenario([503, 200], [503, 200], False)
    await testar_cenario([200, 503], [200], False)
    await testar_cenario([503, 503], [503, 503], True)

if __name__ == "__main__":
    asyncio.run(main())