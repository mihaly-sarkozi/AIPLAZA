from __future__ import annotations

from core.kernel.http.app_errors import AppError


class ChatError(AppError):
    code = "CHAT_ERROR"
    status_code = 500
    safe_message = "Chat operation failed."


class ChatPermissionDenied(ChatError):
    code = "CHAT_PERMISSION_DENIED"
    status_code = 403
    safe_message = "No permission to use the requested chat resource."


class ChatPolicyViolation(ChatError):
    code = "CHAT_POLICY_VIOLATION"
    status_code = 422
    safe_message = "Chat request violates policy."


class ChatProviderUnavailable(ChatError):
    code = "CHAT_PROVIDER_UNAVAILABLE"
    status_code = 503
    safe_message = "Chat provider is unavailable."


class ChatConfigurationError(ChatError):
    code = "CHAT_CONFIGURATION_ERROR"
    status_code = 503
    safe_message = "Chat service is not configured."


class ChannelCredentialRejected(ChatError):
    code = "CHANNEL_CREDENTIAL_REJECTED"
    status_code = 401
    safe_message = "Channel credential was rejected."


class ChannelCredentialPolicyInvalid(ChatError):
    code = "CHANNEL_CREDENTIAL_POLICY_INVALID"
    status_code = 400
    safe_message = "Channel credential policy is invalid."


class ChannelCredentialNotFound(ChatError):
    code = "CHANNEL_CREDENTIAL_NOT_FOUND"
    status_code = 404
    safe_message = "Channel credential not found."


__all__ = [
    "ChannelCredentialNotFound",
    "ChannelCredentialPolicyInvalid",
    "ChannelCredentialRejected",
    "ChatConfigurationError",
    "ChatError",
    "ChatPermissionDenied",
    "ChatPolicyViolation",
    "ChatProviderUnavailable",
]
