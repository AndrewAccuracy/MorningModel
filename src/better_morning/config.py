from typing import List, Optional, Literal, Union
from pydantic import BaseModel, HttpUrl, Field, validator
import toml
import os
import re


# --- LLM Settings ---
class LLMSettings(BaseModel):
    reasoner_model: str = ""
    light_model: str = ""
    temperature: float = 0.7
    n_most_important_news: int = 5
    k_words_each_summary: int = 100
    prompt_template: Optional[str] = None  # Collection-specific prompt or for filtering
    article_selection_prompt_template: Optional[str] = None
    collection_summary_prompt_template: Optional[str] = None
    filter_prompt_template: Optional[str] = None
    output_language: str = "english"  # Added language setting
    thinking_effort_reasoner: Optional[Union[int, str]] = (
        None  # Thinking effort for reasoner model (tokens or effort level)
    )
    thinking_effort_light: Optional[Union[int, str]] = (
        None  # Thinking effort for light model (tokens or effort level)
    )
    api_key: Optional[str] = None  # To hold the resolved API key


# --- Filter Settings ---
class FilterSettings(BaseModel):
    filter_query: Optional[str] = None
    filter_model: Optional[str] = None


# --- Content Extraction Settings ---
class ContentExtractionSettings(BaseModel):
    follow_article_links: bool = False
    parser_type: Optional[str] = "html.parser"
    link_filter_pattern: Optional[str] = None
    browser_sandbox: bool = True
    allow_private_networks: bool = False


# --- Output Settings ---
class OutputSettings(BaseModel):
    output_type: Literal["github_release", "email"] = "github_release"
    # Set email_provider to auto-configure smtp_server and smtp_port.
    # Supported values: gmail, outlook, icloud, qq, 163, 126, yahoo, zoho, custom
    # Use "custom" (or leave unset) to specify smtp_server/smtp_port manually.
    email_provider: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_username_env: Optional[str] = "BETTER_MORNING_SMTP_USERNAME"
    smtp_password_env: Optional[str] = "BETTER_MORNING_SMTP_PASSWORD"
    recipient_email_env: Optional[str] = "BETTER_MORNING_RECIPIENT_EMAIL"
    github_token_env: Optional[str] = "BETTER_MORNING_GITHUB_TOKEN"


# --- Global Configuration ---
class GlobalConfig(BaseModel):
    llm_api_token_env: str = (
        "BETTER_MORNING_LLM_API_KEY"  # Default env var for LLM API token
    )
    token_size_threshold: int = 128 * 1024  # 128K tokens
    max_articles_per_collection: int = 100  # Global limit for articles per collection
    content_extraction_batch_size: int = 10  # Batch size for content extraction
    context_digest_size: int = (
        3  # Number of previous digests to send as context to models
    )
    history_retention_days: int = 7  # Days to keep articles in history
    adaptive_search_enabled: bool = True
    adaptive_search_lookback_days: int = 7
    llm_settings: LLMSettings = Field(default_factory=LLMSettings)
    filter_settings: FilterSettings = Field(default_factory=FilterSettings)
    content_extraction_settings: ContentExtractionSettings = Field(
        default_factory=ContentExtractionSettings
    )
    output_settings: OutputSettings = Field(default_factory=OutputSettings)


# --- RSS Feed Definition ---
class RSSFeed(BaseModel):
    url: HttpUrl
    name: Optional[str] = None  # Name is optional now
    max_articles: Optional[int] = None  # Max articles to fetch from this feed
    follow_article_links: Optional[bool] = None  # Per-source link following setting
    timeout: Optional[int] = 30  # Per-feed timeout in seconds (default 30s)
    max_retries: Optional[int] = 3  # Per-feed max retry attempts (default 3)
    filter_query: Optional[str] = None
    filter_model: Optional[str] = None
    credibility_tier: Optional[int] = None  # 1-5 manual source trust override
    readership_tier: Optional[int] = None  # 1-5 manual audience reach override


# --- Collection-specific overrides (for parsing TOML) ---
class CollectionOverrides(BaseModel):
    llm_settings: Optional[LLMSettings] = None
    filter_settings: Optional[FilterSettings] = None
    content_extraction_settings: Optional[ContentExtractionSettings] = None
    collection_prompt: Optional[str] = None  # Prompt specific to this collection
    max_age: Optional[Union[str, None]] = (
        None  # Maximum age for articles (e.g., "2d", "24h", "last-digest")
    )

    @validator("max_age")
    def validate_max_age(cls, v):
        if v is None:
            return v
        if v == "last-digest":
            return v
        # Validate time span format (e.g., "1h", "2d", "30m")
        pattern = r"^(\d+)([hdm])$"
        if not re.match(pattern, v):
            raise ValueError(
                "max_age must be 'last-digest' or a time span in format like '1h', '2d', '30m'"
            )
        return v


# --- Fully resolved Collection Configuration ---
class Collection(BaseModel):
    name: str
    feeds: List[RSSFeed]
    # These will hold the *resolved* settings after merging with global
    llm_settings: LLMSettings
    filter_settings: FilterSettings
    content_extraction_settings: ContentExtractionSettings
    collection_prompt: Optional[str] = None
    max_age: Optional[str] = None  # Maximum age for articles


# --- Main Configuration Loader ---
GLOBAL_CONFIG_FILE = "config.toml"  # Assuming global config is at project root


EMAIL_PROVIDER_PROFILES = {
    # Western providers
    "gmail": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "note": "Requires a Gmail App Password (2-Step Verification must be enabled). "
                "Generate one at https://myaccount.google.com/apppasswords",
    },
    "outlook": {
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
        "note": "Works with Outlook, Hotmail, and Microsoft 365 accounts. "
                "Use an App Password if MFA is enabled.",
    },
    "hotmail": {  # alias for outlook
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
        "note": "Alias for outlook. Use an App Password if MFA is enabled.",
    },
    "icloud": {
        "smtp_server": "smtp.mail.me.com",
        "smtp_port": 587,
        "note": "Requires an Apple App-Specific Password. "
                "Generate one at https://appleid.apple.com/account/manage",
    },
    "yahoo": {
        "smtp_server": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "note": "Requires a Yahoo App Password. "
                "Generate one at https://login.yahoo.com/account/security",
    },
    "zoho": {
        "smtp_server": "smtp.zoho.com",
        "smtp_port": 587,
        "note": "Works with Zoho Mail free and paid accounts.",
    },
    # Chinese providers
    "qq": {
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "note": "Requires a QQ Mail authorization code (授权码), NOT your QQ password. "
                "Enable SMTP and generate a code at: QQ Mail → Settings → Account → POP3/SMTP.",
    },
    "163": {
        "smtp_server": "smtp.163.com",
        "smtp_port": 465,
        "note": "Requires a 163 Mail authorization code (客户端授权密码). "
                "Enable SMTP at: 163 Mail → Settings → POP3/SMTP/IMAP.",
    },
    "126": {
        "smtp_server": "smtp.126.com",
        "smtp_port": 465,
        "note": "Requires a 126 Mail authorization code (客户端授权密码). "
                "Enable SMTP at: 126 Mail → Settings → POP3/SMTP/IMAP.",
    },
    "sina": {
        "smtp_server": "smtp.sina.com",
        "smtp_port": 465,
        "note": "Requires Sina Mail SMTP to be enabled and an authorization code.",
    },
}


def apply_email_provider_overrides(config: GlobalConfig) -> GlobalConfig:
    """Auto-configure smtp_server and smtp_port from email_provider if set.

    Explicit smtp_server / smtp_port values in config.toml always win over the
    provider profile so that advanced users can still override individual fields.
    """
    provider = (config.output_settings.email_provider or "").lower().strip()
    if not provider or provider == "custom":
        return config

    profile = EMAIL_PROVIDER_PROFILES.get(provider)
    if profile is None:
        known = ", ".join(sorted(EMAIL_PROVIDER_PROFILES))
        print(
            f"Warning: Unknown email_provider '{provider}'. "
            f"Known providers: {known}. "
            "Falling back to manual smtp_server / smtp_port settings."
        )
        return config

    # Only apply profile values when the field hasn't been set explicitly.
    if config.output_settings.smtp_server is None:
        config.output_settings.smtp_server = profile["smtp_server"]
    if config.output_settings.smtp_port == 587 and profile["smtp_port"] != 587:
        # 587 is the Pydantic default — treat it as "not explicitly set" so the
        # profile port wins.  Users who really want 587 can set it explicitly.
        config.output_settings.smtp_port = profile["smtp_port"]

    return config


LLM_PROVIDER_PROFILES = {
    "openai": {
        "reasoner_model": "openai/gpt-4o",
        "light_model": "openai/gpt-4o-mini",
        "filter_model": "openai/gpt-4o",
        "api_key_env": "BETTER_MORNING_OPENAI_API_KEY",
    },
    "deepseek": {
        "reasoner_model": "deepseek/deepseek-reasoner",
        "light_model": "deepseek/deepseek-chat",
        "filter_model": "deepseek/deepseek-chat",
        "api_key_env": "BETTER_MORNING_DEEPSEEK_API_KEY",
    },
    "gemini": {
        "reasoner_model": "gemini/gemini-2.5-pro",
        "light_model": "gemini/gemini-2.5-flash",
        "filter_model": "gemini/gemini-2.5-flash",
        "api_key_env": "BETTER_MORNING_GEMINI_API_KEY",
    },
}


def infer_llm_provider() -> str:
    """Infer provider from explicit choice or the single filled provider key."""
    explicit_provider = os.getenv("BETTER_MORNING_LLM_PROVIDER", "auto").lower().strip()
    if explicit_provider and explicit_provider != "auto":
        return explicit_provider

    configured_providers = [
        provider
        for provider, profile in LLM_PROVIDER_PROFILES.items()
        if os.getenv(profile["api_key_env"])
    ]
    if len(configured_providers) == 1:
        return configured_providers[0]

    generic_api_key = os.getenv("BETTER_MORNING_LLM_API_KEY")
    if generic_api_key and generic_api_key.startswith("AIza"):
        return "gemini"

    return "openai"


def apply_llm_env_overrides(config: GlobalConfig) -> GlobalConfig:
    """Allow .env.local to select provider/model without editing tracked config files."""
    provider = infer_llm_provider()
    profile = LLM_PROVIDER_PROFILES.get(provider)

    if profile:
        provider_key_env = profile["api_key_env"]
        if os.getenv(provider_key_env):
            config.llm_api_token_env = provider_key_env
        config.llm_settings.reasoner_model = profile["reasoner_model"]
        config.llm_settings.light_model = profile["light_model"]
        config.filter_settings.filter_model = profile["filter_model"]
    elif provider:
        print(
            f"Warning: Unknown BETTER_MORNING_LLM_PROVIDER '{provider}'. Falling back to config.toml model settings."
        )

    reasoner_model = os.getenv("BETTER_MORNING_REASONER_MODEL")
    if reasoner_model:
        config.llm_settings.reasoner_model = reasoner_model

    light_model = os.getenv("BETTER_MORNING_LIGHT_MODEL")
    if light_model:
        config.llm_settings.light_model = light_model

    filter_model = os.getenv("BETTER_MORNING_FILTER_MODEL")
    if filter_model:
        config.filter_settings.filter_model = filter_model

    # Allow output language override via env var.
    # Example: BETTER_MORNING_OUTPUT_LANGUAGE=English
    output_language = os.getenv("BETTER_MORNING_OUTPUT_LANGUAGE")
    if output_language:
        config.llm_settings.output_language = output_language

    return config


def load_global_config(path: str = GLOBAL_CONFIG_FILE) -> GlobalConfig:
    try:
        if not os.path.exists(path):
            print(
                f"Warning: Global config file '{path}' not found. Using default global settings."
            )
            config = GlobalConfig()
        else:
            data = toml.load(path)
            config = GlobalConfig(**data)
        config = apply_llm_env_overrides(config)
        config = apply_email_provider_overrides(config)

        # After loading, immediately try to resolve the API key
        try:
            api_key = get_secret(config.llm_api_token_env, "Global LLM API Key")
            config.llm_settings.api_key = api_key
        except ValueError as e:
            print(
                f"Warning: Could not resolve the global LLM API key. LLM calls may fail. Error: {e}"
            )

        return config
    except Exception as e:
        print(f"Error loading or validating global config from {path}: {e}")
        raise


def load_collection(collection_path: str, global_config: GlobalConfig) -> Collection:
    """
    Loads a collection configuration, merging with global settings.
    """
    try:
        collection_data = toml.load(collection_path)

        # Allow `follow_article_links` to be a top-level key in collection TOML for convenience.
        # If it exists, we move it into the `content_extraction_settings` dictionary before parsing.
        if "follow_article_links" in collection_data:
            if "content_extraction_settings" not in collection_data:
                collection_data["content_extraction_settings"] = {}
            # This will overwrite if a value also exists in the dictionary, which is desired.
            collection_data["content_extraction_settings"]["follow_article_links"] = (
                collection_data.pop("follow_article_links")
            )

        # Use CollectionOverrides to parse the collection-specific fields from TOML
        # This allows for partial override declarations without requiring all fields
        overrides = CollectionOverrides(
            llm_settings=collection_data.get("llm_settings"),
            filter_settings=collection_data.get("filter_settings"),
            content_extraction_settings=collection_data.get(
                "content_extraction_settings"
            ),
            collection_prompt=collection_data.get("collection_prompt"),
            max_age=collection_data.get("max_age"),
        )

        # Merge LLM settings: collection overrides global defaults
        # Start with the base defaults from the Pydantic model.
        resolved_llm_settings_data = LLMSettings().model_dump()
        # Layer the global config settings on top.
        resolved_llm_settings_data.update(
            global_config.llm_settings.model_dump(exclude_unset=True)
        )
        # Finally, layer the collection-specific settings, which take highest priority.
        if overrides.llm_settings:
            resolved_llm_settings_data.update(
                overrides.llm_settings.model_dump(exclude_unset=True)
            )
        resolved_llm_settings = LLMSettings(**resolved_llm_settings_data)
        resolved_global_config = apply_llm_env_overrides(global_config)
        resolved_llm_settings.reasoner_model = (
            resolved_global_config.llm_settings.reasoner_model
        )
        resolved_llm_settings.light_model = resolved_global_config.llm_settings.light_model

        # After resolving the model, resolve and set the API key for it.
        try:
            api_key = get_secret(
                global_config.llm_api_token_env,
                f"LLM API Token for model '{resolved_llm_settings.reasoner_model}'",
            )
            resolved_llm_settings.api_key = api_key
        except ValueError as e:
            print(
                f"Warning: Could not resolve API key for collection '{collection_data['name']}'. LLM calls may fail. Error: {e}"
            )

        # Merge Content Extraction settings: collection overrides global defaults
        # Apply the same hierarchical merging logic.
        resolved_content_extraction_settings_data = (
            ContentExtractionSettings().model_dump()
        )
        resolved_content_extraction_settings_data.update(
            global_config.content_extraction_settings.model_dump(exclude_unset=True)
        )
        if overrides.content_extraction_settings:
            resolved_content_extraction_settings_data.update(
                overrides.content_extraction_settings.model_dump(exclude_unset=True)
            )
        resolved_content_extraction_settings = ContentExtractionSettings(
            **resolved_content_extraction_settings_data
        )

        # Merge Filter settings: collection overrides global defaults
        resolved_filter_settings_data = FilterSettings().model_dump()
        resolved_filter_settings_data.update(
            global_config.filter_settings.model_dump(exclude_unset=True)
        )
        if overrides.filter_settings:
            resolved_filter_settings_data.update(
                overrides.filter_settings.model_dump(exclude_unset=True)
            )
        resolved_filter_settings = FilterSettings(**resolved_filter_settings_data)
        resolved_filter_settings.filter_model = (
            resolved_global_config.filter_settings.filter_model
        )

        # Construct the final Collection object with resolved settings
        return Collection(
            name=collection_data["name"],
            feeds=[RSSFeed(**f) for f in collection_data["feeds"]],
            llm_settings=resolved_llm_settings,
            filter_settings=resolved_filter_settings,
            content_extraction_settings=resolved_content_extraction_settings,
            collection_prompt=overrides.collection_prompt,
            max_age=overrides.max_age,
        )
    except Exception as e:
        print(
            f"Error loading or validating collection config from {collection_path}: {e}"
        )
        raise


def get_secret(env_var_name: Optional[str], config_name: str) -> str:
    """Retrieves a secret from environment variables."""
    if env_var_name is None:
        raise ValueError(
            f"Environment variable name for {config_name} is not configured."
        )
    secret = os.getenv(env_var_name)
    if secret is None:
        raise ValueError(
            f"Environment variable '{env_var_name}' for {config_name} is not set."
        )
    return secret
