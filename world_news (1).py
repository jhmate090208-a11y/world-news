#!/usr/bin/env python3
"""
세계 뉴스 + 현지어 학습 (지도 + 단어장 버전)

사용법:
    python world_news.py                 # 기본 실행
    python world_news.py --translate     # 제목/요약 한국어 번역 포함
    python world_news.py --per-feed 5    # 언론사당 기사 수 조절

번역을 쓰려면 먼저:  pip install deep-translator
지도는 파일 안에 내장돼 있어서 인터넷 없이도 보여.

실행하면 world_news.html 이 생기고 브라우저가 자동으로 열려.
"""

import argparse
import base64
import zlib
import html
import json
import re
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# (이름, RSS 주소, 언어, 나라, 위도, 경도)  — 나라는 "언론사가 있는 나라" 기준
SOURCES = [
    ("NHK ニュース", "https://www3.nhk.or.jp/rss/news/cat0.xml", "일본어", "일본", 36.2, 138.3),
    ("朝日新聞", "https://www.asahi.com/rss/asahi/newsheadlines.rdf", "일본어", "일본", 36.2, 138.3),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml", "영어", "미국", 38.9, -77.0),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "영어", "영국", 51.5, -0.1),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "영어", "카타르", 25.3, 51.5),
    ("BBC Mundo", "https://feeds.bbci.co.uk/mundo/rss.xml", "스페인어", "영국", 51.5, -0.1),
    ("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada", "스페인어", "스페인", 40.4, -3.7),
    ("BBC 中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", "중국어", "영국", 51.5, -0.1),
    ("人民网", "http://www.people.com.cn/rss/world.xml", "중국어", "중국", 35.9, 104.2),
    ("Le Monde", "https://www.lemonde.fr/rss/une.xml", "프랑스어", "프랑스", 46.6, 2.4),
    ("France 24", "https://www.france24.com/fr/rss", "프랑스어", "프랑스", 46.6, 2.4),
]

LANG_INFO = {  # 번역 코드, 네이버 사전 주소
    "일본어": ("ja", "https://ja.dict.naver.com/#/search?query="),
    "영어": ("en", "https://en.dict.naver.com/#/search?query="),
    "스페인어": ("es", "https://es.dict.naver.com/#/search?query="),
    "중국어": ("zh-CN", "https://zh.dict.naver.com/#/search?query="),
    "프랑스어": ("fr", "https://fr.dict.naver.com/#/search?query="),
}

UA = {"User-Agent": "Mozilla/5.0 (world-news-study-script)"}


def strip_tags(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def local(tag):
    return tag.split("}", 1)[-1]


def fetch_feed(url, limit):
    """RSS 2.0 / RSS 1.0(RDF) / Atom 처리. 실패하면 빈 리스트."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"  ! 실패: {url} ({e})")
        return []

    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        d = {"title": "", "summary": "", "link": "", "date": ""}
        for ch in el:
            name = local(ch.tag)
            if name == "title":
                d["title"] = strip_tags(ch.text)
            elif name in ("description", "summary", "content") and not d["summary"]:
                d["summary"] = strip_tags(ch.text)[:300]
            elif name == "link":
                d["link"] = (ch.text or ch.attrib.get("href", "")).strip()
            elif name in ("pubDate", "published", "updated", "date"):
                d["date"] = (ch.text or "").strip()
        if d["title"] and d["link"]:
            items.append(d)
        if len(items) >= limit:
            break
    return items


def make_translator():
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("deep-translator 가 없어서 번역은 건너뛸게. (pip install deep-translator)")
        return None

    def tr(text, src):
        if not text:
            return ""
        try:
            return GoogleTranslator(source=src, target="ko").translate(text)
        except Exception:
            return ""

    return tr


WORLD_B64 = (
    "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"
    "6rN+e/1JL0CPV6D0EpReg86XV6H0MmSvQ+mF6PFKZC9F6bXo8WKUXo3Sy1F6PUovSPaKlF6S0mtSelF6vCqllyV7XUovTOmVKb68"
    "NqUXp8erU3p5Sq9P9gKVXqEeL1Evr1H0ImWvUull6vE6xf5ECXGXJ5FuTyL0PjtIcCi0RxH4qCXag8iUSZWwGQfPq+jBBFjD2HW9"
    "iqqO+7Uhhi6cf3FfN0TrBUl0NJ2bcR+IepFKrX8wJMHmfpIovY0PHsV36VUJJ115QgLOfSpMuruoL7mPDblgFG7HH4XBzACj70TG"
    "T6fzPpjhcLjSgw330XQtGionRN3J5yBuo6guuR8niuqT+1uUW0X8xnZDucT6wmUUJSj3ufBsXHWuKfQ+mDbsw+FpPGqXppMCltvX"
    "C93O1e1Xq8vReSj3zepHv9ZuzWu1wnlJlCfVVChJdVJMmSJpk7A6ffH1yvmM16tZImoYnb4WS7FMH1HWI+Ua1gsf5rwXei1hpPSs"
    "vhCEwblWfNaOuZbMtaXXmrn2zLVork2ftWquXXMtm2uXz7f3asNaX22cbZ7vIN9JvqN8Z/kO852+33F/9YHsE+4j6Hu4D/ocvlnE"
    "l+XwcLiJFvGoz7Zj2kRiU3yXmeWnD2xTIAntbXHY6oXxixJ6nsQhfsjmXLiMPjmFlQrW2dPWJ0TZLwmnr0+dtE3P7UhHtJULrGSI"
    "nvOHvT2yHsX1qjwxcP1h/zS/7H1s/5P2QI99UNoL9d/2RGlf9Ngbpf1R2iPZPintldJ+acl4f5NTpxub89u8E7hlxL/tmov3Z9jm"
    "Pnu+cBg7J1I++JHzET4X0S/uhK/7xR2bEx3RJih+/Lh9bHYcVp4MKktO+kbGcU3YqRgGykHBojjpwk7QIsRJFyFOu6DSqAZKoTjp"
    "MEAOk0VCCTFa9XU5VxNKYMhy7TRAuDTBwC19E1Mrw9UCRrjQajpGUHymC2OVQLLKBy82swyX+GDo+IwTEZCb4kKf0Lz/kLKqsBub"
    "2o0o5dYYUnq98eTH9BxSCz7IABsmvuR7E8es+4MuqxGDCYNpOAMhF7wDBzgwyWZSMoY/Rl6aFMfmvUi/5j1Z956z2wtdFzWV9ram"
    "R2vrs9d99r65F/beOPfKz94599K5tzbhexLA5zlsnss+57R5bjt8Ljg53gvtSYm+HORrhPHV6Zq94TWf9zZ7mGrS3uVzbe81H697"
    "by984XTy1cC9+jrGpfRLpLskSyS63CW2BtJj2S97sz92xTfHF+GwDGCIFYPthPtQzmkMyyBQzhABGGUWqF/33lrvkcRd6e+w2f9h"
    "NWrUHWMbNViMoY+fdx6+0zD1fiIpou3vsMuvzsCo3V0j7HeGpQ7DUgji/NT4eYJ8onzCfOJsAbdIttDTYtmC2aJu4Wzx5w3kG8k3"
    "lG/MbzDf6POG842//TL2l9/G9OOYfh3t5zH9Pj5+INMvZPqJTL+R48uvZPqZtN/J9EP5+KVMP5V8jzibeDwNNXsaKqxZs22amEDC"
    "TCsPM8iLKcTMIckk8jCLJNNIMo8kE0kyk4wv5pJkMklmk/Ob+eSbCeWIsFpoj0fNHpB4X9fvlBeaYeVBe3IKM6rE/HhQejwqrRe+"
    "PTCNLw9NkeR22LnRU8nLg8nj0SQ+Hk/SA8rjEWWJJHZIkxR9WGiS0CF/syS7rSblpZQBZ4J0qdf/DJ08EkIcyVs00WaLXm8aZZMq"
    "J8WyCZdFv2wy5qRmNlFzeUCUL1OeDKeURKZ0LHDACh6wyv5tttglXzlLLmhMCbulLLPl8XSLP/bItx89RMQf+HZcZD+H8cGRrQKU"
    "aYbYSu+XDXeRt9G22nLLDmXrq11y7bgkx5sinGGtN5+9qM0K6dXQBNC5uO1C1Qs067+/nMenPFxuNgV2ZcWRmHPlFdMz+9TED+sW"
    "TNRSaAt5sgw5sgx5+QtRqZjFxm5dwwsduQCijUtndhyLepHilF4ayeWfOWhCzo+iot4gfbAHUBL3hXRwQgKikGZM5ij2qSnXkdue"
    "O+UgUvyIpFL5GDWnkfPL6PnUxyg6jaQ/RtNpRG3DwjSyfoyu0wg7jbLTSDvdhdt9eLoTf9yLp7vxdD++7L68vt2VcxUEycPBegYi"
    "hAMqcMgWFBMZgx8jL61MDJZvEG4XrHluOb1gqXP7oH/0+yPyB7Lfr7cXUIJ3JEb2O8f1iux3K+MfkZfK+8fW8kzlIDFv0fNeLLDq"
    "Fq4Y6oxcELGw8pCJfH6EKh+n/mQjgOJ8opsh2/1cAudU+oGazZU/brZNZnRw3CV7+k5i9Z1U6zvZ03H+pUsrE/MHevb2j1Nc4Gm+"
    "hZo+Kz1HxvT3pZqXWDEUePyeeAsk5t35I7PruSIfp/mR0Qo4qmS7rJ4x4ZLXcK6VBS5a9VLSLWsAWkrj1IIYH4SWf9WKdNVmFBeT"
    "UFbAwmWU8yOhrIZpWV7CqBNnWEkIdfIMawmWX6T5tmzZznJuZxFWWTMcW+OeLeuPY6tkWGozPGS1S+teaSrKqnfzOZnfFv2r2vKb"
    "2GgV8cFw/DDC+oTt9u/vsim/0OYoT7gaIVZc9k5E5XIYwkLpcbafD/lD/W3s/Rh/pzF4GoensfjbeHy8jMttbJ7G548xuo3TH2N1"
    "G68/xuxp3G5j9zR+f4zh3XQ4NL3z1QobTIcOm1dzOA2q08A6Da7TADsNsh8D7TTYTgPuNOjWoe7i4QjQ46MPd2koxLAMq4nL9YOB"
    "uM1Ql81Pl81Yl83ZqFy/urGpXZbbA+08ZJzG9njQJADTRv7TyvXTRgbTRgbTSvkzlfyPlP+J7Ac0FUy3r8PuXofdvYpbmV6V6PY1"
    "5E611Bd2eVfqdgX54HS8vUh1e5F6cMn1JXG8EEvP7nLC2IzV1+srvn852YyXE850yplOOsPh8PVhnM6/HN5+Pm2W9JzVz59ob1Pd"
    "rjm73e72eLnJfbvNXS+3umxvtDxEw2AcDUku4BMOEgvSoLYwikoOYkT4wQpS0kl0D6NOiAmjSCUt6DTcNTx20nm6ngAKBHQCbqej"
    "229i+01st8DjF6t8+cdqj/+s9Kf18a+V/rbS/1b647J/rvTX9fjvSn9e6d8rHcSmw9h0IGuHsulg9nE4O74c0tpB7dthLR3Zno8j"
    "Wzq43cZlHKovicumUVSzaB+GT1E9TjW6fsf1O6YOPM53tigAz2F9IX7leyz2+XdUPxzV8L0Tq7FT3AvfflB9I9I3YFA8TNJb+/5j"
    "P2B4KdzKj/sTzFmqvkXhorkJvj2GB/i4lsMyCmAYlp1VxlLkCWNYzPnHyv7kDYNFaHV5ZRtlVHA8lpDXC+lK1qPwm1B5CHeHO78Z"
    "3vdBU8jBELQep2M5IDJrlFioIsUFN9/IRGQooIgwn/FIX7T/ZPoHjyoES1KVa7kyDvg86myPFpSrdlMchg4yqSRA3IrvZhbrDYSC"
    "ktKxRmGCwAeXahhuunDTMV7aB86PR5Yb7GM32seqHceqH8eqIWrLImR8vHB+5RuO9zsnLt/Quh0kYQuTr4VJ1qI4vvw4HTJIIZJV"
    "rkOP/KAftR6FW1XG1oxmjWtmg2tO38yy1vIlFde4OmwWOlZUwgk1aVE9mlntmugnIcQQLsdPh+crvrg+OjASit5S9a1+nubn5XNz"
    "D1Q0tN4fi2PF/TEzRkRj/jHyB1bAHCiXc3HZrXJum3JMvnU7Zls8KuUcszKSkv0+GwQrRNGana0ihTf/NtMeBDUPDudfLg/3Ccdr"
    "TBTel8963Gc/y+HldKzfrSgkUeBA3GLkPJDkgEMRN37w6MZHFSbF5zF3KLHxOpHXKx9I2JV+62zrbDF5HvJjdtqck4vR/JiwMSdH"
    "43K6qbOxM12vh+PxxflIDkhzMKI8PDCJ74I27Hzgtd2gzsfnzXoB2Q54c8ctZRLIs18tV91yRW8UHIZk7Nt6A8RuHL5uLsVjskjP"
    "xr6PDaY+To/HyylyOkl+O00uL6fK3U6W7e8Ge/5i8mGG7Qz4HJukxNs05WOq8piuSDQnrEYbJlUbJlV7jah23oDtlpVmlO6YuLYZ"
    "rd7YbMbSbOrYrIbTrAaEg4vHLXW6qY4P/nJrbTfX6fb6cYOdbrHZnlih4egEKy0bHkbXUTeo6YmxXzhEPc/01SMDOR0wMUU1mgKh"
    "iTpFuGRoipmTiiWHRI/CLu6FJgIkYZMBKjFIgfIxYB1fBqVpYFp+G6A+BqnLYXNCYCv6oGYLYX+Fu693h8PhZqxOXzlms/5VBAyn"
    "5vNWP38zymiZz/u0T7ZX/XE7/vK7mf4f0x9k+ofcL+wff5LpXzL9Tb79T9Iw8e2fMr78V86Xf8v0d5n+L00DVO33t5oGqHanD5fT"
    "jHJhonDz9Wosfi77RWZ9w8+Tfi7hywBni3BtgINEIQjgB09mQRQPFRYQzgsHTxVBTI9DRWEzThLas7ylw8ug6ccybiF2PpA/YadD"
    "ExO5jhCuF3bj8PUlBCE9yqGziMqTaBDmMwxBEIn4l9JP50c8ysPzdBHcC/n8ENEfGVYJu+gyjukziDZlPMPXu9PHK99M879mhy3N"
    "DluaHbY0ef6kQVC1oVJ1+mpijF8GTvNlQJQGRWlg9DY4ai+DpGk0kUc7LxyOt2EUwyIkmfYuy/uFHe+EHJYyvjZjUTyeLzzGUuC+"
    "jFvlF9+nTMcPh000UsIohbYkEf+QiifJeJKOs50wEi55cSNJTAuRwWBVNdWSx+RGxHB8mHWG4fkJY7VGDCPYeXTQQ7KYapKZWlRO"
    "ObpelsNLJDKIRz1qM44f1/PfyyI0vqbB8mURmhai+4XzseD8e7vO3d3eF7LuunDCWct9afSTjQOURsa0+/pgksCTlUbHovAfs5Ae"
    "stIGjrVK/zLkUht0AENWNZShghBXkJDHSXRic2899w8rANE03LpsudoUTpzIKH4Y75PzuIZJGR/4t3AWJk86998/vk5zAhGKgP5f"
    "EImxfimSKbEwanAHgwUeBvq7+ADADRBWbYdwZ14AU+IeA55jzh03SEOk/DgdAOkS3QiBkhv7PzmXOXTy+aN8//5CXgzSx9tw5Io0"
    "FB7rnSHo8BwEnhqQhBx6FYJ8uEs8TKA3Gwh1Yatc6c0GckLyBIUAhwdkFwoRdjI0dM0Z+GgQccMyurL1IEgewaLRxKwuKOQhzCeL"
    "AFVYcfZBxaQuXmZEbrrPIXRyxWOvetu7L+q8dmkw9U2NWegPoYE31ZKgRrX5nqAkRd0iJcHDi6vbwJ0/r2G69qqEixC2Fubsoaka"
    "K4OgZyWwayHyrpSGKLGw+hgK3QnKfFMMqRS4YqrcJyB012hIco56JtqJuIw8USRO7LJw5IqjCJ3AUpNGuBXfu8Kdx5M83Jk8tymK"
    "v71o+tyD4bkUhlekpi+C6Tc/LMbz7AJnoFNnM8tf1LaD2l2NzRhKryOT/odbwFmFt99yA3jrxf3frQ83jbfduGe8Hev4eY71ghR2"
    "uqBb6/v88w/PeIDT8SiXriydwD8GRy3HMI+4je4PkR7d1pWDzPtDY+n9IT6ju0E9HCW5U1UajPQskONdUWKem1VXQjblLD8ry4eN"
    "qoePUONEUWPdtTAb56ZnI1SHb3naNocaAebs2mgROk6uCZWjDGHy2n1t2KPet0va/gWLd9KzlSl6tGIat7LJ4s+JYUxPFMUoDQFh"
    "iA6ualzCNoPpID4Y4tBCb8eUiJEKUzbp2MK0cN08dV3eAIRmS4twOLcOZk+LMJplDWGUG1o6sBzexxNol7tg0sFhwsR9Ub/ueoLr"
    "DPF0y7t0n2YOnOatRRM3PSdu9JNq7hpMlFhqYOKs4uA63v4dcnwVilmE2gZCbPLB7vhBFUbaMhzxHMh24G1zYBuExybBNgpps/DY"
    "MNimIW0cHpuHtIGov20kHpsJ21CkTcVjY5E2F7bBSJuMx0YjbTZsw5E2HY+NR9qCnC+bEMenzchjQ/LmAKsPR9iHMyw5xJJTLLnH"
    "zDn2cJA5PjnKHs4yc5glp9nDcVZ/c6A9nGjmSEvOtORQS0615FhLzrWHgy052ZKjLTnbksMtOd36b8635IB7OOHKb844c8glp9zD"
    "MZeccw8HXXLSJUedOeseDjsvzR+Ou+S8m/+HEy9UXpjvKKbDR+V0p6Nj3W7Hurai5PV0tDtejnjTMe/8ctybjnxtbZSOfh/Hv+kI"
    "2I6Bh5foeE9hjiAszTGOhSxD+BxDbKFk6GzHuHW9HeNSeURvgTyeKdwdbsbq9EVMn0SLcYbFON3vpet9k4GX6Pfm72t2aXBNun0O"
    "WlgIp8RFMV7YqJBF8RKxOH11foeLLDM+KAsNYdP6PCTuEoY4JcjUsl/YXjwnyXsS36QoSyHxSmDf2ahvhdCWKcjWfbYMUcCuFeRU"
    "xjVw8TSyLzNkfTKpnIHz6d5/jo+umTTPrId22wgqZ7cJoU82pEiGxcxkv5kipFvqPSALui+brMeNkXdoW7IPMBWymZFJvHr+kL+1"
    "PrB4B5D7DW5I0DNMWc3Iw+yTtNJTFNDo1Et9fMln9RSXxBT1xJSD6im/1Hja+3UkHF5bohabYqWcotTA0XehSh0W61OMl1NEk1Oa"
    "HwjdoZbApsNAgxDWjA5plML5eHABiON8nJ7frotS4AK0c1mPDL3rWhUoX+c+ibCYb+gwH3RHowg2NxWDC1wczGMnNbigZaRcA+AO"
    "k847MTBPjcPUBFiC/WfpHN/qF9AGgMdSjehTjglYSnsKE6sgKji4SEcSVBBeUJtCIn9EzaZqNrn0hoIIUsrdKpiaAPcFYKNyRzbS"
    "OHEXARWyLnce2EXc98CQNiGFezZoswHuCqHLcBXQ6A8W7jW6vGsQFvc3XXsfGLAczsgherYQ+1+IpC1k6ciDOwi/Bo1LcSxHqzRl"
    "lDULAFpbsv2Lu7ucPPIgoUgTz4gnAUJQu0+ubueW6h7UgrciN4lKmmYdwiLQzQ43l02s8w0bOhoDcOGA+zcqLuLxUSkoEBY674Bd"
    "II+65SRmyuJ40/gFtpEsBbIq+r8KDmSk3AxTbUY1ytcPBhVSaeK8+0GR6nxwOF13fslYk/DoTYC0P6ZY5YMy1aovbI9p129Co4/p"
    "10N49BAgJSGSCJKSMOlznyRUml+ES+c3IdND0MT6k55Uxm3TJCfTpCfTZCikLa2m8aQ5ZNAom7SlxbSfxTSgmDSGVMGETZMnTK2G"
    "nK9wEjyiFYX+kcLD4dDkeGROSYcNWFxtT5LbdPUPdmO86LFNl5302Q+ddnxwnRf9dtJxr99uBdLNQLodSDcEv0gd40X6mCSQMv6m"
    "gwXUe+tNkFCYDiikz6VwczheElq3xyO5TUlsSmZFIiK0Kh5V7UTd+FHBS5U8k9NZZY/fYVV9W9Vij+97V2PRe4eCfZU7BGEzVmNx"
    "vzjKt4r7D/sTjQQbNQVodNc1peL8nWEauorcdIY0BRTWMueDnVO4UIoC07QEiteypdFwNYxSXeBXi/sRRX31QVFbfVA0bUKpTMzq"
    "fFWqErNKs2GaYmJW57OOxqQOiFyvC6ux+HqW6/tYRYOazpY887mK26PIn/001YSwSUH6wer4ImySXDcqUktbYNqsk+XabuzBWl+0"
    "heODRZJ2Yhx/0dXYOFZNu+chVhlCs2eRHHSIKBjLWZOZ6vp2ei2DOfJ0kYBOk9kKjwiI8Zw25yJhcUzjEqFx2JiThtLsb796nt9E"
    "l0YcexgwpPWj+OV02xTJxdTI5UWNnFTJSZ0sI0/20CFTZ6EpksNUyyHzJPZAkyk2kysKh7Eb5fJMKMJAaBkJ3QO7eyDqXaUJ+Olx"
    "2QOzR2YPzR6bPTh79Pnd458voL+wvb6Y/ILOC8vni3u+wPwi8wvNLza/4Pyi9wvjNQK8R4T9GjFeI8jzfuWqReY/nD+b3LOgT/Wt"
    "vq/r8TLRTpPtNOFOk+408dasmCbgH5PwN73PftG7JN3Lm/4llJ5YGN+pDdV033A9wibjEap/2KQ8XL9Ik/Oj+jG8jNvx63OdKDfr"
    "IEAUhuPTLTmFjEF9flB8puTTP3pemvJHSzlyUHbZav6QvgpFza8fW2n8o/lSs19a3sRR8jzrH0OJ/KPnJSZmtpLX5G+WEu9GJf0q"
    "R68UozbKTz8xx2mUHQXhG1Gilj+qf9BFreWz/lGtrKRcJAlImmCbwBXT/BaNJcKpN45T96KxSFid3kb8xPXCarrhZgzTDts4H6fc"
    "SUP80BInTXHSFrN+dFqeTsqnTeaGMRzfjDaZW+WF++XSvv4fJ+br5eQ8nZ6nE/R0is77kxLS48eWRvHcciTHNQepGP09L5khck3R"
    "vZaIbfRaw5SMwqr4JaVHrNGEMp7jWoYoTb+5PYPsYVwvXMJejM1klhyxTjU2jVgnXjiMy+iNDWpyPBPRWn1yNciR3NbsrBlGftQU"
    "4gpa24tssk0/MTb2UM56nAj0L2cC8SLVny+y/aWWA6Kl6FZM1u+fN5BvJN/QqwWyRcL1DpFL3udN6tzor3Pv8XUunufk73Pz9XWu"
    "vh0+pmArpl4zCW63jtMvyrb5RemWtO1J4x5fNO/fFEUZLnbofj5UR78oj9JBvF0bnW1H8+mA/u2QPl7Owc8v5+EfPQC2F7RTpmb1"
    "WJrlhdIaEW7Hi7FAuBx/FJ7FKC0TOFZlfobD4eZwe4W7EeUWhdnHoGWyVe50+e5LYeNrXkd9VH/STK0v/bLzS//so482vvTV1pcj"
    "9nTMXl84HkfuH8fu88vxezqCry8cxm79tu70prtqprkys4LIhD6OwKR9Qg23kIHky6X7y8X7cjo7pLIofNjdiPJ3l2dSN4arw3Zw"
    "9Tgeq3ZMhbZZMoBdUqEwwzmJzzvNTO/jbWkjQuRwHwamqzjWk2ewIw4GiAm2JLRSZDTTeuliXiduxS/yXj92r7aCtU2sLWRtL2vr"
    "WdnS2rL2ZWc7Pza4ssi1fW5a68rYV7LIx67XVr7zMQSWftHS5mSJTBx+uvHoqOihaFl6mdUoQ9SzkWrTVBctswT6kM/+hAYbCK12"
    "foW2wPmm8s0flfmP4x7EB7fOBIQocnqxLA3J4IXN8c3sS2H2pTBrUzcmK9OLpYnT+MePWP3tZ+yX/73y8XzweEKwZ4THU4KcXwkt"
    "YLFMnH4Sib4PUep604ZS04ZS04ZS04ZSH7+K6Wcx/S6mH0b7ZdRz8GNLforkq2gfbPuL3yJe/BfJh5H8GMmXkfwZyaeR/BrJtyH+"
    "/eTj/7XxbfHZGD8b5ffGeb821rnRzo13bsTXC+O1cc+NfG7sPamW4Q2/DKVmLhVtYDXOfIVlus0lHw2/ZPLOpeY+RhmZ8PkfdDv0"
    "YdRgxHK3l6LbS9HtpSjTuZ0zHC4nXM7DLlGTaWWYYeVB8GvILIbMKqhRl7GIwt3YhJhsvdETLjO1LOXjdbOCdm0shWZBxRORpan8"
    "uD7kcUpPOfJFTP6kEG+dPOeUF4a5L+1lvJsLs5tfiSgRwvYTsRxI833nDz9U8kXFC9/8TOZrogjCnI3dHJB9mmvTHJ04H4j+CseL"
    "izO5OZOrM7k7k8szuT2T6zO5P//b1ZkdNg7DQLSh/SAJHlIPSQPpv5DVHKAp/3hCXdZBKxKBwctaoFkbNGuFZu3QrCWatUWz1mjW"
    "HnUt0k2SSbJMkmaSPJMkmiTTzC9yjUk2SbbZpJsk3yQJJ8k4ScqZb+JREpA2EYnXfVOl7g+NKelMSWtKelPSnJLuxPtbVxYAVQnj"
    "MoZOty8vZxIaA0hKd2aWADUNpjaUDiWKq506vB9DhlZOryIyDyWka7+X99u062FSH9th9fa7Es5pBKaG6VTTuj7nAYGo0Q4Klc8X"
    "lecPZ3IzoJMJbUZ0MqM3Q7q9GdPJnN4M6mRSJ6PaR1y0p2TxMbuwcA/J+hvFTMBlRqDzHHZ7aDu9f7ED18EQvF+MwQ9zMBmEZhLW"
    "eqjSDbl8VR4C8zC68zSwnBPml1PzaaXGfjWf4XCPClkQmA+CK919frp7DvKSqLIYSC9ZtnFlQ/9Raa1GZBVxeKgpIPy+2ZPVTXvj"
    "kIeHOpmJRM+PR1FuDtDIXPBp53K53mWl0WPof1YM3Xeoz32I06n9037u1F6etZtMC5oKsJDlulQ9ioyMKeM2mbF4RMT86eVmNdTX"
    "VCLYCpD9kTrNeCVNWBBSqYq4sJ4y26YeoRDLEhxU862rHHSipBUlvShpRkk3OmlHV9KQ+KSm/sAnp+48kS7Cn1Q1VUmgNnmC06mX"
    "9TaRuhzs72SBJxs8WeH9i2Dd3oTr/WSWT2p+cssnuf1kl096+eRXDq2fJ8X95Lg8XSUS1NawuVRXgvkmWC/Ef2ZeCbVqfvN2m/eD"
    "95cii4Dr4fB4m2jHajel8uM82QLEPJTufJWuYWae3+77AhmnJu8C/6wNXN6gatTsNjbQnJBkpwx3qBuKstWeg244S7eXoS/vILF5"
    "LvlPJ2RRah9iKLfjwDdL/cuBiejebSTAXQSq8foZ0yBW2PjHjYNMPKQ869Jb02/Pv42RvLtVqSn4qbOsLR6OsyxulsndZXOzjG6W"
    "1S3vsruvUqDlKK3pUptZehMPEPi+0C2JsQKqbkGMrd+OKTA16NLx0KM+3Q63lYwElx/XZ7pQEz6Tsf7beh0x/3bo+HnnCCiZ6oPT"
    "DL/SvZfwGpkNQG1Wxx2RvEN1tsFUWhPH9PCINb09Zyi9o0bzHVXKKNOOOiXAM4GeJ+BzHgDQBIK+joxHlIlimTi23ollmWi2E8/O"
    "RLR5JKo5cS0T2XZiWya6OfEtE+EyMe6VKDc+iXQ7sW4c6u02v9KGbzRUJ+51Q4u6PUGZ4NftCerTau9Pd4JiV8Ixj9/xJ23HY3Zc"
    "zjculj4ehio1q5fbHqT15VEah8YBWVpfEKbrDWlKaFNCnBLqtCFPCX1aX1CohETFF0TK5zk9WNuTNb88W/H2dKXHa3u+cpwux+1y"
    "HM8+1PSlbp9q+lZPH6vBevS3uv9V5crzflkNu6r2blV7udi+1I5ibYc6QfGTCMkx1kXcHZ17HCt97l4cAw3rc/fiWCjmz59gzbNL"
    "bVTaQHtVtzW2iuJMXB/OoqViTdz+slOPiuWa1Y5COJmo0+rlJ1GArtjUPtIkVVIoSBt2rSdBfJYrL00tObWeXr60zb/fpbrPS5iA"
    "VT6yNHFp2xcKJKlgkmZipDfFE/Fv0xk+04k+zFByzVPNw79WIxE/gv7/kf7324aGX6VBjhS6VfPtodEvMMhVquQnXWovdc+2mnV4"
    "urppu1QzHjURq2s+VtZkVN6ytLKmovTy9OtoN9ZipN7laAcL5eBn3W4xztstayHbLKAjC7O0W1WIp7pgj3R6OVl4wyELaWG5GKm2"
    "H0VWxajl0IvlbaRinaNMDG5r4Rr70bKt21L4NhXtsuo4w7ebCPkhIsI6rMqLpsJOax+FFOZuhXy4HvbHTHh+D46rKYQTtnRzPrTp"
    "vSxs+f5M1/Nc+PEqWreGVc/Z4ce18GOXllOZGTzOhR/rUDYHz4lq32rDTmtrtrTpPFLjaOf8bh2erjJDeL7W8lPXg/Or1yteT++5"
    "Ue5jfi5/eztW3Kyq3lw4f6pAklTsW/YLqt5c2F+WyhCR33TrTYv9DFwm6iVl2SJzlm6V9pKqIBVS1ago51OUisftglN1q1obt3N7"
    "+7cKRZG/xFS1ov7O8kkqhai2fw+XaqByP5gaV/Q7RRkl8pGrfr+cXvnmiECydFibVRRGtrc2a3h+Y0CbbbwPUf190/ypqVTBxlJs"
    "VfclrDeU2teYQjjElyKHSql9VBwvtf68eXvt4FMlryr5VcmzMt8qeVebf5U8rORj+bwlP2vztJKvlbyt5G8lj8t8ruR1bX6XeV7J"
    "9zLvK/lfmweWfLBLkYaK++fzz6zielHVD+sVVjG/67qt6rfS8ejg+17leyrm63dQpwoK1KmRuTr1e5Uu67N/U+MwXC5u67R6/eb1"
    "2tLybeh72tT3Yv7S/U3tnP+sTz9M6Liht/xS5MVBa7FqPq8HNKzdysfX1Pw/1/5+n/6MCn1yAcJxd/MTyeAIOD1fTxoRPxmC4gp/"
    "v0//ebrZ02vwo7zx9/ONT0d6puAz/ImyOE9X4C+DnwwawlvxrND5Wf+xXNk//rr4Ofy5nu95rg+Gn+h9fvYS1feZG38xB/+mOxge"
    "WFoTZQMdkpuCSr4QWU0ry99C4GWEVRHCQ3nOOg2KjcbEGqyz+/xL4kQ4ONGiFfH5P0jf5vPTQUIQHVbP+nQkNuvTM7oc5dVOrNq7"
    "NRggrEFMbw3GBfkNzzZDm4YVZXAH8e3P/whKk33UrlKaT5/bIAoCjX+sioMZCBSidAdWeU4SGE90XF48kufngkK1XOtiEPWi3eXi"
    "tpeWL1h+McS4eM0XI5xL6OEpY01ygmm7GaIID7lKh0vSVJ6ALseZjZv9+sxDkWLHgo081qYZ/5zCHi8adXg6np8kBw3o2aFv9LlZ"
    "YnrldAWZuQwKISOik5+Nn6CMsNPSZdrpZ+08enw+e9gQTUbX7djb567WGVju7JuD/XQw0jrYQ2HuwFgd48xD0WYGm2k3xpJgyWF6"
    "p+VGFp3OgHTQOvQ8pKAaACsBPN1kcd/82X7k+hnhKc/drdNm0+mW6QxXd9ppOgtUw0iE0iTo8IO1nMdS+WuWcJ4y0svI8o+YiT3a"
    "m6O/ORq8R4c9Wpyjx3s0eXyNNpdDj9HpPVqdo9f1PbpdlMDC5SO0vZga1Y+l74M5309vLNxJ1VOctGv/t07FIboLkGJ0nqNtl+IM"
    "3fGM7oKl3QU4qd7PEY4/eDTeo6aKl5SfVxyn319xivWJY+y4RsY5Mu6RcZBx6DziJvW4Liw7ifRcPjcrXYxlEMNlFflc67Huppgc"
    "l+8um9hVzlDLqWIdyytyO4rVqd1ZjpDTI6z+HnP2WDQJ2qtVUdDoHnPvy+3lsXkvN7q1eSw+vsbqFduUqnyMVDFOTV9WbEexSrVv"
    "jf2jXA31+Zc0FAXmfDzvDicKcf7U/gzvz/B+4nmXNAYclxONyNbx8eDlnYryPUVqRo6mT61H7RxwCw+A8XxBQ2gankesT218j5E6"
    "4ckDbpw+Luu0dqvXH14fxx1O2Ipw24lcIQoCy2n27C8qd8nzSXW5Tr/X8Lw3pXFLQ+UyqS6wagYm54e3E8v9dLi/kWIEsw6IgVPv"
    "/HCEMTo7REi+hqOveCWHE9sE4wuv8YgOT0eRpzIZOB/R5qkexfVhPxvKLGC0FlFy9zBGZ7mcfgFcnrq8PXEqrqm0ZO3Hcru73bT/"
    "pPddjgqLPK1osWlKPC4NirDN4/Vx98vkRNmn1G6iLhWvX2R8Q4YI9w8EximCrzToodP55Hll+jRRVbeqqaO46PNHI9wqZyHZmMa0"
    "kfOW+Tf6o5x/JBGHtSS0Fgf915Hz4wHN5YHYrTl9uO2Ix2pej0O/u4K34v7SZg3aixqp6jZjXErmZYIotVtVcnKauzHXZXVujJON"
    "p5ONpYpdScuhxbahW4mu2P7090+xd6RhbT/brrbtRof9qK7DntS+7Eu2M6W9adud0v6Udijbo9IutSue8/x5ED2GeXbDmVyObsXU"
    "4G2YeRF2J2NokTyEJdNFLNmKpItDhhgUVbu7XdVG8eKl5Enp4FCjgBCiYmBIEjmC0ovTyX1YYfCDcVJLiYIxlQGH/ZMOkSGmsgtx"
    "PBuLlVinjXlK7FP/wkIJE5XYqBdGyoxkZrgVZ8IBO4XgG45nKKtK080xLOYaAm7RNTgtdeYccFfU5emXvg/nl0G6Iq4hDAs2s6BY"
    "GwaTibkK465QFDgUGFI7+YfJQzz5iPPI1MvMvTj0OjL9MvMvMwHnoeXgM16evnTeqPPH/QxDqj6xMGPQRdTdDnXApgvG9pSfTTrU"
    "IdkRi3QomqD1uF126cTjGZeX+LwXTm99cHuJ39s4PiMcE+mIOt1VcQri/ppRkNgjqghn3PPmS9V86ZriAyKZnUSzdhDPTEArIqix"
    "61ShQ1AXmsttvazLOqzdKufeR+WfkjrGiS5WFE8JDH03I0OJOPEVKb5CxWe2Fp8Ha5Gf+LOc4jbajow39IXdOk+MlbJt39iOkY4j"
    "Zpox1IypZoyV15NXtn917uzs7vz5Y2hir+lH0nWFGLkSgY1HGr5pEcti+CfOjCNKulL3+4ruK5xXPHtA9ojsIfcBA10HJDShoQkR"
    "TahoQkYTOpoQ0oSSnpDS+4CYJtSU5+XvP1ZbOWg="
)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>세계 뉴스 · 현지어 학습</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--bd:#ddd;--ac:#1a4d8f;--card:#f7f7f9}
@media(prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#eee;--mut:#9aa;--bd:#333;--ac:#7fb0ff;--card:#1f2229}}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:14px 20px;border-bottom:1px solid var(--bd)}
header h1{margin:0;font-size:18px} header small{color:var(--mut)}
.nav button,.chip{padding:7px 14px;border:1px solid var(--bd);background:var(--card);color:var(--fg);border-radius:20px;cursor:pointer;font-size:14px}
.nav button.on,.chip.on{background:var(--ac);color:#fff;border-color:var(--ac)}
.wrap{max-width:900px;margin:0 auto;padding:0 20px 60px}
#map{position:relative;border:1px solid var(--bd);border-radius:10px;margin:14px 0;background:#cfe3f3;overflow:hidden;touch-action:none}
@media(prefers-color-scheme:dark){#map{background:#0f2536}}
#map svg{display:block;width:100%;height:auto;cursor:grab}
.land{fill:#f1ead8;stroke:#b9ad8c;stroke-width:.4}
@media(prefers-color-scheme:dark){.land{fill:#2c3440;stroke:#4a5566}}
.zb{position:absolute;right:8px;top:8px;display:flex;flex-direction:column;gap:4px}
.zb button{width:30px;height:30px;border:1px solid var(--bd);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer;font-size:16px}
.pinc{cursor:pointer}.pinc circle{fill:var(--ac);stroke:#fff;stroke-width:1.5}.pinc.sel circle{fill:#d9480f}
.pinc text{fill:#fff;font-size:11px;font-weight:700;text-anchor:middle;dominant-baseline:central;pointer-events:none}
.row{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.pin{width:30px;height:30px;border-radius:50%;background:var(--ac);color:#fff;font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)}
.pin.sel{background:#d9480f}
h2{font-size:15px;color:var(--ac);margin:20px 0 8px}
article{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.meta{font-size:12px;color:var(--mut);margin-bottom:4px}
.t{font-weight:600;color:var(--fg);text-decoration:none;font-size:16px;line-height:1.4}.t:hover{color:var(--ac)}
.s{margin:6px 0;color:var(--mut);font-size:14px;line-height:1.5}
.kobtn{background:none;border:1px solid var(--bd);color:var(--ac);border-radius:6px;padding:3px 10px;cursor:pointer;font-size:12px}
.ko{display:none;margin-top:8px;font-size:14px;line-height:1.5}.ko.show{display:block}
.hint{font-size:13px;color:var(--mut);margin:6px 0}
#pop{position:absolute;display:none;z-index:9999;background:#d9480f;color:#fff;border:0;border-radius:6px;padding:6px 10px;font-size:13px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.35)}
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#222;color:#fff;padding:8px 16px;border-radius:20px;font-size:13px;display:none;z-index:99999}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{border-bottom:1px solid var(--bd);padding:8px 6px;text-align:left;vertical-align:top}
td input{width:100%;padding:5px;border:1px solid var(--bd);border-radius:5px;background:var(--bg);color:var(--fg)}
.w{font-weight:700;font-size:16px}.ctx{font-size:12px;color:var(--mut)}
.act{padding:8px 14px;border:0;background:var(--ac);color:#fff;border-radius:6px;cursor:pointer;font-size:13px}
.del{background:none;border:0;color:#c33;cursor:pointer;font-size:16px}
a{color:var(--ac)}
.hide{display:none}
</style></head><body>
<header>
  <div><h1>세계 뉴스 · 현지어 학습</h1><small>업데이트: __NOW__</small></div>
  <div class="nav"><button id="nNews" class="on">뉴스 지도</button> <button id="nVocab">단어장 (<span id="vc">0</span>)</button></div>
</header>

<div class="wrap" id="vNews">
  <div id="map"></div>
  <div class="hint">핀을 누르면 그 나라 기사만 나와. 휠/+−로 확대, 드래그로 이동. 기사 속 단어를 드래그하면 "단어장에 저장" 버튼이 떠.</div>
  <div class="row" id="langChips"></div>
  <div class="row" id="countryChips"></div>
  <div id="list"></div>
</div>

<div class="wrap hide" id="vVocab">
  <div class="row" style="margin-top:14px">
    <button class="act" id="csv">CSV로 내보내기</button>
    <button class="act" id="clear" style="background:#c33">전체 삭제</button>
  </div>
  <div id="vocabBox"></div>
</div>

<button id="pop">📌 단어장에 저장</button>
<div id="toast"></div>

<script>
const DATA = __DATA__;
const ARTICLES = DATA.articles, COUNTRIES = DATA.countries, DICT = DATA.dict;
const $ = s => document.querySelector(s);
function el(tag, cls, text){ const e=document.createElement(tag); if(cls) e.className=cls; if(text!==undefined) e.textContent=text; return e; }
function toast(m){ const t=$('#toast'); t.textContent=m; t.style.display='block'; clearTimeout(toast.h); toast.h=setTimeout(()=>t.style.display='none',1800); }

/* ---------- 단어장 (브라우저 localStorage) ---------- */
let vocab = [];
try { vocab = JSON.parse(localStorage.getItem('vocab_v1') || '[]'); } catch(e) {}
function saveVocab(){ try{ localStorage.setItem('vocab_v1', JSON.stringify(vocab)); }catch(e){} $('#vc').textContent = vocab.length; }

function renderVocab(){
  const box = $('#vocabBox'); box.textContent='';
  if(!vocab.length){ box.appendChild(el('p','hint','아직 저장한 단어가 없어. 기사에서 단어를 드래그해봐.')); return; }
  const tb = el('table'); const hr = el('tr');
  ['단어','언어','내 메모(뜻)','문맥',''].forEach(h=>hr.appendChild(el('th',null,h)));
  tb.appendChild(hr);
  vocab.forEach((v,i)=>{
    const tr = el('tr');
    const c1 = el('td'); c1.appendChild(el('div','w',v.word));
    const a = el('a',null,'사전'); a.href = DICT[v.lang]+encodeURIComponent(v.word); a.target='_blank'; a.rel='noopener';
    c1.appendChild(a); tr.appendChild(c1);
    tr.appendChild(el('td',null,v.lang));
    const c3 = el('td'); const inp = el('input'); inp.value = v.memo||''; inp.placeholder='뜻 입력';
    inp.onchange = ()=>{ v.memo = inp.value; saveVocab(); };
    c3.appendChild(inp); tr.appendChild(c3);
    const c4 = el('td'); const l = el('a','ctx',v.context); l.href=v.link; l.target='_blank'; l.rel='noopener';
    c4.appendChild(l); c4.appendChild(el('div','ctx',v.date)); tr.appendChild(c4);
    const c5 = el('td'); const d = el('button','del','✕'); d.title='삭제';
    d.onclick = ()=>{ vocab.splice(i,1); saveVocab(); renderVocab(); };
    c5.appendChild(d); tr.appendChild(c5);
    tb.appendChild(tr);
  });
  box.appendChild(tb);
}
$('#csv').onclick = ()=>{
  const rows = [['단어','언어','메모','문맥','링크','저장일']].concat(vocab.map(v=>[v.word,v.lang,v.memo||'',v.context,v.link,v.date]));
  const csv = '\ufeff' + rows.map(r=>r.map(c=>'"'+String(c).replace(/"/g,'""')+'"').join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  a.download = 'vocab.csv'; a.click();
};
$('#clear').onclick = ()=>{ if(vocab.length && confirm('단어장을 전부 지울까?')){ vocab=[]; saveVocab(); renderVocab(); } };

/* ---------- 선택 → 저장 ---------- */
const pop = $('#pop'); let pending = null;
function checkSel(){
  setTimeout(()=>{
    const sel = window.getSelection(); const w = sel.toString().trim().replace(/\s+/g,' ');
    if(!w || w.length>60 || !sel.rangeCount){ pop.style.display='none'; return; }
    const n = sel.anchorNode && (sel.anchorNode.nodeType===1 ? sel.anchorNode : sel.anchorNode.parentElement);
    const art = n && n.closest('article[data-i]');
    if(!art){ pop.style.display='none'; return; }
    const a = ARTICLES[+art.dataset.i];
    pending = {word:w, lang:a.lang, context:a.title, link:a.link, memo:'', date:new Date().toISOString().slice(0,10)};
    const r = sel.getRangeAt(0).getBoundingClientRect();
    pop.style.left = Math.max(8, r.left+window.scrollX)+'px';
    pop.style.top = (r.bottom+window.scrollY+6)+'px';
    pop.style.display='block';
  },0);
}
document.addEventListener('mouseup', e=>{ if(e.target!==pop) checkSel(); });
document.addEventListener('touchend', e=>{ if(e.target!==pop) checkSel(); });
pop.addEventListener('mousedown', e=>e.preventDefault());
pop.onclick = ()=>{
  if(!pending) return;
  if(vocab.some(v=>v.word===pending.word && v.lang===pending.lang)) toast('이미 저장된 단어야');
  else { vocab.unshift(pending); saveVocab(); toast('저장: '+pending.word); }
  pop.style.display='none'; window.getSelection().removeAllRanges(); pending=null;
};

/* ---------- 뉴스 + 지도 ---------- */
let selLang = null, selCountry = null;
const LANGS = [...new Set(ARTICLES.map(a=>a.lang))];

function filtered(ignoreCountry){
  return ARTICLES.map((a,i)=>({a,i})).filter(({a})=>
    (!selLang || a.lang===selLang) && (ignoreCountry || !selCountry || a.country===selCountry));
}
function renderChips(){
  const lc = $('#langChips'); lc.textContent='';
  [null].concat(LANGS).forEach(l=>{
    const b = el('button','chip'+(selLang===l?' on':''), l||'전체 언어');
    b.onclick = ()=>{ selLang=l; selCountry=null; refresh(); };
    lc.appendChild(b);
  });
  const cc = $('#countryChips'); cc.textContent='';
  const b0 = el('button','chip'+(!selCountry?' on':''),'전체 나라');
  b0.onclick = ()=>{ selCountry=null; refresh(); }; cc.appendChild(b0);
  const counts = {};
  filtered(true).forEach(({a})=>counts[a.country]=(counts[a.country]||0)+1);
  Object.keys(counts).forEach(c=>{
    const b = el('button','chip'+(selCountry===c?' on':''), c+' '+counts[c]);
    b.onclick = ()=>{ selCountry=c; refresh(); }; cc.appendChild(b);
  });
}
const NS='http://www.w3.org/2000/svg', W=1080, H=540;
let vb={x:0,y:0,w:W,h:H}, svg=null, pinLayer=null;
function setVB(){ svg.setAttribute('viewBox',vb.x+' '+vb.y+' '+vb.w+' '+vb.h); const k=vb.w/W; pinLayer.querySelectorAll('.pinc').forEach(g=>{ g.setAttribute('transform','translate('+g.dataset.x+','+g.dataset.y+') scale('+k+')'); }); }
function zoom(f,cx,cy){
  const nw=Math.min(W,Math.max(W/12,vb.w*f)), nh=nw/2;
  cx=cx===undefined?vb.x+vb.w/2:cx; cy=cy===undefined?vb.y+vb.h/2:cy;
  vb.x=Math.min(W-nw,Math.max(0,cx-(cx-vb.x)*(nw/vb.w))); vb.y=Math.min(H-nh,Math.max(0,cy-(cy-vb.y)*(nh/vb.h))); vb.w=nw; vb.h=nh; setVB();
}
function initMap(){
  const box=$('#map'); box.textContent='';
  svg=document.createElementNS(NS,'svg'); svg.setAttribute('viewBox','0 0 '+W+' '+H);
  const land=document.createElementNS(NS,'path'); land.setAttribute('class','land'); land.setAttribute('d',DATA.world); svg.appendChild(land);
  pinLayer=document.createElementNS(NS,'g'); svg.appendChild(pinLayer); box.appendChild(svg);
  const zb=el('div','zb');
  [['+',()=>zoom(.6)],['−',()=>zoom(1/.6)],['⟲',()=>{vb={x:0,y:0,w:W,h:H};setVB();}]].forEach(([t,f])=>{const b=el('button',null,t);b.onclick=f;zb.appendChild(b);});
  box.appendChild(zb);
  const pt=e=>{const r=svg.getBoundingClientRect();return {x:vb.x+(e.clientX-r.left)/r.width*vb.w,y:vb.y+(e.clientY-r.top)/r.height*vb.h,k:vb.w/r.width};};
  svg.addEventListener('wheel',e=>{e.preventDefault();const p=pt(e);zoom(e.deltaY<0?.8:1.25,p.x,p.y);},{passive:false});
  let drag=null;
  svg.addEventListener('pointerdown',e=>{ if(e.target.closest('.pinc')) return; drag={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y}; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener('pointermove',e=>{ if(!drag) return; const r=svg.getBoundingClientRect(); const k=vb.w/r.width;
    vb.x=Math.min(W-vb.w,Math.max(0,drag.vx-(e.clientX-drag.x)*k)); vb.y=Math.min(H-vb.h,Math.max(0,drag.vy-(e.clientY-drag.y)*k)); setVB(); });
  svg.addEventListener('pointerup',()=>drag=null);
}
function renderMap(){
  if(!svg) initMap();
  pinLayer.textContent='';
  const counts = {};
  filtered(true).forEach(({a})=>counts[a.country]=(counts[a.country]||0)+1);
  Object.keys(counts).forEach(c=>{
    const p = COUNTRIES[c];
    const x=(p[1]+180)*3, y=(90-p[0])*3;
    const g=document.createElementNS(NS,'g'); g.setAttribute('class','pinc'+(selCountry===c?' sel':'')); g.dataset.x=x; g.dataset.y=y;
    const ci=document.createElementNS(NS,'circle'); ci.setAttribute('r',13); g.appendChild(ci);
    const tx=document.createElementNS(NS,'text'); tx.textContent=counts[c]; g.appendChild(tx);
    const ti=document.createElementNS(NS,'title'); ti.textContent=c; g.appendChild(ti);
    g.addEventListener('click',()=>{ selCountry=(selCountry===c?null:c); refresh(); });
    pinLayer.appendChild(g);
  });
  setVB();
}
function renderList(){
  const box = $('#list'); box.textContent='';
  const items = filtered(false);
  if(!items.length){ box.appendChild(el('p','hint','기사가 없어.')); return; }
  let lastSrc = null;
  items.forEach(({a,i})=>{
    if(a.source!==lastSrc){ box.appendChild(el('h2',null,a.source+' · '+a.country+' · '+a.lang)); lastSrc=a.source; }
    const art = el('article'); art.dataset.i = i;
    const t = el('a','t',a.title); t.href=a.link; t.target='_blank'; t.rel='noopener';
    art.appendChild(t);
    if(a.summary) art.appendChild(el('p','s',a.summary));
    if(a.date) art.appendChild(el('div','meta',a.date));
    if(a.ko_title){
      const kb = el('button','kobtn','한국어 보기'); const k = el('div','ko');
      k.appendChild(el('b',null,a.ko_title)); k.appendChild(document.createElement('br')); k.appendChild(document.createTextNode(a.ko_summary||''));
      kb.onclick = ()=>k.classList.toggle('show');
      art.appendChild(kb); art.appendChild(k);
    }
    box.appendChild(art);
  });
}
function refresh(){ renderChips(); renderMap(); renderList(); }

$('#nNews').onclick = ()=>{ $('#vNews').classList.remove('hide'); $('#vVocab').classList.add('hide'); $('#nNews').classList.add('on'); $('#nVocab').classList.remove('on'); };
$('#nVocab').onclick = ()=>{ $('#vVocab').classList.remove('hide'); $('#vNews').classList.add('hide'); $('#nVocab').classList.add('on'); $('#nNews').classList.remove('on'); renderVocab(); };

saveVocab(); refresh();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--translate", action="store_true", help="한국어 번역 추가")
    ap.add_argument("--per-feed", type=int, default=8, help="언론사당 기사 수")
    ap.add_argument("--no-open", action="store_true", help="브라우저 자동 열기 끄기")
    args = ap.parse_args()

    tr = make_translator() if args.translate else None

    articles, countries = [], {}
    for name, url, lang, country, lat, lng in SOURCES:
        print(f"[{lang}] {name}")
        countries[country] = [lat, lng]
        code = LANG_INFO[lang][0]
        for it in fetch_feed(url, args.per_feed):
            it.update(source=name, lang=lang, country=country)
            if tr:
                it["ko_title"] = tr(it["title"], code)
                it["ko_summary"] = tr(it["summary"], code)
            articles.append(it)

    payload = {
        "articles": articles,
        "countries": countries,
        "dict": {k: v[1] for k, v in LANG_INFO.items()},
        "world": zlib.decompress(base64.b64decode("".join(WORLD_B64))).decode().replace("\n", ""),
    }
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = (TEMPLATE
            .replace("__DATA__", data_json)
            .replace("__NOW__", datetime.now().strftime("%Y-%m-%d %H:%M")))

    out = Path(__file__).with_name("world_news.html")
    out.write_text(page, encoding="utf-8")
    print(f"\n완료: {out}  (기사 {len(articles)}개)")
    if not args.no_open:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
