"""Premium branding footer links for overlay, setup wizard, and dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PremiumFooterLink:
    label: str
    url: str
    icon: str
    color: str = "#E6EDF3"


PREMIUM_FOOTER_LINKS: tuple[PremiumFooterLink, ...] = (
    PremiumFooterLink("Web", "https://muhammad-faraz-dev.netlify.app", "🌐", "#58A6FF"),
    PremiumFooterLink("Facebook", "https://facebook.com/share/1JGnSNK2Mc", "f", "#1877F2"),
    PremiumFooterLink("Fiverr", "https://fiverr.com/s/qDKLLXX", "Fi", "#1DBF73"),
    PremiumFooterLink("Upwork", "https://upwork.com/freelancers/~018c67c9c97b482a3a", "Up", "#14A800"),
    PremiumFooterLink("GitHub", "https://github.com/farazgoal-boop", "GH", "#E6EDF3"),
    PremiumFooterLink("LinkedIn", "https://linkedin.com/in/m-faraz-85b175179", "in", "#0A66C2"),
    PremiumFooterLink("YouTube", "https://www.youtube.com/@farazautomation", "YT", "#FF0000"),
    PremiumFooterLink("Email", "mailto:farazautomation@gmail.com", "@", "#F0883E"),
)

BRAND_TITLE = "Faraz Automation"
BRAND_TAGLINE = "Career Copilot Premium by Faraz Automation"


def footer_links_html() -> str:
    items = []
    for link in PREMIUM_FOOTER_LINKS:
        items.append(
            f'<a class="premium-footer__link premium-footer__link--{link.label.lower()}" '
            f'href="{link.url}" target="_blank" rel="noopener noreferrer" '
            f'title="{link.label}">'
            f'<span class="premium-footer__icon" aria-hidden="true">{link.icon}</span>'
            f"<span>{link.label}</span></a>"
        )
    return (
        f'<footer class="premium-footer">'
        f'<div class="premium-footer__brand">{BRAND_TITLE}</div>'
        f'<div class="premium-footer__links">{"".join(items)}</div>'
        f"</footer>"
    )
