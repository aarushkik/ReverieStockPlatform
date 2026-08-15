from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT = "output/pdf/MarketLens_Feedback_Loop_Submission.pdf"

NAVY = colors.HexColor("#071A2B")
INK = colors.HexColor("#173042")
MINT = colors.HexColor("#22C99A")
CYAN = colors.HexColor("#4EB4D8")
PALE = colors.HexColor("#F2F7F8")
PALE_MINT = colors.HexColor("#E9F8F3")
MID = colors.HexColor("#607480")
LINE = colors.HexColor("#CFDCE1")
WHITE = colors.white
AMBER = colors.HexColor("#E89C2D")
RED = colors.HexColor("#C94D48")


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverKicker", fontName="Helvetica-Bold", fontSize=9, leading=11,
    textColor=MINT, spaceAfter=10, uppercase=True, tracking=1.1,
))
styles.add(ParagraphStyle(
    name="CoverTitle", fontName="Helvetica-Bold", fontSize=31, leading=34,
    textColor=WHITE, spaceAfter=12,
))
styles.add(ParagraphStyle(
    name="CoverSub", fontName="Helvetica", fontSize=12, leading=17,
    textColor=colors.HexColor("#D3E1E7"), spaceAfter=20,
))
styles.add(ParagraphStyle(
    name="CoverBody", fontName="Helvetica", fontSize=9.4, leading=13.2,
    textColor=colors.HexColor("#E4EEF2"), spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="CoverFoot", fontName="Helvetica", fontSize=7.8, leading=10.3,
    textColor=colors.HexColor("#94AAB5"),
))
styles.add(ParagraphStyle(
    name="Section", fontName="Helvetica-Bold", fontSize=18, leading=22,
    textColor=NAVY, spaceBefore=4, spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="Subsection", fontName="Helvetica-Bold", fontSize=12.5, leading=15,
    textColor=INK, spaceBefore=9, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="BodyClean", fontName="Helvetica", fontSize=9.4, leading=13.2,
    textColor=INK, spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="Small", fontName="Helvetica", fontSize=7.8, leading=10.3,
    textColor=MID,
))
styles.add(ParagraphStyle(
    name="Tiny", fontName="Helvetica", fontSize=6.8, leading=8.5,
    textColor=MID,
))
styles.add(ParagraphStyle(
    name="Label", fontName="Helvetica-Bold", fontSize=7.5, leading=9.4,
    textColor=NAVY,
))
styles.add(ParagraphStyle(
    name="Answer", fontName="Helvetica", fontSize=8.25, leading=11.2,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="CardTitle", fontName="Helvetica-Bold", fontSize=9.4, leading=11.5,
    textColor=NAVY, spaceAfter=3,
))
styles.add(ParagraphStyle(
    name="CardBody", fontName="Helvetica", fontSize=8.3, leading=11.2,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="Metric", fontName="Helvetica-Bold", fontSize=18, leading=20,
    textColor=MINT, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="MetricLabel", fontName="Helvetica", fontSize=7.4, leading=9,
    textColor=colors.HexColor("#D3E1E7"), alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="TableHead", fontName="Helvetica-Bold", fontSize=7.2, leading=8.5,
    textColor=WHITE,
))
styles.add(ParagraphStyle(
    name="TableBody", fontName="Helvetica", fontSize=7.35, leading=9.5,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="Quote", fontName="Helvetica-Oblique", fontSize=10, leading=14,
    textColor=NAVY, leftIndent=10, rightIndent=10, alignment=TA_LEFT,
))


REVIEWERS = [
    {
        "name": "Marcus Vance",
        "tag": "Professional trader",
        "audience": "Active retail investor or trader",
        "experience": "Professional",
        "task": (
            "I ran an Nvidia pre-earnings setup through the multi-stage analysis and "
            "compared it with a basic one-prompt result. I also checked the entry range, "
            "position sizing, risk-to-reward, and stop-loss guidance."
        ),
        "worked": (
            "The full pipeline gave me something I could actually inspect: a defined entry "
            "range, a 1:2.35 risk-to-reward ratio, and options sensitivity details. It felt "
            "closer to a trading plan than generic market commentary."
        ),
        "grievance": (
            "The default 3.5% stop looked precise, but it treated every stock as if it moved "
            "the same way. On a high-beta name, that can stop out a reasonable idea during "
            "normal intraday movement."
        ),
        "evidence": (
            "In the Nvidia scenario, the stop could be reached without the original thesis "
            "being invalidated. I would have to ignore the platform's risk number and rebuild "
            "the stop manually before trusting the setup."
        ),
        "improvement": (
            "Use ATR or another volatility measure to set a suggested range, then show the "
            "assumption behind it. Let the user adjust the multiplier instead of presenting "
            "one fixed percentage as the correct answer."
        ),
        "impact": "Major friction - I could complete the task, but I would not use the default risk control.",
        "feature": "Research / technical analysis",
        "rating": "Not provided; the source notes focused on the written evaluation.",
        "follow": "Not recorded in the original notes - confirm with reviewer.",
        "quote": "A fixed stop percentage makes the risk control look precise without actually being precise.",
    },
    {
        "name": "Elena Rostova",
        "tag": "Systematic portfolio manager",
        "audience": "Finance, data, or software professional",
        "experience": "Professional",
        "task": (
            "I used the research tab on several stocks, turned on candlestick and technical "
            "overlays, and checked whether the 0-100 composite score helped with an initial screen."
        ),
        "worked": (
            "The composite score was a useful starting point because it brought trend, relative "
            "strength, and volatility into one place. I could scan first and investigate the "
            "components second, which could save about fifteen minutes per first pass."
        ),
        "grievance": (
            "The chart became crowded when several overlays were active. The original AI sidebar "
            "also used text that was too light against its background, especially on a laptop in "
            "a bright room."
        ),
        "evidence": (
            "On a 14-inch display, labels and lines competed for the same space, so I had to turn "
            "features off to read the chart. The low-contrast sidebar slowed down scanning and made "
            "the analysis feel more tiring than it needed to be."
        ),
        "improvement": (
            "Add clean chart presets for common workflows and limit overlays by default. Increase "
            "sidebar contrast, keep the most important values visually dominant, and let secondary "
            "details recede."
        ),
        "impact": "Major friction - the analysis was useful, but the presentation made it harder to use.",
        "feature": "Visual design / readability / accessibility",
        "rating": "Not provided; the source notes focused on the written evaluation.",
        "follow": "Not recorded in the original notes - confirm with reviewer.",
        "quote": "The information is useful, but if I have to fight the interface to see it, I will not use the extra information.",
    },
    {
        "name": "Devansh Patel",
        "tag": "Active swing trader",
        "audience": "Active retail investor or trader",
        "experience": "Advanced",
        "task": (
            "I tested the mobile drawer, quick ticker shortcuts, AI Copilot, and price alerts. My "
            "goal was to see how quickly I could go from finding a stock to setting up something "
            "worth monitoring."
        ),
        "worked": (
            "The chat was easy to scan because my messages and the assistant's responses were "
            "visually distinct. The ticker shortcuts also helped me jump back to names I already "
            "follow without repeating a search."
        ),
        "grievance": (
            "Some early screens showed third-party provider names and generic robot icons where I "
            "expected MarketLens branding. That made the product feel like a wrapper instead of a "
            "system with its own point of view."
        ),
        "evidence": (
            "I noticed the outside branding before I understood the platform's own analysis flow. "
            "That immediately raised questions about which parts were original and where my data "
            "was going."
        ),
        "improvement": (
            "Use consistent MarketLens branding and explain outside data providers in a small, "
            "transparent source note. Users should understand what the platform built and what data "
            "it depends on without seeing a confusing mix of identities."
        ),
        "impact": "Minor friction - I could complete the task, but it reduced trust in the product.",
        "feature": "Security / privacy / trust",
        "rating": "Not provided; the source notes focused on the written evaluation.",
        "follow": "Not recorded in the original notes - confirm with reviewer.",
        "quote": "If the first thing I notice is another company's name, I start questioning what your product actually does.",
    },
    {
        "name": "Priya Shah",
        "tag": "Beginner investor / CS student",
        "audience": "Student learning about investing",
        "experience": "Beginner",
        "task": (
            "I searched for a company I already knew, opened its research page, read the Copilot "
            "explanation, and tried to decide which information mattered before making a paper trade."
        ),
        "worked": (
            "It was helpful to ask basic questions without leaving the app to look up every finance "
            "term. Keeping the chart and company research together also made it easier to connect an "
            "explanation with what I was seeing."
        ),
        "grievance": (
            "The first screen gave me too many numbers without a clear starting point. A phrase like "
            "'relative strength is improving' still assumes I know why that matters and what I should "
            "check next."
        ),
        "evidence": (
            "I could find information, but I was not confident enough to turn it into a decision. I "
            "kept moving between sections and rereading labels because there was no obvious beginner path."
        ),
        "improvement": (
            "Add a guided first-use flow that explains one metric at a time: what it means, why it "
            "matters, and what evidence would support or weaken the conclusion. A short example would "
            "help more than another definition."
        ),
        "impact": "Major friction - I reached the information but could not confidently complete the decision task.",
        "feature": "Getting started / sign-in",
        "rating": "Not provided; the source notes focused on the written evaluation.",
        "follow": "Not recorded in the original notes - confirm with reviewer.",
        "quote": "I need the product to teach me how to read the information instead of assuming I already know.",
    },
    {
        "name": "Jordan Lee",
        "tag": "Paper-trading user / engineering student",
        "audience": "Student learning about investing",
        "experience": "Intermediate",
        "task": (
            "I started with a technical idea, checked it on the chart, set an alert, and tried to turn "
            "the idea into a paper trade. I wanted a clear path from analysis to a testable strategy."
        ),
        "worked": (
            "Combining quantitative signals with a plain-language explanation made the setup easier "
            "to understand. Alerts were useful because I could keep monitoring the idea without "
            "leaving the site open."
        ),
        "grievance": (
            "The workflow stopped just before validation. I could find a pattern and read an analysis, "
            "but I could not define the conditions, test them historically, or keep a clear record of "
            "why I entered the paper trade."
        ),
        "evidence": (
            "I ended up moving the setup into separate notes. That broke the connection between the "
            "chart, the alert, and the eventual trade, and it made it difficult to review whether my "
            "reasoning was consistent."
        ),
        "improvement": (
            "Add a lightweight strategy builder with entry, exit, and invalidation conditions. Let me "
            "run a simple historical check and attach the original reasoning to the paper-trade log."
        ),
        "impact": "Major friction - I could discover an idea but could not validate the full workflow.",
        "feature": "Paper trading / order entry",
        "rating": "Not provided; the source notes focused on the written evaluation.",
        "follow": "Not recorded in the original notes - confirm with reviewer.",
        "quote": "You help me find a trade idea, but not yet a good way to prove to myself that it works.",
    },
]


QUESTIONS = [
    ("Reviewer name", "name"),
    ("Audience", "audience"),
    ("Experience", "experience"),
    ("Task attempted", "task"),
    ("What worked", "worked"),
    ("Main grievance", "grievance"),
    ("Evidence / effect", "evidence"),
    ("Best improvement", "improvement"),
    ("Impact", "impact"),
    ("Product area", "feature"),
    ("Optional rating", "rating"),
    ("Follow-up", "follow"),
]


class MarketLensDocTemplate(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(
            filename,
            pagesize=letter,
            leftMargin=0.62 * inch,
            rightMargin=0.62 * inch,
            topMargin=0.62 * inch,
            bottomMargin=0.58 * inch,
            title="MarketLens Feedback Loop Submission",
            author="MarketLens Project Team",
            subject="Detailed reviewer responses, action plan, and cybersecurity design",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="main",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="standard", frames=[frame], onPage=draw_page))


def draw_page(canvas, doc):
    width, height = letter
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(MINT)
        canvas.rect(0, height - 0.18 * inch, width, 0.18 * inch, fill=1, stroke=0)
        return

    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 0.34 * inch, width, 0.34 * inch, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(WHITE)
    canvas.drawString(0.62 * inch, height - 0.225 * inch, "MARKETLENS  /  FEEDBACK LOOP")
    canvas.setStrokeColor(LINE)
    canvas.line(0.62 * inch, 0.41 * inch, width - 0.62 * inch, 0.41 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MID)
    canvas.drawString(0.62 * inch, 0.22 * inch, "Product feedback, response plan, and security review")
    canvas.drawRightString(width - 0.62 * inch, 0.22 * inch, str(doc.page))
    canvas.restoreState()


def P(text, style="BodyClean"):
    return Paragraph(text, styles[style])


def metric_card(number, label):
    return Table(
        [[P(number, "Metric")], [P(label, "MetricLabel")]],
        colWidths=[1.45 * inch],
        rowHeights=[0.34 * inch, 0.3 * inch],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#102B3D")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#26465A")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]),
    )


def callout(text, fill=PALE_MINT, border=MINT):
    table = Table([[P(text, "BodyClean")]], colWidths=[7.05 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def section_title(number, title, subtitle=None):
    parts = [
        Table(
            [[P(number, "CardTitle"), P(title, "Section")]],
            colWidths=[0.38 * inch, 6.67 * inch],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), MINT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
                ("LEFTPADDING", (1, 0), (1, 0), 10),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (1, 0), (1, 0), 0),
                ("BOTTOMPADDING", (1, 0), (1, 0), 0),
            ]),
        )
    ]
    if subtitle:
        parts.extend([Spacer(1, 2), P(subtitle, "Small")])
    parts.append(Spacer(1, 8))
    return parts


def reviewer_page(reviewer, index):
    story = []
    story.extend(section_title(
        f"{index:02}",
        reviewer["name"],
        reviewer["tag"] + "  |  Form-aligned response",
    ))

    rows = []
    for row_index, (label, key) in enumerate(QUESTIONS):
        fill = WHITE if row_index % 2 == 0 else PALE
        rows.append([
            P(label.upper(), "Label"),
            P(reviewer[key], "Answer"),
        ])
    table = Table(rows, colWidths=[1.25 * inch, 5.8 * inch], repeatRows=0)
    table_style = [
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
    ]
    for row_index in range(len(rows)):
        table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), WHITE if row_index % 2 == 0 else PALE))
        table_style.append(("BACKGROUND", (0, row_index), (0, row_index), PALE_MINT))
    table.setStyle(TableStyle(table_style))
    story.append(table)
    story.append(Spacer(1, 10))
    quote_table = Table([[P('“' + reviewer["quote"] + '”', "Quote")]], colWidths=[7.05 * inch])
    quote_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF4F8")),
        ("LINEBEFORE", (0, 0), (0, 0), 3, CYAN),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(quote_table)
    return story


def build_story():
    story = []

    # Cover
    story.append(Spacer(1, 0.72 * inch))
    story.append(P("PRODUCT FEEDBACK LOOP / BOUNTY SUBMISSION", "CoverKicker"))
    story.append(P("MarketLens", "CoverTitle"))
    story.append(P(
        "Detailed reviewer responses, prioritized product changes, and a practical cybersecurity review.",
        "CoverSub",
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#355064")))
    story.append(Spacer(1, 0.25 * inch))

    metrics = Table(
        [[
            metric_card("5", "REVIEWER PROFILES"),
            metric_card("12", "FORM FIELDS EACH"),
            metric_card("5", "PRIORITY THEMES"),
            metric_card("2", "SECURITY MODELS"),
        ]],
        colWidths=[1.72 * inch] * 4,
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    story.append(metrics)
    story.append(Spacer(1, 0.32 * inch))

    intro = Table([[P(
        "<b>What this document does</b><br/>Each reviewer entry now follows the exact questions in the current MarketLens feedback form. The answers are concise enough to scan, but retain the task, evidence, impact, and requested change that make feedback useful.",
        "CoverBody",
    )]], colWidths=[7.0 * inch])
    intro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#102B3D")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#355064")),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
    ]))
    story.append(intro)
    story.append(Spacer(1, 0.35 * inch))
    story.append(P("Scope", "CoverKicker"))
    story.append(P(
        "Market research  /  AI-assisted analysis  /  paper trading  /  usability  /  trust  /  suspicious-login detection",
        "CoverSub",
    ))
    story.append(Spacer(1, 0.23 * inch))
    story.append(P(
        "Prepared from the supplied feedback document and the current MarketLens form structure. August 2026.",
        "CoverFoot",
    ))
    story.append(PageBreak())

    # Executive overview
    story.extend(section_title("01", "Review design", "Why these responses are useful"))
    story.append(P(
        "The reviewers represent two experienced market users, one active retail trader, and two students at different learning levels. Each person completed a task instead of giving a rating alone. The result is specific: what they tried, what helped, what failed, how it affected them, and what they would change.",
    ))
    story.append(callout(
        "<b>Verification note.</b> This is a polished rewrite of the supplied tester notes. The source document says the reviewer descriptions should be aligned with the people who actually tested the product. Optional ratings and follow-up consent were not present in those notes, so this report marks them as unrecorded rather than inventing answers.",
        fill=colors.HexColor("#FFF5E4"), border=AMBER,
    ))
    story.append(Spacer(1, 12))
    story.append(P("Audience coverage", "Subsection"))
    audience_rows = [
        [P("REVIEWER", "TableHead"), P("PERSPECTIVE", "TableHead"), P("PRIMARY TEST AREA", "TableHead")],
        [P("Marcus Vance", "TableBody"), P("Professional trader", "TableBody"), P("Risk controls and position sizing", "TableBody")],
        [P("Elena Rostova", "TableBody"), P("Portfolio manager", "TableBody"), P("Research density and readability", "TableBody")],
        [P("Devansh Patel", "TableBody"), P("Active swing trader", "TableBody"), P("Mobile flow, alerts, and trust", "TableBody")],
        [P("Priya Shah", "TableBody"), P("Beginner investor", "TableBody"), P("Onboarding and explanations", "TableBody")],
        [P("Jordan Lee", "TableBody"), P("Paper-trading user", "TableBody"), P("Strategy validation and journaling", "TableBody")],
    ]
    audience_table = Table(audience_rows, colWidths=[1.45 * inch, 1.72 * inch, 3.88 * inch], repeatRows=1)
    audience_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(audience_table)
    story.append(Spacer(1, 12))
    story.append(P("What the review changed", "Subsection"))
    bullets = [
        "Precision needs context: risk controls should respond to volatility.",
        "More information is not automatically more usable; chart density and contrast matter.",
        "Brand consistency and clear data provenance affect whether users trust the product.",
        "Beginners need a path through the analysis, not only definitions.",
        "Research becomes more valuable when it connects to testing, alerts, and a decision log.",
    ]
    for item in bullets:
        story.append(P("<font color='#22C99A'><b>•</b></font>  " + item, "BodyClean"))

    # Reviewer pages
    for index, reviewer in enumerate(REVIEWERS, 2):
        story.append(PageBreak())
        story.extend(reviewer_page(reviewer, index))

    # Synthesis
    story.append(PageBreak())
    story.extend(section_title("07", "What we heard", "Cross-review synthesis and ranked grievances"))
    synthesis_rows = [
        [P("PRIORITY", "TableHead"), P("GRIEVANCE", "TableHead"), P("EVIDENCE", "TableHead"), P("RESPONSE", "TableHead")],
        [P("P0", "TableBody"), P("Risk controls ignore volatility", "TableBody"), P("Fixed 3.5% stop can trigger during normal high-beta movement.", "TableBody"), P("Use ATR-based guidance with a visible, adjustable assumption.", "TableBody")],
        [P("P0", "TableBody"), P("Dense charts and weak contrast", "TableBody"), P("Overlays collide on a 14-inch display; sidebar text is tiring to scan.", "TableBody"), P("Ship clean presets, stronger hierarchy, and accessibility checks.", "TableBody")],
        [P("P0", "TableBody"), P("Trust is weakened by mixed branding", "TableBody"), P("Third-party names appear before MarketLens value is clear.", "TableBody"), P("Use consistent branding and transparent, quiet source attribution.", "TableBody")],
        [P("P1", "TableBody"), P("Beginners lack a first-use path", "TableBody"), P("A new user found the data but could not turn it into a decision.", "TableBody"), P("Guide users through meaning, relevance, and the next check.", "TableBody")],
        [P("P1", "TableBody"), P("Ideas cannot be validated end-to-end", "TableBody"), P("Strategy conditions and trade reasoning moved into outside notes.", "TableBody"), P("Add lightweight backtesting and a linked paper-trade journal.", "TableBody")],
    ]
    synthesis = Table(synthesis_rows, colWidths=[0.52 * inch, 1.55 * inch, 2.32 * inch, 2.66 * inch], repeatRows=1)
    synthesis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 1), (0, 3), RED),
        ("TEXTCOLOR", (0, 4), (0, 5), AMBER),
    ]))
    story.append(synthesis)
    story.append(Spacer(1, 13))
    story.append(P("Decision principles", "Subsection"))
    story.append(callout(
        "<b>Clarity before breadth.</b> Make the existing research path understandable before adding more indicators.<br/><b>Evidence before confidence.</b> Show the assumptions behind calculated risk and AI conclusions.<br/><b>Workflow before novelty.</b> Connect discovery to testing, alerts, paper trading, and review.<br/><b>Trust by design.</b> Treat readability, branding, security, and data provenance as product behavior - not polish added at the end.",
    ))
    story.append(Spacer(1, 13))
    story.append(P("One request we are not implementing as proposed", "Subsection"))
    story.append(P(
        "A reviewer suggested bypassing the adversarial bear-audit stage to reduce response time. We are declining that change for now. The audit exists to challenge overly bullish conclusions; removing it would trade a visible speed gain for weaker reasoning safeguards. The better next step is to profile and optimize the audit while preserving its role.",
    ))

    # Action plan
    story.append(PageBreak())
    story.extend(section_title("08", "Response plan", "Owners, deliverables, and proof that the issue is fixed"))
    plan_rows = [
        [P("WHEN", "TableHead"), P("CHANGE", "TableHead"), P("DELIVERABLE", "TableHead"), P("VALIDATION", "TableHead")],
        [P("Now / P0", "TableBody"), P("Volatility-aware stops", "TableBody"), P("ATR-based range, adjustable multiplier, and visible rationale.", "TableBody"), P("Replay the Nvidia case plus low- and high-volatility names; confirm the stop reflects normal movement.", "TableBody")],
        [P("Now / P0", "TableBody"), P("Chart and AI readability", "TableBody"), P("Clean, Swing, and Advanced presets; stronger text contrast.", "TableBody"), P("Test on a 14-inch laptop, keyboard-only navigation, and automated contrast checks.", "TableBody")],
        [P("Now / P0", "TableBody"), P("Trust and provenance", "TableBody"), P("Unified MarketLens identity with clear data-source and AI limitation notes.", "TableBody"), P("Ask a new user to explain what MarketLens built, what comes from providers, and where data goes.", "TableBody")],
        [P("Next / P1", "TableBody"), P("Beginner research path", "TableBody"), P("Guided sequence: meaning, why it matters, evidence, next step.", "TableBody"), P("Three beginners complete a research task without outside definitions; record hesitation points.", "TableBody")],
        [P("Next / P1", "TableBody"), P("Strategy test + journal", "TableBody"), P("Simple rule builder, historical check, and reasoning attached to paper trades.", "TableBody"), P("A user moves from chart idea to test, alert, paper order, and later review without external notes.", "TableBody")],
        [P("Then / P2", "TableBody"), P("Security hardening", "TableBody"), P("Production MFA, rate limits, monitoring, model drift checks, and retention controls.", "TableBody"), P("Threat-model review, abuse tests, audit evidence, and measured false-positive/challenge rates.", "TableBody")],
    ]
    plan = Table(plan_rows, colWidths=[0.72 * inch, 1.32 * inch, 2.14 * inch, 2.87 * inch], repeatRows=1)
    plan.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(plan)
    story.append(Spacer(1, 14))
    story.append(P("Success measures", "Subsection"))
    measures = [
        [P("Task completion", "CardTitle"), P("Target users finish the same reviewer tasks with less assistance and fewer abandoned steps.", "CardBody")],
        [P("Trust", "CardTitle"), P("Users can explain data sources, AI limitations, and security decisions in plain language.", "CardBody")],
        [P("Quality", "CardTitle"), P("Calculated risk guidance exposes assumptions; strategy results can be reproduced and reviewed.", "CardBody")],
        [P("Safety", "CardTitle"), P("Challenges catch suspicious behavior without routinely locking out legitimate travelers or new devices.", "CardBody")],
    ]
    measure_table = Table(measures, colWidths=[1.35 * inch, 5.7 * inch])
    measure_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PALE_MINT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(measure_table)

    # Cybersecurity
    story.append(PageBreak())
    story.extend(section_title("09", "Cybersecurity by design", "How MarketLens evaluates suspicious logins"))
    story.append(P(
        "MarketLens protects the research and paper-trading experience with a layered sign-in gate. The design does not treat one model score as absolute truth. Deterministic evidence, credential checks, calibrated probabilities, and a graded response all contribute to the final decision.",
    ))

    flow_rows = [[
        P("1  BOT CHECK", "CardTitle"),
        P("2  CREDENTIALS", "CardTitle"),
        P("3  LOGIN RISK", "CardTitle"),
        P("4  DECISION", "CardTitle"),
    ], [
        P("Behavior and browser telemetry are checked before expensive password work.", "CardBody"),
        P("Scrypt verifies a salted password; unknown users still pay the same decoy-hash cost.", "CardBody"),
        P("Context such as travel speed, device familiarity, network, location, and time is scored.", "CardBody"),
        P("The user is allowed, challenged, or denied with readable reasons.", "CardBody"),
    ]]
    flow = Table(flow_rows, colWidths=[1.76 * inch] * 4)
    flow.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE_MINT),
        ("BACKGROUND", (0, 1), (-1, 1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(flow)
    story.append(Spacer(1, 12))

    security_rows = [
        [P("LAYER", "TableHead"), P("IMPLEMENTED DESIGN", "TableHead"), P("WHY IT MATTERS", "TableHead")],
        [P("Bot detection", "TableBody"), P("19 behavioral and browser features: pointer path, turn entropy, typing rhythm, fill time, automation flags, environment plausibility, and a honeypot.", "TableBody"), P("Stops obvious automation early and avoids wasting password-hashing work.", "TableBody")],
        [P("Login risk", "TableBody"), P("18 contextual features: implied travel velocity, distance, elapsed time, country/city/network/device familiarity, time-of-day deviation, reputation, recent failures, account age, and timezone agreement.", "TableBody"), P("Flags patterns consistent with stolen credentials while allowing normal context to reduce risk.", "TableBody")],
        [P("Credential storage", "TableBody"), P("Scrypt password hashes with a random per-user salt; constant-work decoy verification for unknown usernames.", "TableBody"), P("Raises offline cracking cost and reduces username-enumeration timing signals.", "TableBody")],
        [P("Response", "TableBody"), P("Allow, challenge, or deny. Rules can outrank a probability when evidence is unambiguous, and every decision includes plain-language reasons.", "TableBody"), P("Avoids treating uncertainty as a binary lockout and makes decisions auditable.", "TableBody")],
        [P("Privacy", "TableBody"), P("The event log stores resolved city and coarse coordinates rather than the raw IP address.", "TableBody"), P("Keeps enough context for risk analysis while reducing retained sensitive data.", "TableBody")],
    ]
    security_table = Table(security_rows, colWidths=[1.05 * inch, 3.58 * inch, 2.42 * inch], repeatRows=1)
    security_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(security_table)
    story.append(Spacer(1, 12))
    story.append(callout(
        "<b>Important limitation.</b> Both security models were trained on simulated data because the project does not yet have a labeled set of real sign-ins. The reported model metrics measure how well each model recovers its generator, not field accuracy against live attackers. Production use requires consent, monitoring, representative data, drift checks, and retraining.",
        fill=colors.HexColor("#FFF0EF"), border=RED,
    ))

    # Security evaluation and close
    story.append(PageBreak())
    story.extend(section_title("10", "Security evaluation and next steps", "Measured results, threat coverage, and responsible deployment"))
    metric_rows = [
        [P("MODEL", "TableHead"), P("ROC-AUC", "TableHead"), P("PR-AUC", "TableHead"), P("BRIER", "TableHead"), P("CALIBRATION ERROR", "TableHead"), P("PRECISION / RECALL", "TableHead")],
        [P("Login risk", "TableBody"), P("0.966", "TableBody"), P("0.941", "TableBody"), P("0.046", "TableBody"), P("0.018", "TableBody"), P("0.926 / 0.941", "TableBody")],
        [P("Bot detection", "TableBody"), P("0.978", "TableBody"), P("0.966", "TableBody"), P("0.022", "TableBody"), P("0.005", "TableBody"), P("0.976 / 0.969", "TableBody")],
    ]
    metric_table = Table(metric_rows, colWidths=[1.25 * inch, 0.82 * inch, 0.82 * inch, 0.75 * inch, 1.22 * inch, 1.42 * inch], repeatRows=1)
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(metric_table)
    story.append(Spacer(1, 5))
    story.append(P("These are held-out results on simulated examples, not a production security guarantee.", "Tiny"))
    story.append(Spacer(1, 10))

    threat_rows = [
        [P("THREAT", "TableHead"), P("CURRENT CONTROL", "TableHead"), P("NEXT HARDENING STEP", "TableHead")],
        [P("Bots and scripted abuse", "TableBody"), P("Behavioral model, automation flags, honeypot, and decisive rules.", "TableBody"), P("Add server-side rate limits, shared abuse signals, and replay-resistant telemetry.", "TableBody")],
        [P("Credential stuffing", "TableBody"), P("Recent-failure features, bot gate, memory-hard password verification, graded denial.", "TableBody"), P("Add breached-password checks, IP/account throttles, and security notifications.", "TableBody")],
        [P("Username enumeration", "TableBody"), P("Unknown accounts execute a full scrypt operation against a decoy hash.", "TableBody"), P("Keep errors uniform and measure end-to-end timing under load.", "TableBody")],
        [P("Stolen credentials", "TableBody"), P("Device, network, travel, time, and location context can trigger a challenge.", "TableBody"), P("Replace the demo code with production MFA or passkeys and secure recovery.", "TableBody")],
        [P("Model drift / bias", "TableBody"), P("Calibrated probabilities, explicit rules, and readable reasons.", "TableBody"), P("Track challenge and false-positive rates by scenario; retrain only on consented, reviewed data.", "TableBody")],
        [P("Sensitive-data exposure", "TableBody"), P("Coarse location logging without raw IP retention.", "TableBody"), P("Document retention/deletion windows, encrypt backups, restrict access, and audit exports.", "TableBody")],
    ]
    threats = Table(threat_rows, colWidths=[1.35 * inch, 2.62 * inch, 3.08 * inch], repeatRows=1)
    threats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(threats)
    story.append(Spacer(1, 13))
    story.append(callout(
        "<b>Bottom line.</b> MarketLens is strongest when its financial analysis and its security design follow the same rule: a confident-looking number is not enough. The product should expose assumptions, preserve safeguards, explain decisions, and improve based on evidence from real users.",
    ))
    return story


def main():
    doc = MarketLensDocTemplate(OUTPUT)
    doc.build(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    main()
