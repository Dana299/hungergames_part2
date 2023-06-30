from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass
class URLStructure:
    protocol: str
    domain: str
    domain_zone: str
    path: str
    query_params: dict


def parse_url(url: str) -> URLStructure:
    """Exctracts protocol, domain, domain zone, path and query params from a given url."""
    parsed_url = urlparse(url)

    domain = parsed_url.netloc
    domain_zone = domain.split(".")[-1]
    path = parsed_url.path
    protocol = parsed_url.scheme
    query_params = parse_qs(parsed_url.query)

    return URLStructure(
        protocol=protocol,
        domain=domain,
        domain_zone=domain_zone,
        path=path,
        query_params=query_params,
    )
