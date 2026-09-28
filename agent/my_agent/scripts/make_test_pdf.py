
"""生成测试课件 PDF（仅用于阶段 2 验证，非项目运行时依赖）。

依赖 reportlab（测试数据生成用，不进 requirements.txt）：
    pip install reportlab

生成一份「二次函数」章节的中文课件到 data/sample_courseware.pdf，
内容里埋了若干可检索的独立知识点，用于验证「检索到正确片段并回答」。
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# 注册中文字体：STSong-Light 是 PDF 内置的 CJK 字体，无需外部字体文件
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_courseware.pdf"

STYLE_TITLE = ParagraphStyle("title", fontName="STSong-Light", fontSize=18, leading=24)
STYLE_HEAD = ParagraphStyle("head", fontName="STSong-Light", fontSize=14, leading=20)
STYLE_BODY = ParagraphStyle("body", fontName="STSong-Light", fontSize=12, leading=20)

SECTIONS = [
    ("第二章 二次函数", "title"),
    ("2.1 二次函数的概念", "head"),
    (
        "一般地，形如 y = ax² + bx + c（其中 a、b、c 是常数，且 a ≠ 0）的函数，"
        "叫做二次函数。其中 x 是自变量，y 是因变量。a 叫做二次项系数，b 叫做一次项系数，"
        "c 叫做常数项。当 b = 0 时，二次函数退化为 y = ax² + c；当 c = 0 时，"
        "退化为 y = ax² + bx。",
        "body",
    ),
    ("2.2 图像与性质", "head"),
    (
        "二次函数的图像是一条抛物线。开口方向由二次项系数 a 决定：当 a > 0 时，"
        "抛物线开口向上，函数有最小值；当 a < 0 时，抛物线开口向下，函数有最大值。",
        "body",
    ),
    (
        "抛物线的对称轴是直线 x = -b / (2a)。顶点是抛物线的最高点或最低点，"
        "顶点坐标公式为（-b / (2a)，(4ac - b²) / (4a)）。",
        "body",
    ),
    ("2.3 判别式与求根公式", "head"),
    (
        "对于二次函数 y = ax² + bx + c，令 y = 0 得到一元二次方程 ax² + bx + c = 0。"
        "定义判别式 Δ = b² - 4ac。当 Δ > 0 时，方程有两个不相等的实数根；"
        "当 Δ = 0 时，方程有两个相等的实数根；当 Δ < 0 时，方程没有实数根。",
        "body",
    ),
    (
        "求根公式为 x = (-b ± √(b² - 4ac)) / (2a)，其中根号下的 b² - 4ac 就是判别式 Δ。",
        "body",
    ),
    ("2.4 配方法", "head"),
    (
        "配方法是把二次函数一般式 y = ax² + bx + c 化为顶点式 y = a(x - h)² + k 的方法。"
        "其中 h = -b / (2a)，k = (4ac - b²) / (4a)。配方后能直接读出对称轴 x = h 和顶点 (h, k)。",
        "body",
    ),
]


def build() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    story = []
    for text, kind in SECTIONS:
        style = {
            "title": STYLE_TITLE,
            "head": STYLE_HEAD,
            "body": STYLE_BODY,
        }[kind]
        story.append(Paragraph(text, style))
        story.append(Spacer(1, 0.4 * cm))

    doc.build(story)
    print(f"已生成测试课件：{OUT_PATH}")


if __name__ == "__main__":
    build()