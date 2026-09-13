"""Adapter customizado para invocar modelos no AWS Bedrock com payload específico."""

import json
import os
from typing import Any, Optional

try:
    import boto3
except ImportError:
    boto3 = None

from langchain_core.language_models import LLM
from langchain_core.messages import AIMessage


class _ResponseWrapper:
    """Wrapper para compatibilidade com LangChain - simula um AIMessage."""
    def __init__(self, text: str):
        self.content = text


class CustomBedrockLLM(LLM):
    """LLM wrapper para modelos customizados no AWS Bedrock com payload flexível."""

    model_id: str
    region_name: str = "us-east-1"
    credentials_profile_name: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 0.9
    top_k: int = 100

    @property
    def _llm_type(self) -> str:
        return "bedrock_custom"

    def _get_client(self):
        """Obtém o cliente Bedrock com credenciais configuradas."""
        if not boto3:
            raise ImportError("boto3 é necessário para usar Bedrock. Instale com: pip install boto3")

        session_kwargs = {}
        if self.credentials_profile_name:
            session_kwargs["profile_name"] = self.credentials_profile_name

        session = boto3.Session(**session_kwargs)
        return session.client("bedrock-runtime", region_name=self.region_name)

    def invoke(self, input: str, **kwargs: Any) -> _ResponseWrapper:
        """Sobrescreve invoke para retornar com .content (compatível com LangChain).

        Aceita kwargs como max_tokens para sobrescrever o padrão.
        """
        # Se passou max_tokens nos kwargs, usa ele temporariamente
        max_tokens_original = self.max_tokens
        if "max_tokens" in kwargs:
            self.max_tokens = kwargs.pop("max_tokens")

        try:
            resultado = self._call(input, **kwargs)
            return _ResponseWrapper(resultado)
        finally:
            self.max_tokens = max_tokens_original

    def _call(
        self,
        prompt: str,
        stop: Optional[list[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """Invoca o modelo Bedrock com payload específico."""
        client = self._get_client()

        # Payload para modelos Qwen/similares (prompt + parâmetros)
        body = {
            "prompt": prompt,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "temperature": self.temperature,
            "stop": stop or [],
        }

        try:
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read().decode("utf-8"))

            # Extrair o texto da resposta (formato OpenAI-style)
            if isinstance(response_body, dict):
                # Formato OpenAI com choices[0].text
                if "choices" in response_body and len(response_body["choices"]) > 0:
                    choice = response_body["choices"][0]
                    if "text" in choice:
                        return choice["text"].strip()

                # Tenta campos raiz alternativos
                for chave in ["text", "completion", "output", "response", "generated_text"]:
                    if chave in response_body:
                        return response_body[chave]

                # Se não encontrou, retorna a resposta inteira formatada
                return json.dumps(response_body)
            else:
                return str(response_body)

        except Exception as e:
            raise RuntimeError(f"Erro ao invocar modelo Bedrock {self.model_id}: {str(e)}")
