import json
import logging

import aiofiles

from ingestor.exceptions import StorageError

logger = logging.getLogger(
    __name__
)

async def salvar_json(
        caminho: str,
        dados: dict | list,
        *,
        fonte: str,       
):
    logger.info(
        "INICIO PERSISTENCIA | fonte=%s",
        fonte,
    )

    try:
        conteudo = json.dumps(
            dados,
            indent=2,
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as erro:
        raise StorageError(
            "Erro ao serializar",
            source=fonte,
        ) from erro

    try:
        async with aiofiles.open(caminho, "w", encoding="utf-8") as arquivo:
            await arquivo.write(conteudo)

    except OSError as erro:
        raise StorageError(
            "Falha ao persistir",
            source=fonte,
        ) from erro


    logger.info(
        "PERSISTENCIA CONCLUIDA | fonte=%s | caminho=%s",
        fonte,
        caminho,
    )