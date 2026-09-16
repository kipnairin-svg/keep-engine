"""
Keep Engine — shared top navigation bar.

One consistent bar across Home, Clients, and Intake so the app feels like
one product instead of a few separate pages. render_nav(active) returns
the HTML; NAV_CSS is included once per page alongside theme.BASE_CSS.
"""

NAV_CSS = """
  .keep-nav{background:var(--card);border-bottom:1px solid var(--border);}
  .keep-nav-inner{max-width:960px;margin:0 auto;display:flex;align-items:center;gap:26px;padding:14px 24px;}
  .keep-nav-logo{color:var(--text);font-weight:800;letter-spacing:3px;font-size:15px;text-decoration:none;}
  .keep-nav-link{color:var(--ice);text-decoration:none;font-size:13.5px;font-weight:600;}
  .keep-nav-link:hover{color:var(--text);}
  .keep-nav-link.active{color:var(--gold);}
  .keep-nav-cta{margin-left:auto;background:var(--gold);color:var(--navy);padding:8px 16px;border-radius:20px;font-size:13px;font-weight:700;text-decoration:none;}
  .keep-nav-cta:hover{opacity:.9;}
"""


def render_nav(active: str = "") -> str:
    def cls(name):
        return "keep-nav-link active" if active == name else "keep-nav-link"

    return (
        '<div class="keep-nav"><div class="keep-nav-inner">'
        '<a href="/home" class="keep-nav-logo">KEEP</a>'
        '<a href="/home" class="' + cls("home") + '">Home</a>'
        '<a href="/dashboard" class="' + cls("clients") + '">Clients</a>'
        '<a href="/intake" class="keep-nav-cta">+ New Client</a>'
        '</div></div>'
    )
