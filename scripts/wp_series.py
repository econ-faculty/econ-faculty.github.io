"""Working papers are kept only when they belong to an official / institutional working-paper series
(NBER, CEPR, IZA, central banks, IMF, World Bank, research institutes, university department series ...).
Ordinary working papers (no series, SSRN/arXiv preprints, 'work in progress', 'submitted to <journal>' ...) are dropped."""
import re

# named institutions whose working-paper / discussion-paper / staff-report series count
INST = re.compile(r"""\b(
    NBER|National\ Bureau\ of\ Economic\ Research|CEPR|Centre\ for\ Economic\ Policy\ Research|IZA|CESifo|
    IMF|International\ Monetary\ Fund|World\ Bank|Policy\ Research\ Working|OECD|BIS|Bank\ for\ International\ Settlements|
    ECB|European\ Central\ Bank|Federal\ Reserve|FRB|Fed\b|Board\ of\ Governors|Finance\ and\ Economics\ Discussion|FEDS|
    Bank\ of\ [A-Z][a-z]+|Bundesbank|Banque\ de\ France|Banca\ d'Italia|Banco\ de\ Espa|Banco\ Central|Sveriges\ Riksbank|Norges\ Bank|
    Danmarks\ Nationalbank|De\ Nederlandsche\ Bank|Swiss\ National\ Bank|Reserve\ Bank|Central\ Bank|
    IFS|Institute\ for\ Fiscal\ Studies|IFN|CEMFI|CEP\b|Centre\ for\ Economic\ Performance|STICERD|
    Becker\ Friedman|BFI|Cowles|Hoover|Brookings|Hutchins|PIIE|Peterson\ Institute|Upjohn|RAND|Urban\ Institute|
    Census|Center\ for\ Economic\ Studies|CES\ Working|BLS|Bureau\ of\ Labor|Bureau\ of\ Economic|BEA\b|Treasury|CBO|
    ZEW|DIW|ifo|IWH|RWI|Kiel\ Institute|IfW|WZB|Max\ Planck|ECONtribute|CRC\ TR|SAFE|CFS|Tinbergen|CREST|TSE|PSE|
    Paris\ School\ of\ Economics|Barcelona\ (GSE|School\ of\ Economics)|BSE|UPF|CEMMAP|CReAM|IGC|J-PAL|
    3ie|UNU-WIDER|WIDER|IDB|Inter-American|ADB|Asian\ Development|AfDB|EBRD|Harvard\ Business\ School|HBS|
    Kennedy\ School|HKS|Marketing\ Science\ Institute|MSI|RIETI|ESRI|CIRJE|KDI|ERIA|Becker|NHH|VATT|ETLA|IFAU|
    Statistics\ (Canada|Norway|Netherlands|Sweden|Denmark)|CPB|IGIER|EIEF|CSEF|CEIS|Carlo\ Alberto|Collegio|FEEM|
    Rockwool|CEBI|ISER|
    CIRANO|CIREQ|CLEF|Canadian\ Labour|Melbourne\ Institute|CAMA|Academia\ Sinica|
    Federal\ Reserve\ Bank|Staff\ Report|PIER|HCEO|NSF|GLO|Global\ Labor\ Organization|IAAE|CAGE|
    Becker-Friedman|Stigler\ Center|Jacobs\ Levy|Fama-Miller|ECGI|European\ Corporate\ Governance|
    Swiss\ Finance\ Institute|SFI|HKIMR|ABFER|AEA\ Papers
)\b""", re.X)
# a numbered / named series of some institution, e.g. 'Department of Economics Working Paper No. 2023-04', 'Discussion Paper Series 1123'
SERIES = re.compile(r"(working|discussion|research|staff|policy|occasional)\s+papers?\s*(series|no\.?|nr\.?|#|\d)|"
                    r"(working|discussion)\s+paper\s+series|staff\s+report|\bdp\s*\d|\bwp\s*\d", re.I)
JUNK = re.compile(r"\b(ssrn|arxiv|preprint|medrxiv|biorxiv|socarxiv|osf|psyarxiv|researchgate|mimeo|manuscript|draft|"
                  r"in progress|in preparation|under review|under preparation|submitted|job market|target|revis|reject|"
                  r"blog|opinion|bloomberg|op-ed|technical report)\b", re.I)


def wp_official(series):
    s = (series or "").strip()
    if not s or JUNK.search(s):
        return False
    return bool(INST.search(s) or SERIES.search(s))
