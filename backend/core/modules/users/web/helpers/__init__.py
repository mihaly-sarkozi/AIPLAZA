# backend/core/modules/users/web/helpers/__init__.py
# Feladat: A users web helper csomag exportfelülete. Profilhoz kapcsolódó helper importok számára biztosít namespace-t. Vékony users web helper belépési pont.
# Sárközi Mihály - 2026.05.21

from .profile_helper import effective_locale_theme

__all__ = ["effective_locale_theme"]
