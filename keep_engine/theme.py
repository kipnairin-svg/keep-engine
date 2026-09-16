"""
Keep Engine — shared visual theme.

Same dark navy/gold/blue palette as Keep_Complete_9.16.26.pptx and
Keep_Product_Prototype.html, so the engine looks like it belongs to the
same product family as the deck and demo rather than a separate light-mode
tool. One place to keep the palette in sync; every page (nav, home,
clients, intake, report) pulls its CSS variables from here.
"""

THEME_VARS = """
    --navy:#0F1B3D; --navy2:#13234F; --blue:#2B5CE6; --gold:#C9A227;
    --bg:#040815; --card:#091124; --cardhover:#0D1530; --text:#F5F7FC;
    --ice:#B9C3DC; --muted:#8B93B8; --border:#1E2A52;
    --good:#1E9E6B; --goodtext:#3DDC97; --warn:#C9A227; --warntext:#E0BB4A;
    --bad:#D9534F; --badtext:#F0837E;
"""

# Base rules every page shares: root vars, resets, typography, and the
# translucent severity/status badge pattern used everywhere in the app.
BASE_CSS = """
  :root{""" + THEME_VARS + """}
  *{box-sizing:border-box;}
  body{margin:0;font-family:Calibri,'Segoe UI',Helvetica,Arial,sans-serif;color:var(--text);background:var(--bg);line-height:1.55;}
  h1,h2,h3,.serif{font-family:Cambria,Georgia,'Times New Roman',serif;}
  a{color:var(--blue);}
  .badge{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:4px 10px;border-radius:20px;}
  .badge-high{background:rgba(217,83,79,.16);color:var(--badtext);}
  .badge-medium{background:rgba(201,162,39,.16);color:var(--warntext);}
  .badge-low{background:rgba(43,92,230,.16);color:#8FA8FF;}
  .badge-good{background:rgba(30,158,107,.16);color:var(--goodtext);}
"""


def render_page(title: str, active: str, body_html: str, extra_css: str = "") -> str:
    """
    Shared page shell for the simpler list/stat pages (Home, Clients) --
    nav bar + dark theme + a centered .wrap container. Intake and the
    coverage report build their own markup since they're more custom, but
    pull the same BASE_CSS/NAV_CSS variables so every page matches.
    """
    from nav import render_nav, NAV_CSS

    return (
        "<!DOCTYPE html><html><head><title>Keep — " + title + "</title>"
        "<style>" + BASE_CSS + NAV_CSS + """
          .wrap{max-width:960px;margin:0 auto;padding:28px 24px 80px;}
          .wrap h1{font-size:22px;margin:0 0 22px;}
          table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;}
          th,td{text-align:left;padding:12px 16px;border-bottom:1px solid var(--border);font-size:13.5px;}
          th{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:1px;}
          tr:last-child td{border-bottom:none;}
          a{text-decoration:none;font-weight:600;}
        """ + extra_css + "</style></head><body>"
        + render_nav(active)
        + '<div class="wrap">' + body_html + "</div>"
        + "</body></html>"
    )
