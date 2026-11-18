# -*- coding: utf-8 -*-
"""Genere les livrables DOCX + PDF du Jour 2 a partir de docs_src/.
Sortie : Jour2/UC03_Hadoop_HDFS.docx/.pdf, Jour2/UC04_ingestion_NiFi.docx/.pdf,
         Jour2/README_Jour2.docx/.pdf, Jour2/UC03_preuves/00_index_preuves.docx/.pdf,
         Jour2/UC04_preuves/00_index_preuves.docx/.pdf
"""
import html
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_gen2", "docs_src")
IMG_DIR = os.path.join(SRC, "diagrams")
TMP = os.path.join(ROOT, "_gen2", "html")
os.makedirs(TMP, exist_ok=True)

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE):
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

def parse_md(text):
    lines = text.splitlines()
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1; continue
        if line.startswith("```"):
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            blocks.append(("code", buf)); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip())); i += 1; continue
        if line.lstrip().startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                tbl.append(lines[i].strip()); i += 1
            if len(tbl) > 1 and re.match(r"^\|[\s:|-]+\|?$", tbl[1]):
                rows = [[c.strip() for c in r.strip("|").split("|")] for r in [tbl[0]] + tbl[2:]]
                blocks.append(("table", rows))
            else:
                blocks.append(("p", " ".join(t.strip() for t in tbl)))
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)$", line.strip())
        if m:
            blocks.append(("img", m.group(1), m.group(2))); i += 1; continue
        if re.match(r"^[-*] ", line.strip()) or re.match(r"^\d+\. ", line.strip()):
            items, ordered = [], bool(re.match(r"^\d+\. ", line.strip()))
            while i < len(lines) and re.match(r"^\s*(?:[-*]|\d+\.) ", lines[i]):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.) ", "", lines[i]).strip()); i += 1
            blocks.append(("list", items, ordered)); continue
        para = [line.strip()]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|```|\s*\||!\[|\s*[-*] |\s*\d+\. )", lines[i]):
            para.append(lines[i].strip()); i += 1
        blocks.append(("p", " ".join(para)))
    return blocks

def md_of(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return parse_md(f.read())

def md_until(name, stop_heading):
    """Blocs du fichier jusqu'au premier titre h2 commencant par stop_heading."""
    out = []
    for b in md_of(name):
        if b[0] == "h" and b[1] <= 2 and b[2].lower().startswith(stop_heading.lower()):
            break
        out.append(b)
    return out

def body(name, stop_heading=None):
    """Contenu sans le h1 de titre (deja dans le bandeau)."""
    blocks = md_until(name, stop_heading) if stop_heading else md_of(name)
    if blocks and blocks[0][0] == "h" and blocks[0][1] == 1:
        blocks = blocks[1:]
    return blocks

def resolve_img(path):
    if path.startswith("diagrams/"):
        return os.path.join(IMG_DIR, os.path.basename(path))
    return os.path.join(SRC, path)

def _shade(cell, color="D9D9D9"):
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear"); el.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(el)

def _inline(par, text):
    for tok in re.split(r"(\*\*.+?\*\*|`.+?`)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("`"):
            r = par.add_run(tok[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9.5)
        else:
            par.add_run(tok)

def docx_blocks(doc, blocks, level_shift=0):
    for b in blocks:
        if b[0] == "h":
            h = doc.add_heading(level=min(b[1] + level_shift, 4))
            r = h.add_run(b[2]); r.font.color.rgb = RGBColor(0, 0, 0)
        elif b[0] == "p":
            _inline(doc.add_paragraph(), b[1])
        elif b[0] == "list":
            style = "List Number" if b[2] else "List Bullet"
            for it in b[1]:
                _inline(doc.add_paragraph(style=style), it)
        elif b[0] == "code":
            p = doc.add_paragraph()
            for i, ln in enumerate(b[1]):
                r = p.add_run(ln + ("\n" if i < len(b[1]) - 1 else ""))
                r.font.name = "Consolas"; r.font.size = Pt(8.5)
            p.paragraph_format.left_indent = Cm(0.5)
        elif b[0] == "img":
            path = resolve_img(b[2])
            if os.path.exists(path):
                doc.add_picture(path, width=Cm(16))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap = doc.add_paragraph()
                r = cap.add_run(b[1]); r.italic = True; r.font.size = Pt(9)
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif b[0] == "table":
            rows = b[1]
            ncols = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=ncols)
            t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, row in enumerate(rows):
                for ci in range(ncols):
                    cell = t.cell(ri, ci)
                    cell.text = ""
                    par = cell.paragraphs[0]
                    txt = row[ci] if ci < len(row) else ""
                    run = par.add_run(txt)
                    run.font.size = Pt(8.5)
                    if ri == 0:
                        run.bold = True; _shade(cell)
                    else:
                        _shade(cell, "FFFFFF")
            doc.add_paragraph()

def new_docx():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"; st.font.size = Pt(11)
    for name, size in [("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 12), ("Heading 4", 11)]:
        s = doc.styles[name]
        s.font.name = "Calibri"; s.font.size = Pt(size)
        s.font.color.rgb = RGBColor(0, 0, 0); s.font.bold = True
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.2)
        sec.top_margin = sec.bottom_margin = Cm(2.2)
    return doc

def docx_title(doc, title_lines):
    for i, (txt, size, bold) in enumerate(title_lines):
        p = doc.add_paragraph()
        r = p.add_run(txt)
        r.font.size = Pt(size); r.bold = bold
        if i == 0:
            r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
    doc.add_paragraph()

def save_docx(path, title_lines, parts):
    doc = new_docx()
    docx_title(doc, title_lines)
    for h1, blocks in parts:
        if h1:
            h = doc.add_heading(level=1)
            r = h.add_run(h1); r.font.color.rgb = RGBColor(0, 0, 0)
        docx_blocks(doc, blocks)
    doc.save(path)

def inline_html(text):
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t

def html_blocks(blocks):
    out = []
    for b in blocks:
        if b[0] == "h":
            lv = min(b[1], 4)
            out.append(f"<h{lv}>{inline_html(b[2])}</h{lv}>")
        elif b[0] == "p":
            out.append(f"<p>{inline_html(b[1])}</p>")
        elif b[0] == "list":
            tag = "ol" if b[2] else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline_html(i)}</li>" for i in b[1]) + f"</{tag}>")
        elif b[0] == "code":
            out.append("<pre>" + html.escape("\n".join(b[1])) + "</pre>")
        elif b[0] == "img":
            src = os.path.basename(b[2])
            out.append(f'<p class="fig"><img src="diagrams/{src}"><br><span class="cap">{inline_html(b[1])}</span></p>')
        elif b[0] == "table":
            rows = b[1]
            trs = []
            for ri, row in enumerate(rows):
                tag = "th" if ri == 0 else "td"
                trs.append("<tr>" + "".join(f"<{tag}>{inline_html(c)}</{tag}>" for c in row) + "</tr>")
            out.append("<table>" + "".join(trs) + "</table>")
    return "\n".join(out)

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: Calibri, Arial, sans-serif; font-size: 10.5pt; color: #111; line-height: 1.4; }
h1 { font-size: 16pt; border-bottom: 2px solid #333; padding-bottom: 4px; page-break-before: always; }
h1:first-of-type { page-break-before: auto; }
h2 { font-size: 13pt; margin-top: 18px; }
h3 { font-size: 11.5pt; margin-top: 14px; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 8px 0; }
th, td { border: 1px solid #888; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #e8e8e8; }
pre { background: #f4f4f4; border: 1px solid #ccc; padding: 6px; font-family: Consolas, monospace; font-size: 8pt; white-space: pre-wrap; }
code { font-family: Consolas, monospace; font-size: 9pt; }
.fig { text-align: center; margin: 10px 0; }
.fig img { max-width: 100%; }
.cap { font-size: 9pt; font-style: italic; color: #333; }
.ttl p { margin: 2px 0; }
.ttl .t0 { color: #555; font-size: 11pt; }
.ttl .t1 { font-size: 15pt; font-weight: bold; }
.ttl .t2 { font-size: 11pt; }
"""

def save_pdf(path, title_lines, parts):
    body = ['<div class="ttl">']
    for i, (txt, size, bold) in enumerate(title_lines):
        body.append(f'<p class="t{i}">{html.escape(txt)}</p>')
    body.append("</div><hr>")
    for h1, blocks in parts:
        if h1:
            body.append(f"<h1>{html.escape(h1)}</h1>")
        body.append(html_blocks(blocks))
    doc_html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
    base = os.path.basename(path).replace(".pdf", "")
    html_path = os.path.join(TMP, base + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc_html)
    img_out = os.path.join(TMP, "diagrams")
    os.makedirs(img_out, exist_ok=True)
    for fn in os.listdir(IMG_DIR):
        if fn.endswith(".png"):
            src = os.path.join(IMG_DIR, fn)
            dst = os.path.join(img_out, fn)
            if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                with open(src, "rb") as a, open(dst, "wb") as b:
                    b.write(a.read())
    pdf_tmp = os.path.join(TMP, base + ".pdf")
    subprocess.run([EDGE, "--headless", "--disable-gpu",
                    f"--print-to-pdf={pdf_tmp}",
                    "--no-pdf-header-footer",
                    "file:///" + html_path.replace("\\", "/")],
                   check=True, capture_output=True, timeout=120)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(pdf_tmp, "rb") as a, open(path, "wb") as b:
        b.write(a.read())

AUTHOR = ("Amani Layouni — Mastère Data & IA (IPSSI)", 11, False)
TL = ("Retail Intelligence — TP Jour 2", 11, False)

def ttl(main):
    return [TL, (main, 15, True), AUTHOR]

def main():
    jobs = [
        (os.path.join(ROOT, "Jour2", "UC03_Hadoop_HDFS"),
         ttl("UC-03 : Hadoop, HDFS et création du Data Lake"),
         [(None, body("UC03.md"))]),
        (os.path.join(ROOT, "Jour2", "UC04_ingestion_NiFi"),
         ttl("UC-04 : Ingestion et orchestration avec Apache NiFi"),
         [(None, body("UC04.md"))]),
        (os.path.join(ROOT, "Jour2", "README_Jour2"),
         ttl("README — reproduction des manipulations du Jour 2"),
         [(None, body("README_Jour2.md"))]),
        (os.path.join(ROOT, "Jour2", "UC03_preuves", "00_index_preuves"),
         ttl("Preuves UC-03"),
         [(None, body("annexe_UC03.md"))]),
        (os.path.join(ROOT, "Jour2", "UC04_preuves", "00_index_preuves"),
         ttl("Preuves UC-04"),
         [(None, body("annexe_UC04.md"))]),
        (os.path.join(ROOT, "Jour2", "livrables_jour2"),
         ttl("Livrables du Jour 2 — document unique"),
         [("Partie 1 : UC-03 — Hadoop, HDFS et création du Data Lake",
           body("UC03.md", "Questions de recul")),
          ("Partie 2 : UC-04 — Ingestion et orchestration avec Apache NiFi",
           body("UC04.md", "Questions de recul")),
          ("Partie 3 : erreurs, traçabilité et provenance",
           md_of("erreurs_tracabilite.md")),
          ("Partie 4 : questions de recul",
           md_of("questions_recul.md")),
          ("Annexe A : preuves UC-03", md_of("annexe_UC03.md")),
          ("Annexe B : preuves UC-04", md_of("annexe_UC04.md"))]),
    ]
    for base, title, parts in jobs:
        save_docx(base + ".docx", title, parts)
        print("docx :", base + ".docx")
        save_pdf(base + ".pdf", title, parts)
        print("pdf  :", base + ".pdf")

if __name__ == "__main__":
    main()
