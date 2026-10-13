"""Convierte rag/documents/*.md a PDF (rag/documents/pdf/*.pdf).

Los PDFs generados se versionan en el repo (el enunciado exige PDFs), así que
este script solo hace falta si se edita algún .md.
Soporta el subconjunto de Markdown usado en los documentos: títulos (#, ##),
listas (-, 1.), tablas simples, negritas (**x**) y párrafos.
"""
import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).parent
SRC = ROOT / "documents"
OUT = SRC / "pdf"

# Fuente Unicode (acentos, ñ, ¿). Primera que exista.
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def find_fonts():
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    sys.exit("No se encontró una fuente TrueType Unicode (Arial o DejaVu Sans)")


class Doc(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("body", size=8)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")


def strip_inline(text: str) -> str:
    return text.replace("**", "").replace("`", "")


def render(md: str, regular: str, bold: str) -> Doc:
    pdf = Doc(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_font("body", "", regular)
    pdf.add_font("body", "B", bold)
    pdf.add_page()

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            pdf.ln(2)
        elif line.startswith("# "):
            pdf.set_font("body", "B", 18)
            pdf.multi_cell(0, 9, strip_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("body", "B", 13)
            pdf.multi_cell(0, 7, strip_inline(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append([strip_inline(c) for c in cells])
                i += 1
            i -= 1
            with pdf.table(first_row_as_headings=True, text_align="LEFT") as table:
                pdf.set_font("body", size=10)
                for r in rows:
                    row = table.row()
                    for c in r:
                        row.cell(c)
            pdf.ln(2)
        elif re.match(r"^(- |\d+\. )", line):
            pdf.set_font("body", size=11)
            marker = "•" if line.startswith("- ") else re.match(r"^\d+\.", line).group()
            body = line[2:] if line.startswith("- ") else line.split(". ", 1)[1]
            pdf.set_x(24)
            pdf.multi_cell(0, 6, f"{marker} {strip_inline(body)}", new_x="LMARGIN", new_y="NEXT")
        else:
            # Párrafo: **negrita** inline mediante markdown de fpdf2
            pdf.set_font("body", size=11)
            pdf.multi_cell(0, 6, line.replace("`", ""), markdown=True, new_x="LMARGIN", new_y="NEXT")
        i += 1
    return pdf


def main():
    regular, bold = find_fonts()
    OUT.mkdir(exist_ok=True)
    for md_path in sorted(SRC.glob("*.md")):
        pdf = render(md_path.read_text(encoding="utf-8"), regular, bold)
        out = OUT / f"{md_path.stem}.pdf"
        pdf.output(str(out))
        print(f"{md_path.name} -> {out.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
