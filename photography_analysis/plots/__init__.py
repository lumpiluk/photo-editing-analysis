import fractions

from .metadata import plot_metadata, plot_photo_capture_hours_of_day
from .sessions import plot_sessions
from .time_between_photos import plot_time_between_photos


def fraction_formatter(x, pos):
    # (With help from Claude)
    if x <= 0:
        return "0"
    elif x < 1:
        frac = fractions.Fraction(x)
        if frac.numerator == 1:
            return f"1/{frac.denominator}"
        else:
            return f"{frac.numerator}/{frac.denominator}"
    else:
        if x == int(x):
            return f"{int(x)}s"
        else:
            return f"{x:.1f}s"


def aperture_formatter(x, pos):
    # We just pretend it's fractions
    return f"1/{x:g}"
