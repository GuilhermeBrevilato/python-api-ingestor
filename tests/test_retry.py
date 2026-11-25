import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from ingestor.cliente_http import extrair_com_retry
from ingestor.exceptions import EsperaExcedeOrcamento

URL = "https://api.exemplo.test/transacoes"
DADOS_OK = {"transacoes": [102, 103]}


def relogio_fixo():
    return datetime(2026, 11, 1, 14, 59, 40, tzinfo=UTC)


def escolher_limite_superior(minimo, maximo):
    return maximo


async def executar(status_planejados, retry_after, chamadas, esperas):
    planejados = iter(status_planejados)

    async def simular_espera(segundos):
        esperas.append(segundos)

    def simular_api(request):
        status = next(planejados)
        chamadas.append(status)

        if status == 200:
            return httpx.Response(200, json=DADOS_OK)

        return httpx.Response(status, headers={"Retry-After": retry_after})

    transporte = httpx.MockTransport(simular_api)

    async with httpx.AsyncClient(transport=transporte) as client:
        return await extrair_com_retry(
            client,
            URL,
            aguardar=simular_espera,
            sortear=escolher_limite_superior,
            relogio=relogio_fixo,
        )

def test_retry_after_em_data_espera_ate_o_instante_pedido():
    # Preparar
    chamadas, esperas = [], []

    # Executar
    dados = asyncio.run(
        executar([429, 200], "Sun, 01 Nov 2026 15:00:00 GMT", chamadas, esperas)
    )

    # Conferir
    assert dados == DADOS_OK
    assert chamadas == [429, 200]
    assert esperas == [20.0]


def test_retry_after_com_data_vencida_usa_backoff():
    # Preparar
    chamadas, esperas = [], []

    # Executar
    dados = asyncio.run(
        executar([429, 200], "Sun, 01 Nov 2026 14:55:00 GMT", chamadas, esperas)
    )

    # Conferir
    assert dados == DADOS_OK
    assert chamadas == [429, 200]
    assert esperas == [1.0]


def test_retry_after_igual_ao_orcamento_e_aceito():
    # Preparar
    chamadas, esperas = [], []

    # Executar
    dados = asyncio.run(
        executar([429, 200], "600", chamadas, esperas)
    )

    # Conferir
    assert dados == DADOS_OK
    assert chamadas == [429, 200]
    assert esperas == [600.0]

def test_retry_after_acima_do_orcamento_interrompe_com_erro():
    # Preparar
    chamadas, esperas = [], []

    # Executar, esperando o erro
    with pytest.raises(EsperaExcedeOrcamento):
        asyncio.run(
            executar(
                [429, 200], "601", chamadas, esperas,
            )
        )

    # Conferir
    assert chamadas == [429]
    assert esperas == []
