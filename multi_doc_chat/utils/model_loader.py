import json
import os
import sys
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from multi_doc_chat.exception.custom_exception import DocumentPortalException
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.utils.config_loader import load_config


class ApiKeyManager:
    def __init__(self):
        self.api_keys = {}
        raw = os.getenv("apikeyliveclass")

        if raw:
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("apikeyliveclass is not a valid JSON object")
                self.api_keys.update(parsed)
                log.info("Loaded API keys from ECS secret")
            except Exception as e:
                log.warning("Failed to parse apikeyliveclass JSON", error=str(e))

        self._load_individual_keys([
            "GROQ_API_KEY",
            "GOOGLE_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "YOUR_OPENROUTER_API_KEY",
            "HUGGINGFACEHUB_API_TOKEN",
        ])

    def _load_individual_keys(self, keys):
        for key in keys:
            if key not in self.api_keys:
                env_val = os.getenv(key)
                if env_val:
                    self.api_keys[key] = env_val
                    log.info(f"Loaded {key} from individual env var")

    def get(self, key: str, fallback_keys: list[str] | None = None) -> str:
        value = self.api_keys.get(key)
        if not value and fallback_keys:
            for alias in fallback_keys:
                value = self.api_keys.get(alias) or os.getenv(alias)
                if value:
                    break
        if not value:
            raise KeyError(f"API key for {key} is missing")
        return value


class ModelLoader:
    def __init__(self):
        if os.getenv("ENV", "local").lower() != "production":
            load_dotenv()
            log.info("Running in LOCAL mode: .env loaded")
        else:
            log.info("Running in PRODUCTION mode")

        self.api_key_mgr = ApiKeyManager()
        self.config = load_config()
        log.info("YAML config loaded", config_keys=list(self.config.keys()))

    def load_embeddings(self):
        embedding_config = self.config.get("embedding_model", {})
        provider = embedding_config.get("provider", "openai")
        model_name = embedding_config.get("model_name")
        base_url = embedding_config.get("base_url")

        log.info("Loading embeddings", provider=provider, model=model_name)

        if provider == "google":
            return GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=self.api_key_mgr.get("GOOGLE_API_KEY"),
            )

        if provider == "openai":
            return OpenAIEmbeddings(
                model=model_name,
                api_key=self.api_key_mgr.get(
                    "OPENAI_API_KEY",
                    fallback_keys=["OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY"],
                ),
            )

        if provider == "openrouter":
            return OpenAIEmbeddings(
                model=model_name,
                api_key=self.api_key_mgr.get(
                    "OPENROUTER_API_KEY",
                    fallback_keys=["OPENAI_API_KEY", "YOUR_OPENROUTER_API_KEY"],
                ),
                base_url=base_url,
            )

        if provider == "local":
            return SentenceTransformerEmbeddings(
                model_name=model_name,
            )

        if provider == "huggingface":
            try:
                hf_token = self.api_key_mgr.get("HUGGINGFACEHUB_API_TOKEN")
                embeddings = HuggingFaceEndpointEmbeddings(
                    model=model_name,
                    huggingfacehub_api_token=hf_token,
                )
                # Smoke-test the API to confirm it's reachable
                embeddings.embed_query("test")
                log.info("HuggingFace Inference API embeddings loaded", model=model_name)
                return embeddings
            except Exception as e:
                log.warning(
                    "HuggingFace API unavailable, falling back to local embeddings",
                    error=str(e),
                    model=model_name,
                )
                return SentenceTransformerEmbeddings(model_name=model_name)

        raise DocumentPortalException(
            f"Unsupported embedding provider: {provider}", sys
        )

    def load_llm(self):
        llm_block = self.config.get("llm", {})
        provider_key = os.getenv("LLM_PROVIDER", "openai")
        provider_key = provider_key.strip().strip('"').strip("'").lower()

        if provider_key not in llm_block:
            if "openai" in llm_block:
                log.warning(
                    "LLM provider not found in config, falling back to openai",
                    requested_provider=provider_key,
                )
                provider_key = "openai"
            else:
                log.error("LLM provider not found in config", provider=provider_key)
                raise ValueError(f"LLM provider '{provider_key}' not found in config")

        llm_config = llm_block[provider_key]
        provider = llm_config.get("provider")
        model_name = llm_config.get("model_name")
        temperature = llm_config.get("temperature", 0.2)
        max_tokens = llm_config.get("max_output_tokens", 2048)
        base_url = llm_config.get("base_url")

        log.info("Loading LLM", provider=provider, model=model_name)

        if provider == "google":
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=self.api_key_mgr.get("GOOGLE_API_KEY"),
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        if provider == "groq":
            return ChatGroq(
                model=model_name,
                api_key=self.api_key_mgr.get("GROQ_API_KEY"),
                temperature=temperature,
            )

        if provider == "openai":
            return ChatOpenAI(
                model=model_name,
                api_key=self.api_key_mgr.get(
                    "OPENAI_API_KEY",
                    fallback_keys=["OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY"],
                ),
                temperature=temperature,
                max_tokens=max_tokens,
                base_url=base_url,
            )

        if provider == "openrouter":
            return ChatOpenAI(
                model=model_name,
                api_key=self.api_key_mgr.get(
                    "OPENROUTER_API_KEY",
                    fallback_keys=["OPENAI_API_KEY", "YOUR_OPENROUTER_API_KEY"],
                ),
                temperature=temperature,
                max_tokens=max_tokens,
                base_url=base_url,
            )

        log.error("Unsupported LLM provider", provider=provider)
        raise ValueError(f"Unsupported LLM provider: {provider}")


if __name__ == "__main__":
    loader = ModelLoader()
    embeddings = loader.load_embeddings()
    print(f"Embedding Model Loaded: {embeddings}")
    result = embeddings.embed_query("Hello, how are you?")
    print(f"Embedding Result: {result}")

    llm = loader.load_llm()
    print(f"LLM Loaded: {llm}")
    response = llm.invoke("Hello, how are you?")
    print(f"LLM Result: {response}")