import re
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ddgs import DDGS


socket.setdefaulttimeout(10)


class ReadableTextParser(HTMLParser):
    """Extract readable text from HTML while skipping common boilerplate."""

    SKIP_TAGS = {
        "script", "style", "noscript", "svg", "nav",
        "header", "footer", "aside", "form", "iframe",
    }

    BLOCK_TAGS = {
        "p", "div", "article", "section", "main",
        "h1", "h2", "h3", "h4", "li", "tr", "br",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
        elif self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def get_text(self):
        text = " ".join(self.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def fetch_page_text(url, timeout=10, max_chars=12000):
    """
    Retrieve readable text from a webpage.
    Return an empty string if the page cannot be fetched.
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return ""

        if not parsed.hostname:
            return ""

        # Avoid fetching non-web resources.
        if parsed.path.lower().endswith(
            (".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".mp4")
        ):
            return ""

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()

            if "html" not in content_type and "text/plain" not in content_type:
                return ""

            raw = response.read(2_000_000)

            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")

        parser = ReadableTextParser()
        parser.feed(html)
        text = parser.get_text()

        return text[:max_chars]

    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return ""
    except Exception:
        return ""


def search_web(query, max_results=5):
    """
    Search the web and enrich each result with readable webpage text.

    Return structure remains compatible with existing agents:
    [{"title": ..., "url": ..., "content": ...}]
    """
    results = []
    seen_urls = set()

    try:
        with DDGS() as ddgs:
            search_results = list(
                ddgs.text(query, max_results=max_results)
            )
    except Exception as exc:
        print(f"[SEARCH WARNING] Search failed: {exc}")
        return results

    for item in search_results:
        title = str(item.get("title") or "").strip()
        url = str(item.get("href") or item.get("url") or "").strip()

        if not url or url in seen_urls:
            continue

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue

        seen_urls.add(url)

        snippet = str(
            item.get("body")
            or item.get("snippet")
            or item.get("content")
            or ""
        ).strip()

        page_text = fetch_page_text(url)

        if page_text:
            content = page_text
            retrieval_status = "full_page"
        else:
            content = snippet
            retrieval_status = "search_snippet_only"

        results.append(
            {
                "title": title,
                "url": url,
                "content": content,
                "snippet": snippet,
                "retrieval_status": retrieval_status,
            }
        )

        status_label = (
            "full page" if page_text else "snippet fallback"
        )
        print(f"[FETCH] {status_label}: {title[:65]}")

    return results


if __name__ == "__main__":
    query = input("Enter a search query: ").strip()

    for result in search_web(query, max_results=5):
        print("\n" + "=" * 70)
        print("TITLE:", result["title"])
        print("URL:", result["url"])
        print("RETRIEVAL:", result["retrieval_status"])
        print("CONTENT:", result["content"][:1000])