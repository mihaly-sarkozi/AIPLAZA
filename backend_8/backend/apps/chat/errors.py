from __future__ import annotations

from core.kernel.http.app_errors import AppError


class ChatError(AppError):
    code = "CHAT_ERROR"
    status_code = 500
    safe_message = "Chat operation failed."


class ChatPermissionDenied(ChatError, PermissionError):
    code = "CHAT_PERMISSION_DENIED"
    status_code = 403
    safe_message = "You are not allowed to use this chat channel."


class ChatRequestInvalid(ChatError):
    code = "CHAT_REQUEST_INVALID"
    status_code = 400
    safe_message = "Chat request is invalid."


class ChatPolicyViolation(ChatError):
    code = "CHAT_POLICY_VIOLATION"
    status_code = 422
    safe_message = "Chat request violates policy."


class ChatProviderUnavailable(ChatError):
    code = "CHAT_PROVIDER_UNAVAILABLE"
    status_code = 503
    safe_message = "Chat provider is unavailable."


class ChatBudgetUnavailable(ChatError):
    code = "CHAT_BUDGET_UNAVAILABLE"
    status_code = 503
    safe_message = "Chat budget tracking is unavailable."


class ChatConfigurationError(ChatError):
    code = "CHAT_CONFIGURATION_ERROR"
    status_code = 503
    safe_message = "Chat service is not configured."


class ChannelCredentialRejected(ChatError):
    code = "CHANNEL_CREDENTIAL_REJECTED"
    status_code = 401
    safe_message = "The channel credential was rejected."


class ChannelCredentialPolicyInvalid(ChatError):
    code = "CHANNEL_CREDENTIAL_POLICY_INVALID"
    status_code = 400
    safe_message = "Channel credential policy is invalid."


class ChannelCredentialNotFound(ChatError):
    code = "CHANNEL_CREDENTIAL_NOT_FOUND"
    status_code = 404
    safe_message = "Channel credential not found."


class ChannelFeedbackNotFound(ChatError):
    code = "CHANNEL_FEEDBACK_NOT_FOUND"
    status_code = 404
    safe_message = "Channel feedback was not found."


__all__ = [
    "ChannelCredentialNotFound",
    "ChannelCredentialPolicyInvalid",
    "ChannelCredentialRejected",
    "ChannelFeedbackNotFound",
    "ChatBudgetUnavailable",
    "ChatConfigurationError",
    "ChatError",
    "ChatPermissionDenied",
    "ChatPolicyViolation",
    "ChatProviderUnavailable",
    "ChatRequestInvalid",
]
