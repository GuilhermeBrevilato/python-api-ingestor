from pathlib import Path

from ingestor.models import FonteAPI

MAX_CONCORRENCIA = 3

HTTP_TIMEOUT = 10.0

BACKOFFS = (
    0.5,
    1.0,
    2.0,
)

STATUS_RETRY = {
    429,
    500,
    502,
    503,
    504,
}

BASE_DIR = Path(__file__).resolve().parent().parent().parent()
BRONZE_DIR = BASE_DIR / "data" / "bronze"
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

FONTES = [
    FonteAPI(
        nome="BrasilAPI Bancos",
        url=("https://brasilapi.com.br/api/banks/v1"),
        arquivo=str(BRONZE_DIR / "brasilapi_bancos.json"),
    ),
    FonteAPI(
        nome="BrasilAPI Feriados",
        url=("https://brasilapi.com.br/api/feriados/v1/2026"),
        arquivo=str(BRONZE_DIR / "brasilapi_feriados.json"),
    ),
    FonteAPI(
        nome="IBGE Estados",
        url=("https://servicodados.ibge.gov.br/api/v1/localidades/estados"),
        arquivo=str(BRONZE_DIR / "ibge_estados.json"),
    ),
    FonteAPI(
        nome="IBGE Municipios SP",
        url=(
            "https://servicodados.ibge.gov.br/api/v1/localidades/estados/SP/municipios"
        ),
        arquivo=str(BRONZE_DIR / "ibge_municipios_sp.json"),
    ),
    FonteAPI(
        nome="Open-Meteo São Paulo",
        url=(
            "https://api.open-meteo.com/v1/"
            "forecast?latitude=-23.55"
            "&longitude=-46.63"
            "&current=temperature_2m"
        ),
        arquivo=str(BRONZE_DIR / "open_meteo_sp.json"),
    ),
]