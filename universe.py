"""Listas de acciones para escanear."""
import io
import urllib.request

EJEMPLOS = ["AMRN", "DPRO", "MTS.MC"]

IBEX35 = [
    "ACS.MC", "ACX.MC", "AENA.MC", "AMS.MC", "ANA.MC", "ANE.MC", "BBVA.MC", "BKT.MC",
    "CABK.MC", "CLNX.MC", "COL.MC", "ELE.MC", "ENG.MC", "FDR.MC", "FER.MC", "GRF.MC",
    "IAG.MC", "IBE.MC", "IDR.MC", "ITX.MC", "LOG.MC", "MAP.MC", "MRL.MC", "MTS.MC",
    "NTGY.MC", "PUIG.MC", "RED.MC", "REP.MC", "ROVI.MC", "SAB.MC", "SAN.MC", "SCYR.MC",
    "SLR.MC", "TEF.MC", "UNI.MC",
]

CONTINUO = [
    "A3M.MC", "ADX.MC", "AED.MC", "ALM.MC", "AMP.MC", "APAM.MC", "ATRY.MC", "AZK.MC",
    "CAF.MC", "CIE.MC", "DIA.MC", "EBRO.MC", "ECR.MC", "EDR.MC", "ENC.MC", "ENO.MC",
    "FAE.MC", "GEST.MC", "GRE.MC", "HOME.MC", "LDA.MC", "MEL.MC", "MVC.MC", "NHH.MC",
    "NXT.MC", "OHLA.MC", "PHM.MC", "PRM.MC", "PSG.MC", "R4.MC", "SCO.MC", "SQRL.MC",
    "TLGO.MC", "TRE.MC", "TUB.MC", "VID.MC", "VIS.MC", "ZOT.MC",
]

NASDAQ100 = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN", "AMZN",
    "ANSS", "APP", "ARM", "ASML", "AVGO", "AXON", "AZN", "BIIB", "BKNG", "BKR", "CCEP",
    "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CSX",
    "CTAS", "CTSH", "DASH", "DDOG", "DXCM", "EA", "EXC", "FANG", "FAST", "FTNT", "GEHC",
    "GFS", "GILD", "GOOGL", "HON", "IDXX", "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC",
    "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDB", "MDLZ", "MELI", "META", "MNST", "MRVL",
    "MSFT", "MSTR", "MU", "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX",
    "PCAR", "PDD", "PEP", "PLTR", "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS",
    "TEAM", "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL", "ZS",
]


def nasdaq_completo():
    """Todas las acciones del NASDAQ (lista oficial de nasdaqtrader.com)."""
    url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    with urllib.request.urlopen(url, timeout=20) as r:
        txt = r.read().decode()
    out = []
    for line in io.StringIO(txt).readlines()[1:]:
        f = line.split("|")
        # f[3]=Test Issue, f[6]=ETF
        if len(f) > 6 and f[3] == "N" and f[6] == "N" and f[0].isalpha():
            out.append(f[0])
    return out


LISTAS = {
    "Ejemplos (AMRN, DPRO, MTS)": lambda: EJEMPLOS,
    "IBEX 35": lambda: IBEX35,
    "Mercado continuo (selección)": lambda: CONTINUO,
    "NASDAQ 100": lambda: NASDAQ100,
    "NASDAQ completo (lento)": nasdaq_completo,
}
