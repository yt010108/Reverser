"""서버 없이 열어 보는 단일 HTML 대시보드."""

from html import escape
from pathlib import Path

from .storage import ChallengeStore


# store.list()를 테이블로 렌더링해 dashboard.html을 생성
def build_dashboard(store: ChallengeStore) -> Path:
    rows = []
    for item in store.list():
        rows.append(
            "<tr>"
            f"<td>{escape(str(item['title']))}</td>"
            f"<td>{escape(str(item['status']))}</td>"
            f"<td>{escape(str(item.get('architecture') or '-'))}</td>"
            f"<td>{len(item.get('flags', []))}</td>"
            f"<td><code>{escape(str(item['challenge_id']))}</code></td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="5">저장된 문제가 없습니다.</td></tr>'
    html = f"""<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CTF Reverse</title>
<style>body{{font:15px system-ui;max-width:1100px;margin:40px auto;padding:0 16px;background:#111;color:#eee}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #333;text-align:left}}code{{color:#8fd}}</style>
<h1>CTF Reverse</h1><p>로컬 읽기 전용 요약</p>
<table><thead><tr><th>문제</th><th>상태</th><th>아키텍처</th><th>플래그 후보</th><th>ID</th></tr></thead><tbody>{body}</tbody></table>
</html>"""
    destination = store.root / "dashboard.html"
    destination.write_text(html, encoding="utf-8", newline="\n")
    return destination
