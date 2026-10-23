"""Paper-level topic tags (1-2 per paper) using the site's journal-topic taxonomy (D.jtopics).

classify(title, journal_topic) -> list of topic indices
  1) keyword rules on the title (first two distinct hits, rule order = priority)
  2) fall back to the journal's own topic when the title gives nothing
     (general-interest journals: topic 0 'General Economics' stays only as a last resort)
"""
import re

RULES = [  # (topic name in jtopics, regex on lower-cased title)
    ("Environment & Energy", r"climat|carbon|emission|pollut|environment|energy|electric(ity|al)|renewable|solar|wind power|fossil|\boil\b|natural gas|coal|gasoline|fuel|greenhouse|air quality|wildfire|flood|hurricane|drought|deforest|biodivers|ecosystem|conservation|water (quality|pricing|scarcity)|\bheat\b|temperature|extreme weather|sustainab"),
    ("Agricultural", r"agricultur|\bcrop|\bfarm|food (price|security|policy|insecurity)|fertili[sz]er|livestock|irrigation|land tenure|rural"),
    ("Health", r"health|hospital|medic(al|aid|are)|physician|patient|disease|mortality|insurance market.*health|drug|pharma|opioid|covid|pandemic|obesity|mental health"),
    ("Education", r"school|educat|student|teacher|college|universit(y|ies) admission|tuition|test score|human capital"),
    ("Labor", r"labou?r(?!ator)|wage|employ|worker|job|unemploy|minimum wage|occupation|union|migra|immigra|gender gap|earnings|retire|pension"),
    ("Development", r"develop(ing|ment) (countr|econom)|poverty|microfinance|india|africa|china'?s|kenya|bangladesh|village|informal sector|foreign aid"),
    ("Public Economics", r"\btax|fiscal|public good|transfer program|welfare (program|reform)|social insurance|government spending|redistribut|public finance|subsid"),
    ("Industrial Organization", r"competition|antitrust|merger|market power|monopol|oligopol|pricing|entry|platform|regulat(ion|ed) (industr|firm)|auction|collusion|vertical"),
    ("International", r"trade|tariff|export|import|exchange rate|currency|global value chain|multinational|foreign direct|international|sovereign debt|capital flow"),
    ("Macro & Monetary", r"monetary|inflation|central bank|interest rate|business cycle|recession|macro|output gap|productivity growth|economic growth|fiscal multiplier|unemployment dynamics|dsge|phillips"),
    ("Urban & Regional", r"urban|city|cities|housing|neighborhood|regional|spatial|commut|zoning|gentrif|place-based"),
    ("Economic History", r"histor|nineteenth|19th century|18th century|colonial|medieval|great depression|industrial revolution|slavery"),
    ("Law & Economics", r"\blaw\b|legal|court|litigat|crime|criminal|police|incarcerat|judge|patent law|contract enforcement"),
    ("Behavioral & Experimental", r"behavio(u)?ral|experiment|nudge|present bias|loss aversion|overconfiden|belief|reference.dependent|social preference|altruis|fairness|lab "),
    ("Econometrics", r"estimat(or|ion)|inference|identification|instrumental variable|panel data|regression discontinuity|difference.in.difference|bootstrap|nonparametric|semiparametric|time series|forecast|bayesian|machine learning|causal effect"),
    ("Microeconomic Theory", r"equilibri|game|mechanism design|contract theory|information design|persuasion|matching market|bargaining|signal(l)?ing|repeated game|social choice|voting rule"),
    ("Finance", r"asset pric|stock|bond|portfolio|return predict|volatil|option pric|risk premium|hedge fund|mutual fund|investor|ipo|venture capital|private equity|bank|credit|loan|mortgage|liquidity|leverage|capital structure|corporate govern|dividend|cryptocurr|fintech|financial"),
    ("Accounting", r"accounting|earnings management|audit|disclosure|financial report|analyst forecast|accrual|restatement|tax avoidance|ifrs|gaap"),
    ("Marketing", r"consumer|brand|advertis|marketing|customer|retail|promotion|word.of.mouth|purchase|shopping|product review|loyalty"),
    ("Operations & IS", r"supply chain|inventory|operations|queue|scheduling|logistics|information system|online platform design|algorithm|optimi[sz]ation|revenue management|it investment|digital transformation"),
    ("Organizational Behavior", r"leader|team|employee|organizational behavior|negotiat|motivation|diversity|identity at work|burnout|workplace"),
    ("Management & Strategy", r"strateg|firm performance|competitive advantage|alliance|corporate diversification|organizational design|top management|ceo|board of directors"),
    ("Entrepreneurship & Innovation", r"innovat|entrepreneur|startup|start-up|patent|r&d|technolog(y|ical) change|invention"),
    ("Real Estate", r"real estate|reit|commercial property|house price"),
    ("Political Science", r"elect(ion|oral)|vot(er|ing)|politic|democra|parliament|congress|lobby|campaign"),
]


def compile_rules(jtopics):
    idx = {n: i for i, n in enumerate(jtopics)}
    return [(idx[n], re.compile(r"\b(?:" + rx + ")")) for n, rx in RULES if n in idx]  # every keyword starts at a word boundary


def classify(title, journal_topic, rules, general_idx=0):
    t = (title or "").lower()
    out = []
    for i, rx in rules:
        if i not in out and rx.search(t):
            out.append(i)
            if len(out) == 2:
                break
    if journal_topic is not None and journal_topic >= 0 and journal_topic != general_idx:
        if not out:
            out = [journal_topic]
        elif journal_topic not in out and len(out) == 1:
            out.append(journal_topic)   # field journal adds its own topic as the 2nd tag
    if not out and journal_topic == general_idx:
        out = [general_idx]
    return out[:2]
