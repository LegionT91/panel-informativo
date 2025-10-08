"""
Paquete de controladores
"""
from .panel_controller import register_routes, require_login_for_panel, handle_needs_login

__all__ = ['register_routes', 'require_login_for_panel', 'handle_needs_login']

