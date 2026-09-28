"""FD package exports."""
from ai_cio.services.fd.holdings import (
    build_fd_intelligence,
    create_fixed_deposit,
    delete_fixed_deposit,
    list_fixed_deposits,
)
from ai_cio.services.fd.rates import get_fd_rates, scrape_bankbazaar_fd_rates

__all__ = [
    "build_fd_intelligence",
    "create_fixed_deposit",
    "delete_fixed_deposit",
    "list_fixed_deposits",
    "get_fd_rates",
    "scrape_bankbazaar_fd_rates",
]
