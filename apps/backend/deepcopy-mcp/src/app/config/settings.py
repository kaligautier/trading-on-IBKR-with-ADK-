"""Configuration is loaded at the entry point, never at service import time."""

from typing import Literal, Self

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.api.deepcopy.config.settings import DeepcopyApiSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
        hide_input_in_errors=True,
    )

    # Server identity and transport
    name: str = Field(
        default="Deepcopy MCP",
        description="Server name exposed to MCP clients",
    )
    environment: Literal["local", "production"] = Field(
        default="local",
        description="Runtime profile used for transport and authentication checks",
    )
    transport: Literal["stdio", "http"] = Field(
        default="stdio",
        description="MCP transport used by the server",
    )
    host: str = Field(
        default="127.0.0.1",
        description="HTTP server bind address",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="HTTP server port",
    )
    # Logging configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum application logging level",
    )
    log_tool_arguments: bool = Field(
        default=True,
        description="Include tool call payloads, including arguments, in request logs",
    )
    log_max_payload_length: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum number of tool request payload characters logged",
    )

    # MCP listing and HTTP transport protection
    page_size: int = Field(
        default=100,
        ge=1,
        description="Maximum number of MCP components returned per listing page",
    )
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost"],
        description="Explicit HTTP Host header values accepted by the server",
    )
    allowed_origins: list[str] = Field(
        default_factory=list,
        description="Explicit HTTP Origin header values accepted by the server",
    )

    # Authentication configuration
    auth_mode: Literal["none", "jwt"] = Field(
        default="none",
        description="Authentication mode; production requires JWT verification",
    )
    jwt_jwks_uri: HttpUrl | None = Field(
        default=None,
        description="HTTPS endpoint providing signing keys for JWT verification",
    )
    jwt_issuer: str | None = Field(
        default=None,
        description="Expected JWT issuer, matched exactly",
    )
    jwt_audience: str | None = Field(
        default=None,
        description="Expected JWT audience",
    )
    required_scopes: list[str] = Field(
        default_factory=lambda: ["mcp:access"],
        description="Scopes required for authenticated access to the MCP server",
    )

    # Compatibility transforms
    resources_as_tools: bool = Field(
        default=False,
        description="Expose resource listing and reading as tools",
    )
    prompts_as_tools: bool = Field(
        default=False,
        description="Expose prompt listing and rendering as tools",
    )

    # Optional external API connections
    deepcopy_api: DeepcopyApiSettings | None = Field(
        default=None,
        description="Deepcopy API connection settings, including URL and token",
    )

    @model_validator(mode="after")
    def validate_api_transport(self) -> Self:
        for api in (self.deepcopy_api,):
            if api is None:
                continue
            local_http = self.environment == "local" and api.base_url.host in {
                "127.0.0.1",
                "localhost",
                "[::1]",
            }
            if api.base_url.scheme != "https" and not local_http:
                raise ValueError("API URL requires HTTPS except on local loopback")
        return self

    @model_validator(mode="after")
    def validate_auth(self) -> Self:
        if self.environment == "production" and self.auth_mode != "jwt":
            raise ValueError("Production requires JWT authentication")
        if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
            raise ValueError(
                "Explicit allowed hosts are required; wildcards are forbidden"
            )
        if any("*" in origin for origin in self.allowed_origins):
            raise ValueError("Allowed origins must be explicit")
        if self.auth_mode == "jwt":
            if not all((self.jwt_jwks_uri, self.jwt_issuer, self.jwt_audience)):
                raise ValueError("JWT auth requires JWKS URI, issuer and audience")
            if self.jwt_jwks_uri and self.jwt_jwks_uri.scheme != "https":
                raise ValueError("JWT JWKS URI must use HTTPS")
            if self.transport != "http":
                raise ValueError("JWT auth requires HTTP; STDIO uses process access")
            if not self.required_scopes or any(
                not s.strip() for s in self.required_scopes
            ):
                raise ValueError("JWT auth requires nonempty scopes")
        return self
