from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_ENV = RAIZ_PROJETO / ".env"
load_dotenv(CAMINHO_ENV)


class ErroConfiguracao(Exception):
    """Erro de configuração que pode ser explicado ao proprietário."""


def _texto(nome: str, *alternativos: str, padrao: str = "") -> str:
    for candidato in (nome, *alternativos):
        valor = os.getenv(candidato)
        if valor is not None and valor.strip():
            return valor.strip()
    return padrao


def _inteiro(nome: str, padrao: int, minimo: int = 0) -> int:
    bruto = os.getenv(nome, str(padrao)).strip()

    try:
        valor = int(bruto)
    except ValueError as erro:
        raise ErroConfiguracao(
            f"{nome} deve ser um número inteiro."
        ) from erro

    if valor < minimo:
        raise ErroConfiguracao(
            f"{nome} deve ser maior ou igual a {minimo}."
        )

    return valor


def _decimal(
    nome: str,
    padrao: float,
    minimo: float = 0.0,
) -> float:
    bruto = os.getenv(nome, str(padrao)).strip()

    try:
        valor = float(bruto)
    except ValueError as erro:
        raise ErroConfiguracao(
            f"{nome} deve ser um número decimal."
        ) from erro

    if valor < minimo:
        raise ErroConfiguracao(
            f"{nome} deve ser maior ou igual a {minimo}."
        )

    return valor


@dataclass(frozen=True)
class Settings:
    # Modelo de linguagem
    openai_api_key: str
    llm_base_url: str
    llm_model: str
    llm_input_price_per_million: float
    llm_output_price_per_million: float
    llm_max_output_tokens: int

    # MySQL
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str

    # Grafo e orçamentos
    agent_max_steps: int
    agent_max_tool_calls: int
    agent_max_tokens: int
    agent_max_time_seconds: int
    agent_max_cost_usd: float
    graph_recursion_limit: int
    loop_repeat_limit: int
    conversation_max_turns: int

    # Persistência
    checkpoint_database: Path
    memory_database: Path
    corpus_directory: Path
    log_directory: Path
    approval_timeout_hours: int
    memory_episode_half_life_days: int
    rag_max_results: int
    rag_min_score: float

    # Identificação do único usuário autorizado
    default_user_id: str
    default_thread_id: str

    def validar_modelo(self) -> None:
        ausentes = []

        if not self.openai_api_key:
            ausentes.append("OPENAI_API_KEY")

        if not self.llm_model:
            ausentes.append("LLM_MODEL")

        if ausentes:
            raise ErroConfiguracao(
                "Variáveis obrigatórias para chamar o modelo: "
                + ", ".join(ausentes)
            )

    def validar_mysql(self) -> None:
        ausentes = []

        if not self.mysql_database:
            ausentes.append("DB_NAME")

        if not self.mysql_user:
            ausentes.append("DB_USER")

        if ausentes:
            raise ErroConfiguracao(
                "Variáveis obrigatórias para consultar o MySQL: "
                + ", ".join(ausentes)
            )


def carregar_configuracoes() -> Settings:
    return Settings(
        openai_api_key=_texto("OPENAI_API_KEY"),
        llm_base_url=_texto(
            "LLM_BASE_URL",
            padrao="https://api.openai.com/v1",
        ),
        llm_model=_texto("LLM_MODEL"),
        llm_input_price_per_million=_decimal(
            "LLM_INPUT_PRICE_PER_MILLION",
            0.0,
        ),
        llm_output_price_per_million=_decimal(
            "LLM_OUTPUT_PRICE_PER_MILLION",
            0.0,
        ),
        llm_max_output_tokens=_inteiro(
            "LLM_MAX_OUTPUT_TOKENS",
            700,
            1,
        ),
        mysql_host=_texto(
            "MYSQL_HOST",
            "DB_HOST",
            padrao="localhost",
        ),
        mysql_port=_inteiro(
            "MYSQL_PORT",
            int(_texto("DB_PORT", padrao="3306")),
            1,
        ),
        mysql_database=_texto(
            "MYSQL_DATABASE",
            "DB_NAME",
        ),
        mysql_user=_texto(
            "MYSQL_USER",
            "DB_USER",
        ),
        mysql_password=_texto(
            "MYSQL_PASSWORD",
            "DB_PASSWORD",
        ),
        agent_max_steps=_inteiro(
            "AGENT_MAX_STEPS",
            10,
            1,
        ),
        agent_max_tool_calls=_inteiro(
            "AGENT_MAX_TOOL_CALLS",
            8,
            1,
        ),
        agent_max_tokens=_inteiro(
            "AGENT_MAX_TOKENS",
            12_000,
            1,
        ),
        agent_max_time_seconds=_inteiro(
            "AGENT_MAX_TIME_SECONDS",
            _inteiro(
                "AGENT_MAX_SECONDS",
                90,
                1,
            ),
            1,
        ),
        agent_max_cost_usd=_decimal(
            "AGENT_MAX_COST_USD",
            0.15,
            0.001,
        ),
        graph_recursion_limit=_inteiro(
            "GRAPH_RECURSION_LIMIT",
            24,
            2,
        ),
        loop_repeat_limit=_inteiro(
            "LOOP_REPEAT_LIMIT",
            3,
            2,
        ),
        conversation_max_turns=_inteiro(
            "CONVERSATION_MAX_TURNS",
            6,
            1,
        ),
        checkpoint_database=Path(
            _texto(
                "CHECKPOINT_DATABASE",
                padrao=str(
                    RAIZ_PROJETO
                    / "dados"
                    / "checkpoints.sqlite3"
                ),
            )
        ),
        memory_database=Path(
            _texto(
                "MEMORY_DATABASE",
                padrao=str(
                    RAIZ_PROJETO
                    / "dados"
                    / "memoria.sqlite3"
                ),
            )
        ),
        corpus_directory=Path(
            _texto(
                "CORPUS_DIRECTORY",
                padrao=str(
                    RAIZ_PROJETO
                    / "dados"
                    / "corpus"
                ),
            )
        ),
        log_directory=Path(
            _texto(
                "LOG_DIRECTORY",
                padrao=str(RAIZ_PROJETO / "logs"),
            )
        ),
        approval_timeout_hours=_inteiro(
            "APPROVAL_TIMEOUT_HOURS",
            24,
            1,
        ),
        memory_episode_half_life_days=_inteiro(
            "MEMORY_EPISODE_HALF_LIFE_DAYS",
            90,
            1,
        ),
        rag_max_results=_inteiro(
            "RAG_MAX_RESULTS",
            3,
            1,
        ),
        rag_min_score=_decimal(
            "RAG_MIN_SCORE",
            0.001,
            0.0,
        ),
        default_user_id=_texto(
            "AGENT_USER_ID",
            padrao="proprietario",
        ),
        default_thread_id=_texto(
            "AGENT_THREAD_ID",
            padrao="proprietario-principal",
        ),
    )


settings = carregar_configuracoes()