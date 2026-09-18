import os
import random


class ProxyRotator:
    """Rotates Decodo datacenter proxies every N requests.

    Expects a text file with one proxy per line in the format:
        host:port:username:password
    Example:
        dc.decodo.com:10001:sp1vndy77g:6gAjk58iimawUIY+g9

    The proxy is returned as a string compatible with curl_cffi:
        https://username:password@host:port
    """

    def __init__(self, proxy_file, min_requests=10, max_requests=20):
        self.proxies = self._load_proxies(proxy_file)
        if not self.proxies:
            raise RuntimeError(f"No proxies loaded from {proxy_file}")
        self.min_requests = min_requests
        self.max_requests = max_requests
        self.current_index = random.randrange(len(self.proxies))
        self.request_count = 0
        self.requests_until_switch = random.randint(min_requests, max_requests)
        print(f"[PROXY] Loaded {len(self.proxies)} proxies. "
              f"First proxy: {self._mask_proxy(self.current())}")

    @staticmethod
    def _load_proxies(path):
        proxies = []
        if not os.path.exists(path):
            raise FileNotFoundError(f"Proxy file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) != 4:
                    print(f"[WARN] Skipping malformed proxy line: {line}")
                    continue
                host, port, username, password = parts
                proxy_url = f"https://{username}:{password}@{host}:{port}"
                proxies.append(proxy_url)
        return proxies

    @staticmethod
    def _mask_proxy(proxy_url):
        """Hide credentials when printing proxy URL."""
        try:
            at = proxy_url.rfind("@")
            if at == -1:
                return proxy_url
            suffix = proxy_url[at + 1:]
            return f"https://***:***@{suffix}"
        except Exception:
            return "***"

    def current(self):
        return self.proxies[self.current_index]

    def assign_proxy(self):
        if self.request_count >= self.requests_until_switch:
            previous = self.current_index
            # avoid picking the same proxy twice in a row
            choices = [i for i in range(len(self.proxies)) if i != previous]
            self.current_index = random.choice(choices) if choices else previous
            self.request_count = 0
            self.requests_until_switch = random.randint(
                self.min_requests, self.max_requests
            )
            print(f"[PROXY] Switched to {self._mask_proxy(self.current())} "
                  f"for next {self.requests_until_switch} requests")

        proxy = self.current()
        self.request_count += 1
        return proxy
