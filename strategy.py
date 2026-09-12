from dataclasses import dataclass


@dataclass
class Signal:
    action: str
    reason: str


def get_signal(price: float) -> Signal:
    """
    Foreløpig kun testlogikk.

    Vi skal IKKE la denne funksjonen sende ordre.
    """

    return Signal(
        action="HOLD",
        reason="Ingen automatisk handel aktivert ennå."
    )