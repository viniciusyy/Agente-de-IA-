import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_ENV = RAIZ_PROJETO / ".env"

load_dotenv(CAMINHO_ENV)


class ErroConfiguracao(Exception):
    """Erro causado por variável de ambiente ausente ou inválida."""


def obter_variavel(
    nome_principal: str,
    *nomes_alternativos: str,
    padrao: str | None = None,
    obrigatoria: bool = False,
) -> str:
    """
    Procura uma variável pelo nome principal e depois pelos aliases.
    """
    nomes = (nome_principal, *nomes_alternativos)

    for nome in nomes:
        valor = os.getenv(nome)

        if valor is not None and valor.strip():
            return valor.strip()

    if obrigatoria:
        nomes_texto = " ou ".join(nomes)

        raise ErroConfiguracao(
            f"Variável obrigatória não encontrada: {nomes_texto}. "
            f"Verifique o arquivo {CAMINHO_ENV}."
        )

    return padrao or ""


def obter_inteiro(
    nome: str,
    padrao: int,
    minimo: int = 1,
) -> int:
    valor_texto = os.getenv(nome, str(padrao))

    try:
        valor = int(valor_texto)
    except ValueError as erro:
        raise ErroConfiguracao(
            f"A variável {nome} deve conter um número inteiro."
        ) from erro

    if valor < minimo:
        raise ErroConfiguracao(
            f"A variável {nome} deve ser maior ou igual a {minimo}."
        )

    return valor


def obter_decimal(
    nome: str,
    padrao: float,
    minimo: float = 0.0,
) -> float:
    valor_texto = os.getenv(nome, str(padrao))

    try:
        valor = float(valor_texto)
    except ValueError as erro:
        raise ErroConfiguracao(
            f"A variável {nome} deve conter um número decimal."
        ) from erro

    if valor < minimo:
        raise ErroConfiguracao(
            f"A variável {nome} deve ser maior ou igual a {minimo}."
        )

    return valor


@dataclass(frozen=True)
class Settings:
    # Configuração do modelo
    openai_api_key: str
    llm_base_url: str
    llm_model: str

    # Configuração do MySQL
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str

    # Orçamento do agente
    agent_max_steps: int
    agent_max_tool_calls: int
    agent_max_tokens: int
    agent_max_time_seconds: int
    agent_max_cost_usd: float

    # Logs
    log_directory: str


def carregar_configuracoes() -> Settings:
    return Settings(
        openai_api_key=obter_variavel(
            "OPENAI_API_KEY",
            obrigatoria=True,
        ),
        llm_base_url=obter_variavel(
            "LLM_BASE_URL",
            padrao="https://api.openai.com/v1",
        ),
        llm_model=obter_variavel(
            "LLM_MODEL",
            obrigatoria=True,
        ),
        mysql_host=obter_variavel(
            "MYSQL_HOST",
            "DB_HOST",
            padrao="localhost",
        ),
        mysql_port=int(
            obter_variavel(
                "MYSQL_PORT",
                "DB_PORT",
                padrao="3306",
            )
        ),
        mysql_database=obter_variavel(
            "MYSQL_DATABASE",
            "DB_NAME",
            obrigatoria=True,
        ),
        mysql_user=obter_variavel(
            "MYSQL_USER",
            "DB_USER",
            obrigatoria=True,
        ),
        mysql_password=obter_variavel(
            "MYSQL_PASSWORD",
            "DB_PASSWORD",
            obrigatoria=True,
        ),
        agent_max_steps=obter_inteiro(
            "AGENT_MAX_STEPS",
            padrao=8,
        ),
        agent_max_tool_calls=obter_inteiro(
            "AGENT_MAX_TOOL_CALLS",
            padrao=6,
        ),
        agent_max_tokens=obter_inteiro(
            "AGENT_MAX_TOKENS",
            padrao=9000,
        ),
        agent_max_time_seconds=obter_inteiro(
            "AGENT_MAX_TIME_SECONDS",
            padrao=60,
        ),
        agent_max_cost_usd=obter_decimal(
            "AGENT_MAX_COST_USD",
            padrao=0.10,
            minimo=0.001,
        ),
        log_directory=obter_variavel(
            "LOG_DIRECTORY",
            padrao=str(RAIZ_PROJETO / "logs"),
        ),
    )


settings = carregar_configuracoes()