
from urllib.parse import urlparse
import re


class ValidationAgent:
    GENERIC_NAMES = {
        "fintech", "edtech", "healthtech", "agritech", "cleantech",
        "digital payments", "embedded finance", "merchant lending",
        "financial services", "payment processing", "startups",
        "startup ecosystem", "artificial intelligence",
        "financial technology", "technology company",
        "leading platform", "online platform",
    }

    # These are not startup candidates for a company-ranking report.
    # Sources from these organizations may still be useful as evidence.
    EXCLUDED_NAMES = {
        "analytics insight",
        "tracxn",
        "ibef",
        "reserve bank of india",
        "rbi",
        "securities and exchange board of india",
        "sebi",
        "national payments corporation of india",
        "npci",
        "upi",
        "telecom regulatory authority of india",
        "trai",
        "pradhan mantri jan dhan yojana",
        "ministry of finance",
        "government of india",
        "reuters",
        "bloomberg",
        "yourstory",
        "inc42",
        "entrackr",
        "moneycontrol",
        "economic times",
        "livemint",
        "business standard",
    }

    # These terms identify entities that usually should not be ranked
    # as startups. They are checked against candidate identity fields,
    # not against every article mentioning the candidate.
    EXCLUDED_IDENTITY_TERMS = {
        "government scheme",
        "regulatory authority",
        "regulator",
        "stock exchange",
        "news publication",
        "media company",
        "market research firm",
        "industry association",
        "payment network",
        "payment infrastructure",
        "open payment protocol",
        "government department",
        "ministry",
    }

    TRUSTED_DOMAIN_HINTS = {
        "mca.gov.in",
        "bseindia.com",
        "nseindia.com",
        "sebi.gov.in",
        "rbi.org.in",
        "annualreports.com",
        "reuters.com",
        "bloomberg.com",
        "economictimes.indiatimes.com",
        "livemint.com",
        "moneycontrol.com",
        "business-standard.com",
        "inc42.com",
        "entrackr.com",
        "yourstory.com",
    }

    INDUSTRY_KEYWORDS = {
        "fintech": {
            "fintech", "financial technology", "payments",
            "payment gateway", "payment processing", "lending",
            "digital lending", "banking", "insurance", "insurtech",
            "wealth management", "investment platform", "credit",
            "financial services", "upi payments", "trading platform",
            "neobank", "personal finance", "digital finance",
            "consumer finance", "merchant finance", "microfinance",
            "financial software", "payment solutions",
        },
        "edtech": {
            "edtech", "education technology", "education",
            "learning platform", "online courses", "training",
            "tutoring", "educational technology",
        },
        "healthtech": {
            "healthtech", "healthcare technology", "healthcare",
            "medical technology", "digital health", "telemedicine",
            "hospital", "diagnostics",
        },
        "agritech": {
            "agritech", "agriculture technology", "agriculture",
            "farming", "agricultural technology", "farmers", "crop",
        },
        "cleantech": {
            "cleantech", "clean energy", "renewable energy",
            "sustainability", "electric vehicle", "climate technology",
        },
    }

    INDIA_ALIASES = {
        "india", "indian", "bengaluru", "bangalore", "mumbai",
        "new delhi", "delhi", "gurugram", "gurgaon", "hyderabad",
        "chennai", "pune", "noida", "ahmedabad", "kolkata",
        "jaipur", "kochi",
    }

    def __init__(self, min_sources=1, require_trusted_source=False):
        self.min_sources = max(1, int(min_sources))
        self.require_trusted_source = bool(require_trusted_source)

    @staticmethod
    def normalise(text):
        return re.sub(r"[^a-z0-9]", "", str(text or "").casefold())

    @staticmethod
    def normalise_text(text):
        return re.sub(r"\s+", " ", str(text or "").casefold()).strip()

    @classmethod
    def valid_url(cls, url):
        try:
            parsed = urlparse(str(url or "").strip())
            return (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and "." in parsed.hostname
                and not any(char.isspace() for char in parsed.netloc)
            )
        except (TypeError, ValueError):
            return False

    @classmethod
    def domain(cls, url):
        try:
            return (
                (urlparse(str(url or "")).hostname or "")
                .lower()
                .removeprefix("www.")
            )
        except (TypeError, ValueError):
            return ""

    @classmethod
    def is_trusted_domain(cls, url):
        domain = cls.domain(url)
        return any(
            domain == trusted or domain.endswith("." + trusted)
            for trusted in cls.TRUSTED_DOMAIN_HINTS
        )

    @classmethod
    def name_in_source(cls, name, source):
        title = str(source.get("title", "") or "")
        content = str(source.get("content", "") or "")
        combined = f"{title} {content}"

        name = str(name or "").strip()
        if len(name) < 3:
            return False

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(name)
            + r"(?![a-z0-9])"
        )

        return bool(re.search(pattern, combined, flags=re.IGNORECASE))

    @classmethod
    def is_excluded_identity(cls, candidate):
        name = cls.normalise_text(candidate.get("name", ""))
        normalized_name = cls.normalise(name)

        if name in cls.EXCLUDED_NAMES:
            return True, "Candidate is a publisher, regulator, scheme, or infrastructure entity"

        if normalized_name in {
            cls.normalise(item) for item in cls.EXCLUDED_NAMES
        }:
            return True, "Candidate is a publisher, regulator, scheme, or infrastructure entity"

        identity_text = cls.normalise_text(
            " ".join([
                str(candidate.get("description", "") or ""),
                str(candidate.get("industry", "") or ""),
                str(candidate.get("company_type", "") or ""),
                str(candidate.get("entity_type", "") or ""),
            ])
        )

        # Require an explicit entity-type signal. Do not reject a startup
        # merely because an article mentions a regulator or payment network.
        if any(term in identity_text for term in cls.EXCLUDED_IDENTITY_TERMS):
            return True, "Candidate is identified as non-startup infrastructure or an institution"

        return False, ""

    @classmethod
    def industry_relevant(cls, candidate, industry):
        if not industry:
            return True

        industry_key = str(industry).casefold().strip()
        keywords = cls.INDUSTRY_KEYWORDS.get(
            industry_key,
            {industry_key},
        )

        # Search the candidate's description and source passages that
        # mention the candidate. A company name alone is not enough.
        evidence_parts = [
            str(candidate.get("description", "") or ""),
            str(candidate.get("industry", "") or ""),
            str(candidate.get("business_model", "") or ""),
        ]

        for source in candidate.get("source_evidence", []):
            if isinstance(source, dict) and cls.name_in_source(
                candidate.get("name", ""), source
            ):
                evidence_parts.extend([
                    str(source.get("title", "") or ""),
                    str(source.get("content", "") or ""),
                ])

        evidence_text = cls.normalise_text(" ".join(evidence_parts))

        return any(
            keyword in evidence_text
            for keyword in keywords
        )

    @classmethod
    def geography_relevant(cls, candidate, geography):
        if not geography:
            return True

        geography_key = str(geography).strip().casefold()

        evidence_parts = [
            str(candidate.get("geography", "") or ""),
            str(candidate.get("country", "") or ""),
            str(candidate.get("headquarters", "") or ""),
            str(candidate.get("description", "") or ""),
        ]

        for source in candidate.get("source_evidence", []):
            if isinstance(source, dict) and cls.name_in_source(
                candidate.get("name", ""), source
            ):
                evidence_parts.extend([
                    str(source.get("title", "") or ""),
                    str(source.get("content", "") or ""),
                ])

        evidence_text = cls.normalise_text(" ".join(evidence_parts))

        if geography_key in evidence_text:
            return True

        if geography_key in {"india", "indian"}:
            return any(alias in evidence_text for alias in cls.INDIA_ALIASES)

        # Do not infer a company's geography only from the search query.
        return False

    def validate(self, candidates, industry=None, geography=None):
        accepted = []
        rejected = []
        seen_names = set()

        for candidate in candidates:
            if not isinstance(candidate, dict):
                rejected.append({
                    "name": "",
                    "reason": "Candidate is not a valid object",
                })
                continue

            name = str(candidate.get("name", "") or "").strip()
            normalized_name = self.normalise(name)

            if (
                not name
                or name.casefold() in self.GENERIC_NAMES
                or len(name) > 100
                or len(normalized_name) < 3
            ):
                rejected.append({
                    "name": name,
                    "reason": "Generic or invalid company name",
                })
                continue

            if normalized_name in seen_names:
                rejected.append({
                    "name": name,
                    "reason": "Duplicate company candidate",
                })
                continue

            excluded, exclusion_reason = self.is_excluded_identity(candidate)
            if excluded:
                rejected.append({
                    "name": name,
                    "reason": exclusion_reason,
                })
                continue

            sources = candidate.get("source_evidence", [])
            valid_sources = []
            seen_urls = set()

            for source in sources if isinstance(sources, list) else []:
                if not isinstance(source, dict):
                    continue

                url = str(source.get("url", "") or "").strip()
                if not self.valid_url(url):
                    continue

                if not self.name_in_source(name, source):
                    continue

                normalized_url = url.rstrip("/").casefold()
                if normalized_url in seen_urls:
                    continue

                title = str(source.get("title", "") or "").strip()
                content = str(source.get("content", "") or "").strip()

                if not title and not content:
                    continue

                cleaned_source = dict(source)
                cleaned_source["url"] = url
                cleaned_source["domain"] = self.domain(url)
                cleaned_source["domain_trusted"] = self.is_trusted_domain(url)

                valid_sources.append(cleaned_source)
                seen_urls.add(normalized_url)

            if len(valid_sources) < self.min_sources:
                rejected.append({
                    "name": name,
                    "reason": (
                        "Insufficient traceable sources mentioning "
                        "the company"
                    ),
                })
                continue

            candidate["source_evidence"] = valid_sources

            if self.require_trusted_source and not any(
                source.get("domain_trusted", False)
                for source in valid_sources
            ):
                rejected.append({
                    "name": name,
                    "reason": "No source from the configured trusted-domain list",
                })
                continue

            if industry and not self.industry_relevant(candidate, industry):
                rejected.append({
                    "name": name,
                    "reason": (
                        f"Industry relevance could not be established "
                        f"for {industry}"
                    ),
                })
                continue

            if geography and not self.geography_relevant(candidate, geography):
                rejected.append({
                    "name": name,
                    "reason": (
                        f"Geographic relevance could not be established "
                        f"for {geography}"
                    ),
                })
                continue

            candidate["validation_status"] = "candidate_validated"
            candidate["validated_source_count"] = len(valid_sources)
            candidate["trusted_source_count"] = sum(
                source.get("domain_trusted", False)
                for source in valid_sources
            )

            # Validation means the candidate passed these checks;
            # it does not prove its financial claims are true.
            candidate["validation_confidence"] = (
                "trusted_source_present"
                if candidate["trusted_source_count"] > 0
                else "source_mentions_and_relevance_checked"
            )

            seen_names.add(normalized_name)
            accepted.append(candidate)

        return {
            "accepted": accepted,
            "rejected": rejected,
        }
