#!/usr/bin/env python3
"""
TEST: Smartproxy a máxima velocidad con 400 ASINs

Compara resultados de Glow API vs Smartproxy para verificar:
1. Si Amazon bloquea
2. Velocidad real de procesamiento
3. Si los resultados coinciden

USO:
    python3 30_test_smartproxy_full_speed.py
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import re
from datetime import datetime
from collections import defaultdict

load_dotenv()

# ASINs extraídos del log (primeros 400)
TEST_ASINS = [
    "B0C373KYWK", "B002F91TT0", "B0DLZQ8D9V", "B09VPPS96M", "B0C6FLF3X5",
    "B0DQL7BBKB", "B0CT8BSPND", "B07VPHR6GD", "B07GNK18VJ", "B07P82FSFW",
    "B0FHL1D6HS", "B01N46UYTL", "B07Q112TQF", "B0DHVPZ18B", "B0D7HGNMZ1",
    "B0D1K1CTQ7", "B0F543PKD9", "B07F1NG1YR", "B0DBL9CZFK", "B0D7LZ7RWG",
    "B08RL6GQ14", "B09P53JX4R", "B07H9PDL2Y", "B0FC6K37KS", "B01LP0U5X0",
    "B0DFDRSHBJ", "B07SKLLYTW", "B0FQFB8FMG", "B079THM2FY", "B0DZHR44J9",
    "B0CQXMXJC5", "B0DVH6N98L", "B0DRNJ4CBW", "B0FTGQ7V6J", "B084J4Q7N6",
    "B07KFLX8HV", "B0DW9BXCYW", "B0DN45YMP6", "B0CRTR3PMF", "B0C1QDNP2G",
    "B0F4884LN3", "B09D8Q8BXC", "B09RG6D2B7", "B0CXGDK33R", "B0D9H19PBL",
    "B0DW97VBWL", "B0CD33RXR9", "B00004Z64M", "B0FDG8TCKV", "B0BD7H2R3Q",
    "B000GAWSDG", "B06XF6NF5Y", "B0D2X9PWLR", "B07KB75KY8", "B08TRQS1TX",
    "B07M9LDDXG", "B0CT2BY5KL", "B0DBZS6MHK", "B0C2ZGQ15W", "B003NGDIX4",
    "B0BSG3J3W8", "B0DJNG7XP7", "B092RH28GN", "B0D1YQ3MML", "B0FKT28PP7",
    "B0CX69CS2D", "B0B4MZWCXK", "B0B4MWCFV4", "B0DFZPR9Z4", "B002N1KK2M",
    "B0DXZW9HPF", "B07T2P9ZGH", "B0FNRHNQX3", "B08QTP3MLT", "B0FHQ3LQJM",
    "B0F42MPV35", "B0CGLMRLLD", "B0BLMQ8BXB", "B0D1JTDPXH", "B08VWF7R91",
    "B09VGXRKN9", "B0B3FT3T3D", "B0B4M4JWYY", "B0D916T4ZC", "B0DMT133P2",
    "B09RX4HKTD", "B0CMWPDGZH", "B0C375272K", "B0DSWPJ1M8", "B0CJY1TRV8",
    "B0FV33PK2P", "B0BZPYXNFR", "B0F468NMZH", "B0FN75DTW9", "B0BG6YVCK9",
    "B0DWG1K24K", "B0FLKC6L74", "B0DQ7SZRJD", "B0B89C8H4Q", "B0D1Y7LKSQ",
    "B0CHTJTCLF", "B09FL5TQWJ", "B0C9D8DBZH", "B01BMYHBU4", "B00G46TFKK",
    "B08KRJGPKK", "B00F390ZW6", "B0D14N2QZF", "B0DSJM3N5K", "B0FKGPLGB7",
    "B09TXP1KDV", "B0CC51Q3K2", "B0DLBPFZ2J", "B0BT5YNWY5", "B0C4V5LWWL",
    "B0DGGNPHP8", "B07X9VSZMM", "B08M9M2NGW", "B019AJOLEM", "B0DYY5JC1L",
    "B07BHS63SS", "B0BXQ5RMNV", "B074W9FQC2", "B0D8C6GP7T", "B09F2XTF1K",
    "B0F1J12R6N", "B0F1HDBJKH", "B004V9WHDO", "B014KK7M06", "B0CFGFFDTT",
    "B0C9D7JFJ5", "B0FGD267SS", "B087WF59N1", "B083NND39J", "B0CRYRCHZ2",
    "B09Z67ZLQD", "B0B2V8BHPD", "B0C531QPQ8", "B0D53HVL91", "B09H5VSKTZ",
    "B07993PCW4", "B0BMKLJW22", "B0BWYVNYW1", "B01HGD8R5S", "B0F65M9JYS",
    "B07CTLNYVV", "B08JK7Y2SF", "B0BKRPJMWD", "B002FXS71Y", "B002FXS56Q",
    "B08BX7TJPP", "B07XQ2QBJ7", "B0DJ5P3BMM", "B071L3QTT3", "B0FLHXDY5D",
    "B0874XN4D8", "B0DX65SQXF", "B06W9KF8BG", "B0BT36VBGM", "B0CJR2191X",
    "B0D2F4T9RJ", "B0DPPKHV8K", "B0C5C477Q1", "B0C5CDVZJL", "B09B4V3N5W",
    "B07V4HCMVG", "B0F7X5JHR9", "B0FCM26BDZ", "B09ZNY8VNQ", "B09ZXR98LJ",
    "B0CB5JCNM1", "B073J3GWCC", "B0CKVD62NX", "B08HM3X3D3", "B081C946ZJ",
    "B08R36B7LG", "B0F91PZJG5", "B0BRT9C5S2", "B0CTTYRJJY", "B0FKJ6BZ7R",
    "B0CRHDGQRP", "B0DRY8DMCK", "B0BFJZNJ6R", "B0CTWHSSM8", "B08R8FSFRB",
    "B0CXD1D1KN", "B0BZWRSRWV", "B0CQ2HZ8MS", "B0DD3VZ8JZ", "B07X93FQBC",
    "B0FC69S878", "B0FM2TWFGJ", "B084ZKLQR8", "B0997VXC6D", "B0FF9G5HWP",
    "B0BX3XV11W", "B0DRVZ6S5R", "B07FR2HF77", "B0F3NZ12GL", "B0DLGBGH3R",
    "B0FPD23Q82", "B0F2YG21R3", "B0CJRGSWKX", "B0D2QM15P5", "B0BBVNR1GB",
    "B088685QVJ", "B0CGXX2HG5", "B0BF9TYJWR", "B0FPMNJY3M", "B08M8YSFC7",
    "B0D1YG4Y5N", "B08CZXS55W", "B00GRRN2RI", "B0BZVQC2MR", "B0BPRSQGQ4",
    "B0D1STVXZ5", "B0FGDC15DP", "B0C9SBKFLY", "B0CDX5XGLK", "B0F334DN9J",
    "B0B7HVZNMB", "B0D25T4F8V", "B0DC6RF3JG", "B0DYF82545", "B0C8CK2TRK",
    "B0FMJ4YVXX", "B0BCP7PRVR", "B0DSH3G51F", "B0DHRMZZ56", "B083QYHX3K",
    "B09V366BDY", "B0D4DJ6BRR", "B0DBM36WTR", "B0CJJPBBZF", "B0DB1XN58W",
    "B07ZKB4SLK", "B0CYNFWD2R", "B0BV2NF1FS", "B0F8HDRYTR", "B08R5K1YST",
    "B0B63VTW46", "B006INRNNU", "B0D417M67J", "B0CCDG91CS", "B0DJM4QW9B",
    "B08WHMVWJL", "B0892V1FTZ", "B0DK6ZC5ZC", "B0CC9C6P16", "B09TKF28PS",
    "B0BM5CR273", "B09PFCX8Q1", "B0B9RWGYXL", "B09FK1GSXY", "B0DJFW7PNM",
    "B001D3NTF6", "B0886ZPWC8", "B0BGMNKCNT", "B0CSFW3465", "B0BRVB427J",
    "B0CJZFM5NB", "B0BF5QY5Z6", "B0DZ78Q48C", "B0BBMRZZCH", "B0BBMV22Z5",
    "B09N744Y4C", "B0B1BR3G3K", "B0D3WVCW3P", "B0FXN2PQQ6", "B07R295MLS",
    "B0DR7W6CZM", "B0DFQ6Z4K3", "B0D1QYXBNV", "B08LNFPZLB", "B0FCSD4P8L",
    "B082F1RKTM", "B00KWRM78E", "B01MUBU0YC", "B0C9JR3N4W", "B0CMCSGPJC",
    "B08W2JSMHR", "B0993BNN1G", "B07WD4TSNQ", "B0CXGMPLWK", "B003FIN5MY",
    "B0CSJXT5GM", "B0D1T71W4R", "B0B5HLZCKB", "B0BC8QGB81", "B0B5QT3197",
    "B01469DJLM", "B0CBSQN1M2", "B0DDSZP449", "B0C7VQCCG9", "B0C4KN6635",
    "B0DX25Y9GT", "B092642ZS9", "B0BLTJD1PT", "B0BZM7WGXV", "B0FRGMLCG6",
    "B0963152JN", "B0CGHWFF71", "B0DYJV7TKD", "B0BZDPFH45", "B0D1NZGMXS",
    "B08JQNSWL4", "B09QXYND6S", "B0DG6LYP8F", "B0DJ2V9RKJ", "B0D2KYBBYR",
    "B0F7KVTKLN", "B07T67CLB7", "B0DZT6TPGQ", "B00VU2NHVG", "B07YFT27K9",
    "B08YMBQJ49", "B008BMASJM", "B07NQVWRR3", "B07MNZ7C1M", "B01D47DUD4",
    "B0DTYNB8YZ", "B0D79SLYRG", "B0FLDM5BSX", "B07GQT8879", "B08C8Y5XDC",
    "B07Y1C6GDS", "B08GKBDSTN", "B0C2L54Q9H", "B0BHQLWR84", "B0F87Z5V45",
    "B0D54JZTHY", "B093PNQ82J", "B0CCNZDNSN", "B0BRLYT8M1", "B0C6YBHKJ5",
    "B08JGP1WYM", "B08LQ3867X", "B098QKHRGK", "B08G1BBBQW", "B0F83XMKHC",
    "B0BNDM2RNG", "B08131HFSG", "B087M2ZWXR", "B01728NLRG", "B0D9GRD6H7",
    "B0CXSL7BDP", "B0CS6BWL4Q", "B0D1QKZWRS", "B08J4C8871", "B0BNPMJDB6",
    "B0D9ZJVQCD", "B095K84L6H", "B0BYDS9KHV", "B0DSPJPRXD", "B0CZ6XY78Y",
    "B0CYQ5P6T7", "B0CY2C7H6S", "B088WW5HK2", "B08HRPDYTP", "B07PJ7XZ7X",
    "B0DXKY469R", "B0F9YKTYNP", "B0C88ZB3D9", "B084HC9FPB", "B00PLBXUMS",
    "B07ZJ22XM3", "B09HBFNQBR", "B0CMHJRB6S", "B0B4N6B93J", "B0C45H4WG9",
    "B09B5CTHGB", "B0D3633DVB", "B0DPXSS7KX", "B07HXMLCBT", "B0C1MYB5KK",
    "B0DQGQW8YH", "B078GPS6KV", "B0C7L4K4LY", "B0FKYYG389", "B0FCC81G12",
    "B08KDNG5FX", "B0FGND9HR1", "B07TNFPFZ8", "B0D8WJYSF9", "B09BKCDXZC",
    "B07QK2SPP7", "B07QK25652", "B09GJVTRNZ", "B0FVW5YGPD", "B0DDCLFNMF",
    "B0FQ4VQGBW", "B0D7C5RS6T", "B0DZN763X5", "B0F6C9NFCT", "B0DBZP597C",
    "B07D2JQMG1", "B07Q8KY243", "B0CQZ1P9QL", "B0DX8BDZF6", "B0CP92Y52V",
]

ZIPCODE = "33172"
SMARTPROXY_USER = os.getenv('SMARTPROXY_USER')
SMARTPROXY_PASS = os.getenv('SMARTPROXY_PASS')

if not SMARTPROXY_USER or not SMARTPROXY_PASS:
    print("❌ ERROR: Configurá SMARTPROXY_USER y SMARTPROXY_PASS en .env")
    exit(1)

# Resultados esperados del log de Glow API
GLOW_RESULTS = {
    "B0C373KYWK": {"available": False, "days": 5},
    "B002F91TT0": {"available": False, "days": None},
    "B09P53JX4R": {"available": True, "days": 0, "price": 35.99},
    "B0DN45YMP6": {"available": True, "days": 0, "price": 39.95},
    "B0DFZPR9Z4": {"available": True, "days": 0, "price": 42.99},
    "B00004Z64M": {"available": False, "days": None},
    "B092RH28GN": {"available": True, "days": 2, "price": 149.99},
    "B0D1JTDPXH": {"available": True, "days": 0, "price": 47.49},
    "B0CMWPDGZH": {"available": True, "days": 0, "price": 26.98},
    "B00F390ZW6": {"available": True, "days": 0, "price": 18.89},
    "B0FKGPLGB7": {"available": True, "days": 0, "price": 23.23},
    # Agregar más según necesites...
}

def extract_delivery_info(html_content):
    """Extrae delivery days del HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return None

    text = delivery_block.get_text(strip=True)

    # Buscar fecha
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    match = re.search(date_pattern, text)

    if not match:
        return None

    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    month = month_map.get(match.group(2))
    day = int(match.group(3))
    year = 2025 if month <= 1 else datetime.now().year

    try:
        delivery_date = datetime(year, month, day)
        days = (delivery_date - datetime.now()).days
        return days
    except:
        return None

def test_smartproxy_asin(asin):
    """Test un ASIN con Smartproxy"""
    url = f"https://www.amazon.com/dp/{asin}"

    # Usar username directo - ya tiene Florida + zipcode configurado en dashboard
    # No modificar el username, usar tal cual
    proxy_url = f"http://{SMARTPROXY_USER}:{SMARTPROXY_PASS}@us.decodo.com:10001"

    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        response = requests.get(url, proxies=proxies, headers=headers, timeout=15)

        if response.status_code != 200:
            return {'success': False, 'error': f'Status {response.status_code}'}

        # Debug: verificar tamaño de respuesta
        html_size = len(response.text)

        # Si es muy pequeño, probablemente sea un bloqueo/CAPTCHA
        if html_size < 100000:  # HTML normal de Amazon es >500KB
            return {'success': False, 'error': f'Blocked/CAPTCHA (size: {html_size})'}

        days = extract_delivery_info(response.text)

        return {
            'success': True,
            'days': days,
            'available': days is not None and days <= 2,
            'html_size': html_size
        }

    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}

# ==============================================================================
# MAIN TEST
# ==============================================================================
print("=" * 80)
print("🚀 TEST SMARTPROXY - MÁXIMA VELOCIDAD")
print("=" * 80)
print(f"Total ASINs: {len(TEST_ASINS)}")
print(f"Proxy: Smartproxy (IPs residenciales rotativos)")
print(f"Target: {ZIPCODE} (Miami, FL)")
print()

start_time = time.time()
results = {
    'success': 0,
    'errors': 0,
    'available': 0,
    'not_available': 0,
    'matches': 0,
    'mismatches': 0
}

comparison = []

print("Procesando ASINs...")
print()

for i, asin in enumerate(TEST_ASINS, 1):
    result = test_smartproxy_asin(asin)

    # Delay mínimo para evitar saturar (0.5s = 120 req/min)
    time.sleep(0.5)

    # Actualizar stats
    if result['success']:
        results['success'] += 1

        if result['available']:
            results['available'] += 1
            status = "✅"
        else:
            results['not_available'] += 1
            status = "❌"

        # Comparar con Glow si existe
        if asin in GLOW_RESULTS:
            glow = GLOW_RESULTS[asin]
            match = glow['available'] == result['available']

            if match:
                results['matches'] += 1
                comp_icon = "✓"
            else:
                results['mismatches'] += 1
                comp_icon = "✗"

            print(f"[{i}/{len(TEST_ASINS)}] {asin} {status} {result['days']}d | Glow: {glow['days']}d {comp_icon}")
        else:
            print(f"[{i}/{len(TEST_ASINS)}] {asin} {status} {result['days']}d")
    else:
        results['errors'] += 1
        print(f"[{i}/{len(TEST_ASINS)}] {asin} ⚠️ Error: {result['error']}")

    # Flush para ver output en tiempo real
    sys.stdout.flush()

elapsed = time.time() - start_time

# ==============================================================================
# RESULTADOS FINALES
# ==============================================================================
print()
print("=" * 80)
print("📊 RESULTADOS FINALES")
print("=" * 80)
print(f"Total procesados: {len(TEST_ASINS)}")
print(f"✅ Exitosos: {results['success']}")
print(f"⚠️ Errores: {results['errors']}")
print(f"✅ Disponibles (≤2 días): {results['available']}")
print(f"❌ No disponibles: {results['not_available']}")
print()
print(f"📈 COMPARACIÓN CON GLOW API:")
print(f"✓ Coinciden: {results['matches']}")
print(f"✗ Difieren: {results['mismatches']}")
print()
print(f"⏱️ PERFORMANCE:")
print(f"Tiempo total: {elapsed:.1f} segundos")
print(f"Velocidad: {len(TEST_ASINS)/elapsed:.1f} ASINs/segundo")
print(f"Velocidad: {(len(TEST_ASINS)/elapsed)*60:.0f} ASINs/minuto")
print()
print(f"📊 PROYECCIÓN PARA 50,000 ASINs:")
time_for_50k = (50000 / len(TEST_ASINS)) * elapsed
print(f"Tiempo estimado: {time_for_50k/60:.1f} minutos ({time_for_50k/3600:.1f} horas)")
print("=" * 80)
