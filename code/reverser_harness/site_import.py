"""Fetch a user supplied public challenge page and its selected attachments."""

import http.client
import ipaddress
import re
import socket
import ssl
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from .security import safe_filename, validate_http_url


PAGE_LIMIT = 2 * 1024 * 1024
FILE_LIMIT = 128 * 1024 * 1024
FILE_SUFFIXES = {".zip", ".7z", ".rar", ".tar", ".gz", ".xz", ".bz2", ".bin",
                 ".elf", ".exe", ".dll", ".so", ".apk", ".jar", ".wasm", ".py",
                 ".c", ".cpp", ".h", ".txt", ".dat", ".pcap", ".pdf"}
DOWNLOAD_TEXT = re.compile(r"download|attachment|첨부|다운로드|파일|바이너리|source", re.I)


def _public_address(host: str, port: int) -> str:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("문제 사이트 주소를 찾을 수 없습니다.") from exc
    for _family, _type, _proto, _canon, sockaddr in addresses:
        address = ipaddress.ip_address(sockaddr[0])
        if address.is_global:
            return str(address)
    raise ValueError("공개 인터넷 주소의 문제 사이트만 가져올 수 있습니다.")


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str) -> None:
        super().__init__(host, port, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), timeout=self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _open_public(url: str) -> tuple[http.client.HTTPResponse, http.client.HTTPConnection, str]:
    for _ in range(5):
        if len(url) > 4096:
            raise ValueError("문제 사이트 주소가 너무 깁니다.")
        validate_http_url(url)
        parsed = urlsplit(url)
        try:
            host = (parsed.hostname or "").encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("문제 사이트 주소가 올바르지 않습니다.") from exc
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError("문제 사이트 포트가 올바르지 않습니다.")
        address = _public_address(host, port)
        connection = (_PinnedHTTPS(host, port, address) if parsed.scheme == "https"
                      else http.client.HTTPConnection(address, port, timeout=12))
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        hostname = host if port == (443 if parsed.scheme == "https" else 80) else f"{host}:{port}"
        try:
            connection.request("GET", path, headers={"Host": hostname,
                "User-Agent": "Reverser-CTF-Importer/0.1", "Accept": "text/html,*/*",
                "Accept-Encoding": "identity"})
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            connection.close()
            raise ValueError("문제 사이트에 연결하지 못했습니다.") from exc
        if response.status in {301, 302, 303, 307, 308}:
            target = response.getheader("Location")
            connection.close()
            if not target:
                raise ValueError("문제 사이트의 이동 주소가 없습니다.")
            url = urljoin(url, target)
            continue
        if response.status in {401, 403}:
            connection.close()
            raise ValueError("문제 사이트에 로그인이 필요하거나 접근이 거부되었습니다.")
        if response.status != 200:
            connection.close()
            raise ValueError(f"문제 사이트가 HTTP {response.status}을 반환했습니다.")
        return response, connection, url
    raise ValueError("문제 사이트 이동이 너무 많습니다.")


def _read_limited(response: http.client.HTTPResponse, limit: int) -> bytes:
    length = response.getheader("Content-Length")
    if length and length.isdigit() and int(length) > limit:
        raise ValueError("문제 페이지가 너무 큽니다.")
    data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("문제 페이지가 너무 큽니다.")
    return data


def _clean_text(parts: list[str]) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parts).splitlines()]
    return "\n".join(line for line in lines if line)


class _ChallengePage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.body = 0
        self.main = 0
        self.title = 0
        self.h1 = 0
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.body_parts: list[str] = []
        self.main_parts: list[str] = []
        self.meta_title = ""
        self.meta_description = ""
        self.base_href = ""
        self.links: list[tuple[str, str, str, bool]] = []
        self.anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "svg", "nav", "footer", "aside"}:
            self.skip += 1
        if self.skip:
            return
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key == "og:title": self.meta_title = values.get("content") or ""
            if key in {"description", "og:description"}: self.meta_description = values.get("content") or ""
        if tag == "base" and values.get("href") and not self.base_href:
            self.base_href = values["href"] or ""
        if tag == "body": self.body += 1
        if tag in {"main", "article"}: self.main += 1
        if tag == "title": self.title += 1
        if tag == "h1": self.h1 += 1
        if tag == "a": self.anchor = {"href": values.get("href") or "", "download": values.get("download") or "",
                                      "has_download": "1" if "download" in values else ""}
        if tag in {"p", "div", "section", "h1", "h2", "h3", "li", "br", "pre"}:
            self.body_parts.append("\n")
            if self.main: self.main_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "nav", "footer", "aside"} and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a" and self.anchor:
            self.links.append((self.anchor["href"], self.anchor.get("text", ""),
                               self.anchor["download"], bool(self.anchor["has_download"])))
            self.anchor = None
        if tag == "h1": self.h1 = max(0, self.h1 - 1)
        if tag == "title": self.title = max(0, self.title - 1)
        if tag in {"main", "article"}: self.main = max(0, self.main - 1)
        if tag == "body": self.body = max(0, self.body - 1)
        if tag in {"p", "div", "section", "h1", "h2", "h3", "li", "pre"}:
            self.body_parts.append("\n")
            if self.main: self.main_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.title: self.title_parts.append(data)
        if self.h1: self.h1_parts.append(data)
        if self.anchor is not None: self.anchor["text"] = self.anchor.get("text", "") + data
        if self.body:
            self.body_parts.append(data)
            if self.main: self.main_parts.append(data)


def preview_site(url: str) -> dict[str, object]:
    response, connection, final_url = _open_public(url)
    try:
        content_type = (response.getheader("Content-Type") or "").lower()
        pathname = Path(unquote(urlsplit(final_url).path)).name
        if content_type and not any(kind in content_type for kind in ("html", "text/plain", "markdown")):
            name = safe_filename(pathname or "attachment.bin")
            return {"url": final_url, "title": Path(name).stem, "description": "",
                    "files": [{"url": final_url, "name": name}], "note": "파일 URL입니다. 가져올 파일을 선택하세요."}
        payload = _read_limited(response, PAGE_LIMIT)
    finally:
        connection.close()
    charset = re.search(r"charset=([\w.-]+)", content_type)
    encoding = charset.group(1) if charset else "utf-8"
    try:
        text = payload.decode(encoding, errors="replace")
    except LookupError:
        text = payload.decode("utf-8", errors="replace")
    if "html" not in content_type and "<html" not in text[:500].lower():
        title = Path(pathname or "문제").stem
        files = ([{"url": final_url, "name": safe_filename(pathname)}]
                 if Path(pathname).suffix.lower() in FILE_SUFFIXES else [])
        return {"url": final_url, "title": title, "description": text[:20_000], "files": files, "note": ""}
    page = _ChallengePage()
    page.feed(text)
    title = _clean_text(page.h1_parts) or page.meta_title.strip() or _clean_text(page.title_parts)
    title = title[:160] or Path(pathname or "문제").stem
    description = (_clean_text(page.main_parts) or page.meta_description.strip()
                   or _clean_text(page.body_parts))[:20_000]
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = urljoin(final_url, page.base_href) if page.base_href else final_url
    for href, label, download, has_download in page.links:
        target = urljoin(base_url, href)
        try:
            validate_http_url(target)
        except ValueError:
            continue
        suffix = Path(unquote(urlsplit(target).path)).suffix.lower()
        if not (has_download or suffix in FILE_SUFFIXES or DOWNLOAD_TEXT.search(label)):
            continue
        if target in seen or target == final_url:
            continue
        seen.add(target)
        name = safe_filename(download or Path(unquote(urlsplit(target).path)).name or label,
                             f"attachment-{len(files) + 1}.bin")
        files.append({"url": target, "name": name})
        if len(files) == 24:
            break
    login_page = bool(re.search(r"/(login|signin|sign-in)(/|$)", urlsplit(final_url).path, re.I)
                      or re.search(r'<input[^>]+type\s*=\s*["\']?password', text, re.I))
    note = ("로그인 페이지로 이동했습니다. 설명과 파일은 직접 입력해 주세요." if login_page
            else "" if description else "페이지 본문을 찾지 못했습니다. 로그인 또는 자바스크립트가 필요하면 설명을 직접 입력하세요.")
    return {"url": final_url, "title": title, "description": description,
            "files": files, "note": note}


def download_attachment(url: str, destination: Path, limit: int = FILE_LIMIT) -> int:
    response, connection, _final_url = _open_public(url)
    try:
        content_type = (response.getheader("Content-Type") or "").lower()
        disposition = (response.getheader("Content-Disposition") or "").lower()
        if "html" in content_type and "attachment" not in disposition:
            raise ValueError("선택한 파일 링크가 다운로드 대신 웹 페이지를 반환했습니다.")
        length = response.getheader("Content-Length")
        if length and length.isdigit() and int(length) > limit:
            raise ValueError("첨부 파일 총 크기는 128 MiB까지 허용됩니다.")
        total = 0
        with destination.open("wb") as output:
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > limit:
                    raise ValueError("첨부 파일 총 크기는 128 MiB까지 허용됩니다.")
                output.write(chunk)
        return total
    finally:
        connection.close()
