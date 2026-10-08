"""
Etapa 1 — coleta de dados de tabuademares.com/br/paraiba/joao-pessoa.

Objetivo: gravar em data/raw/ os CSVs que as Etapas 2 e 3 vão consumir.

    mares_<ano>.csv      tábua de marés do ano (4 marés por dia)
    mares_previsao.csv   marés do mês corrente, para cruzar com a previsão
    ondas.csv            altura de onda hora a hora (~7 dias à frente)
    vento.csv            velocidade do vento hora a hora (~7 dias à frente)

As funções abaixo estão vazias de propósito. Abra o site no navegador, use o
DevTools para descobrir onde cada dado vive no HTML e implemente o parse.
As colunas de cada CSV são sua decisão — só precisam sustentar as etapas
seguintes (ver README).

Rodar com: uv run python src/scrape.py
"""

import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Os imports acima são o ponto de partida: você vai usar todos eles.
# Seu editor pode marcá-los como não usados até você preencher as funções.

URL_BASE = "https://tabuademares.com/br/paraiba/joao-pessoa"
URL_ONDAS = f"{URL_BASE}/previsao/ondas"
URL_VENTO = f"{URL_BASE}/previsao/vento"

# Servidores rejeitam clientes sem User-Agent. Identifique-se.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Segundos de pausa entre requests. Não tire isso.
PAUSA = 1.5

DIR_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def baixar_html(url: str, dados_post: dict | None = None) -> str:
    """Baixa uma página e devolve o HTML.

    Use POST (passando `dados_post`) quando a página só devolver o conteúdo
    que você quer em resposta a um formulário; GET no resto.

    TODO: fazer a requisição com `requests`, checar o status e devolver o texto.
    Dica: `resp.raise_for_status()` falha alto quando o servidor recusa.
    """
    if dados_post is None:
        resp = requests.get(url, headers=HEADERS, timeout=30)
    else:
        resp = requests.post(url, headers=HEADERS, data=dados_post, timeout=30)
    resp.raise_for_status()
    return resp.text


def parsear_mares(html: str, ano: int, mes: int) -> list[dict]:
    """Extrai da tábua mensal uma linha por evento de maré.

    Cada dia tem cerca de 4 eventos (duas altas, duas baixas). Além de
    horário e altura, a página traz informação de coeficiente de maré e de
    fase da lua — decida o que vale a pena capturar.

    TODO: localizar a tabela no HTML e percorrer as linhas.
    """
    soup = BeautifulSoup(html, "html.parser")
    tabela = soup.find(id="tabla_mareas")
    linhas = []
    for tr in tabela.select("tr.tabla_mareas_fila[onclick]"):
        dia = int(tr.select_one(".tabla_mareas_dia_numero").get_text(strip=True))
        coeficiente = int(re.search(r"\d+", tr.select_one("td.tabla_mareas_coeficiente").get_text()).group())
        for celula in tr.select("td.tabla_mareas_marea"):
            hora = celula.select_one(".tabla_mareas_marea_hora")
            if hora is None:
                continue
            altura = celula.select_one(".tabla_mareas_marea_altura_numero").get_text(strip=True)
            tipo = "baixa"
            if celula.select_one(".tabla_mareas_marea_pleamar"):
                tipo = "alta"
            linhas.append(
                {
                    "data": f"{ano}-{mes:02d}-{dia:02d}",
                    "hora": hora.get_text(strip=True),
                    "altura_m": float(altura.replace(",", ".")),
                    "tipo": tipo,
                    "coeficiente": coeficiente,
                }
            )
    return linhas


def parsear_previsao(html: str, ano: int) -> list[dict]:
    """Extrai leituras horárias das páginas de previsão de onda e de vento.

    As duas páginas têm o mesmo layout: um bloco por dia, com uma linha por
    hora dentro. Uma função só deve dar conta das duas.

    TODO: percorrer os blocos de dia e, dentro deles, as linhas de hora.
    Atenção à data: o bloco mostra dia e mês abreviado, sem o ano.
    """
    meses = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    mes_anterior = 0
    for ficha in soup.select("div.ficha"):
        dia = int(ficha.select_one(".f_circulo .dia").get_text(strip=True))
        mes = meses.index(ficha.select_one(".f_circulo .mes").get_text(strip=True)) + 1
        if mes < mes_anterior:
            ano += 1
        mes_anterior = mes
        for bloco in ficha.select("div.f_temp_horas"):
            hora, direcao = [d.get_text(strip=True) for d in bloco.select("div.f_temp_hora")]
            valor = bloco.select_one(".grafico_temp_barra_relleno").get_text(strip=True)
            numero = re.search(r"\d+(,\d+)?", valor).group()
            linhas.append(
                {
                    "data": f"{ano}-{mes:02d}-{dia:02d}",
                    "hora": hora,
                    "valor": float(numero.replace(",", ".")),
                    "direcao": direcao,
                }
            )
    return linhas


def coletar_mares_do_ano(ano: int) -> pd.DataFrame:
    """Junta os 12 meses da tábua de marés de `ano` num DataFrame.

    TODO: iterar de janeiro a dezembro, chamar `baixar_html` + `parsear_mares`
    e dormir `PAUSA` entre requisições.
    """
    linhas = []
    for mes in range(1, 13):
        html = baixar_html(URL_BASE, {"fecha": f"{ano}-{mes:02d}-01"})
        linhas += parsear_mares(html, ano, mes)
        time.sleep(PAUSA)
    return pd.DataFrame(linhas)


def main(ano: int = 2025) -> None:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    hoje = datetime.now()

    mares = coletar_mares_do_ano(ano)
    mares.to_csv(DIR_RAW / f"mares_{ano}.csv", index=False)
    print(f"mares_{ano}.csv: {len(mares)} linhas")

    html = baixar_html(URL_BASE)
    mares_previsao = pd.DataFrame(parsear_mares(html, hoje.year, hoje.month))
    mares_previsao.to_csv(DIR_RAW / "mares_previsao.csv", index=False)
    print(f"mares_previsao.csv: {len(mares_previsao)} linhas")
    time.sleep(PAUSA)

    html = baixar_html(URL_ONDAS)
    ondas = pd.DataFrame(parsear_previsao(html, hoje.year)).rename(columns={"valor": "altura_onda_m"})
    ondas.to_csv(DIR_RAW / "ondas.csv", index=False)
    print(f"ondas.csv: {len(ondas)} linhas")
    time.sleep(PAUSA)

    html = baixar_html(URL_VENTO)
    vento = pd.DataFrame(parsear_previsao(html, hoje.year)).rename(columns={"valor": "vento_kmh"})
    vento.to_csv(DIR_RAW / "vento.csv", index=False)
    print(f"vento.csv: {len(vento)} linhas")


if __name__ == "__main__":
    main()
