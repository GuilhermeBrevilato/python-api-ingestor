import logging

import httpx

from ingestor.models import FonteAPI

logger = logging.getLogger(
    __name__
)

async def consulta_api(
        client: httpx.AsyncClient,
        fonte: FonteAPI,
) -> dict | list:
    logger.info(
        "HTTP COMEÇANDO | fonte=%s",
        fonte.nome,
    )

    resposta = await client.get(fonte.url)

    resposta.raise_for_status()

    dados = resposta.json()

    logger.info(
        "HTTP CONCLUIDO | fonte=%s | status=%s",
        fonte.nome,
        resposta.status_code,
    )

    return dados