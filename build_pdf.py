"""Renders the markdown deliverables to HTML + PDF (headless Edge/Chrome). python build_pdf.py"""
import os, subprocess, time, markdown
CSS = """
@page { size: A4; margin: 14mm 14mm 14mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.2pt; line-height: 1.38; color: #1f1f1f; }
h1 { font-size: 17pt; margin: 0 0 2px; color: #0b3d91; }
h2 { font-size: 12pt; color: #0b3d91; border-bottom: 1px solid #c9d3e6; padding-bottom: 2px; margin: 14px 0 6px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 8px; font-size: 8.3pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #d0d7e2; padding: 3px 5px; vertical-align: top; text-align: left; }
th { background: #eef2f9; }
blockquote { margin: 6px 0; padding: 6px 10px; background: #f3f7ff; border-left: 3px solid #1a73e8; }
img { max-width: 100%; display: block; margin: 4px auto; }
code, pre { font-family: Consolas, monospace; font-size: 8pt; }
pre { background: #f6f8fa; padding: 6px; white-space: pre-wrap; }
hr { border: 0; border-top: 1px solid #ddd; margin: 8px 0; }
p { margin: 4px 0; } ul, ol { margin: 4px 0 4px 18px; padding: 0; }
"""
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
here = os.path.dirname(os.path.abspath(__file__))
for name in ["case-study", "note-to-procurement-lead"]:
    md = open(os.path.join(here, name + ".md"), encoding="utf-8").read()
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    css = CSS + (".note body{}" if name == "case-study" else "body{font-size:9.6pt}")
    page = f"<!doctype html><html><head><meta charset='utf-8'><title>{name}</title><style>{css}</style></head><body>{html}</body></html>"
    hp = os.path.join(here, name + ".html")
    open(hp, "w", encoding="utf-8").write(page)
    pdf = os.path.join(here, name + ".pdf")
    start = time.time()
    exe = next(b for b in BROWSERS if os.path.exists(b))
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--user-data-dir=" + os.path.join(os.environ.get("TEMP", here), "pdfprof_" + name),
                    f"--print-to-pdf={pdf}", "file:///" + hp.replace("\\", "/")], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    for _ in range(120):                      # headless Edge can finish writing after it returns
        if os.path.exists(pdf) and os.path.getmtime(pdf) > start and os.path.getsize(pdf) > 0:
            break
        time.sleep(0.5)
    else:
        raise SystemExit(f"{pdf} was not written (is it open in a viewer?)")
    print("wrote", pdf)
