# Ez a fájl a(z) apps/features/chat/container csomag exportjait és inicializálási pontjait fogja össze.
from .chat_container import ChatFeatureContainer, build_chat_feature

__all__ = ["ChatFeatureContainer", "build_chat_feature"]
