from .start import router as start_router
from .games import router as games_router
from .deposit import router as deposit_router
from .settings import router as settings_router
from .referral import router as referral_router
from .admin import router as admin_router
from .inline import router as inline_router
from .pvp import router as pvp_router
from .lottery import router as lottery_router
from .mini_app import router as mini_app_router

__all__ = [
    'start_router',
    'games_router',
    'deposit_router',
    'settings_router',
    'referral_router',
    'admin_router',
    'inline_router',
    'pvp_router',
    'lottery_router',
    'mini_app_router',
]

