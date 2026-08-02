"""Ingestion Factory: builds the right BaseIngestionProvider from a state's
config dict, so a State Agent never has to know which platform its state
actually uses -- only its `provider_type`.
"""

from __future__ import annotations

from typing import Any

from .accela_provider import AccelaProvider
from .arcgis_provider import ArcGISProvider
from .base_provider import BaseIngestionProvider
from .carto_provider import CartoProvider
from .ckan_provider import CkanProvider
from .csv_download_provider import CsvDownloadProvider
from .tdlr_tabs_provider import TdlrTabsProvider
from .troy_permits_provider import TroyPermitsProvider
from .energov_provider import EnerGovProvider
from .sam_gov_provider import SamGovProvider
from .socrata_provider import SocrataProvider
from .usaspending_provider import USASpendingProvider


class UnknownProviderType(ValueError):
    pass


def build_provider(state_config: dict[str, Any]) -> BaseIngestionProvider:
    provider_type = state_config.get("provider_type")

    if provider_type == "socrata":
        domain = state_config["endpoint"].split("//", 1)[-1].split("/", 1)[0]
        dataset = state_config["endpoint"].rstrip("/").rsplit("/", 1)[-1].replace(".json", "")
        return SocrataProvider(
            domain=domain,
            dataset=dataset,
            watermark_field=state_config.get("watermark_field", "recordid"),
            hash_fields_list=state_config.get("hash_fields"),
            commercial_where=state_config.get("commercial_where"),
            lookback_days=state_config.get("lookback_days", 30),
            app_token=state_config.get("app_token"),
            date_field=state_config.get("date_field", "processdate"),
            hard_limit=state_config.get("hard_limit", 0),
            feed_id=state_config.get("feed_id"),
            state_code=state_config.get("state_code"),
            county=state_config.get("county"),
            id_field=state_config.get("id_field"),
            name_fields=state_config.get("name_fields"),
            address_fields=state_config.get("address_fields"),
            desc_fields=state_config.get("desc_fields"),
            value_fields=state_config.get("value_fields"),
            city_fields=state_config.get("city_fields"),
            source_url=state_config.get("source_url"),
            join_address_fields=state_config.get("join_address_fields", False),
            default_city=state_config.get("default_city"),
        )

    if provider_type == "ckan":
        return CkanProvider(
            base_url=state_config["endpoint"],
            resource_id=state_config["resource_id"],
            watermark_field=state_config.get("watermark_field", "_id"),
            hash_fields_list=state_config.get("hash_fields"),
            commercial_where=state_config.get("commercial_where"),
            date_field=state_config.get("date_field", "date_entered"),
            lookback_days=state_config.get("lookback_days", 30),
            hard_limit=state_config.get("hard_limit", 0),
            feed_id=state_config.get("feed_id"),
            state_code=state_config.get("state_code"),
            county=state_config.get("county"),
            id_field=state_config.get("id_field"),
            name_fields=state_config.get("name_fields"),
            address_fields=state_config.get("address_fields"),
            desc_fields=state_config.get("desc_fields"),
            value_fields=state_config.get("value_fields"),
            city_fields=state_config.get("city_fields"),
            source_url=state_config.get("source_url"),
        )

    if provider_type == "arcgis":
        # endpoint is the full .../FeatureServer/{layer}/query-style URL or
        # base .../FeatureServer -- accept either.
        endpoint = state_config["endpoint"]
        layer = state_config.get("layer", 0)
        base_url = endpoint
        for suffix in ("/query", f"/{layer}"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]
        return ArcGISProvider(
            base_url=base_url,
            layer=layer,
            out_fields=state_config.get("out_fields", "*"),
            commercial_where=state_config.get("commercial_where"),
            watermark_field=state_config.get("watermark_field", "OBJECTID"),
            hash_fields_list=state_config.get("hash_fields"),
            include_geometry=state_config.get("include_geometry", True),
            date_field=state_config.get("date_field"),
            date_field_is_string=state_config.get("date_field_is_string", False),
            date_literal_style=state_config.get("date_literal_style", "date"),
            lookback_days=state_config.get("lookback_days", 30),
            hard_limit=state_config.get("hard_limit", 0),
            feed_id=state_config.get("feed_id"),
            state_code=state_config.get("state_code"),
            county=state_config.get("county"),
            id_field=state_config.get("id_field"),
            name_fields=state_config.get("name_fields"),
            address_fields=state_config.get("address_fields"),
            desc_fields=state_config.get("desc_fields"),
            value_fields=state_config.get("value_fields"),
            city_fields=state_config.get("city_fields"),
            source_url=state_config.get("source_url"),
        )

    if provider_type == "sam_gov":
        return SamGovProvider(
            state_code=state_config["state_code"],
            naics_codes=state_config.get("naics_codes"),
        )

    if provider_type == "usaspending":
        return USASpendingProvider(
            state_code=state_config["state_code"],
            psc_codes=state_config.get("psc_codes"),
            award_type_codes=state_config.get("award_type_codes"),
            lookback_days=state_config.get("lookback_days", 730),
        )

    if provider_type == "accela":
        return AccelaProvider(
            state_code=state_config["state_code"],
            county=state_config["county"],
            base_url=state_config["endpoint"],
            permit_type_label=state_config.get("permit_type_label", "Building"),
            module=state_config.get("module", "Building"),
            lookback_days=state_config.get("lookback_days", 30),
            max_pages=state_config.get("max_pages", 30),
            start_date_field_id=state_config.get("start_date_field_id"),
            end_date_field_id=state_config.get("end_date_field_id"),
        )

    if provider_type == "energov":
        return EnerGovProvider(
            state_code=state_config["state_code"],
            county=state_config["county"],
            base_url=state_config["endpoint"],
            tenant_id=state_config.get("tenant_id", "1"),
            tenant_name=state_config.get("tenant_name"),
            commercial_keywords=state_config.get("commercial_keywords"),
            date_field=state_config.get("date_field", "IssueDate"),
            lookback_days=state_config.get("lookback_days", 30),
            max_pages=state_config.get("max_pages", 5),
            selfservice_path=state_config.get("selfservice_path", "apps/selfservice"),
        )

    if provider_type == "carto":
        return CartoProvider(
            base_url=state_config["endpoint"],
            table=state_config["table"],
            select_fields=state_config.get("select_fields", "*"),
            where_sql=state_config["where_sql"],
            date_field=state_config["date_field"],
            lookback_days=state_config.get("lookback_days", 30),
            row_limit=state_config.get("row_limit", 5000),
            hash_fields_list=state_config.get("hash_fields"),
            feed_id=state_config.get("feed_id"),
            state_code=state_config.get("state_code"),
            county=state_config.get("county"),
            id_field=state_config.get("id_field"),
            name_fields=state_config.get("name_fields"),
            address_fields=state_config.get("address_fields"),
            desc_fields=state_config.get("desc_fields"),
            value_fields=state_config.get("value_fields"),
            city_fields=state_config.get("city_fields"),
            source_url=state_config.get("source_url"),
        )

    if provider_type == "tdlr_tabs":
        return TdlrTabsProvider(
            state_code=state_config.get("state_code", "TX"),
            county_code=state_config.get("county_code"),
            lookback_days=state_config.get("lookback_days", 30),
            page_size=state_config.get("page_size", 100),
            max_pages=state_config.get("max_pages", 200),
        )

    if provider_type == "troy_permits":
        return TroyPermitsProvider(
            state_code=state_config.get("state_code", "MI"),
            county=state_config.get("county", "Oakland"),
            city=state_config.get("city", "Troy"),
            permit_types=state_config.get("permit_types"),
            lookback_days=state_config.get("lookback_days", 30),
            max_pages=state_config.get("max_pages", 200),
        )

    if provider_type == "csv":
        return CsvDownloadProvider(
            csv_url=state_config["endpoint"],
            date_field=state_config["date_field"],
            filter_field=state_config["filter_field"],
            include_keywords=state_config["include_keywords"],
            exclude_keywords=state_config.get("exclude_keywords"),
            lookback_days=state_config.get("lookback_days", 30),
            hash_fields_list=state_config.get("hash_fields"),
            feed_id=state_config.get("feed_id"),
            state_code=state_config.get("state_code"),
            county=state_config.get("county"),
            id_field=state_config.get("id_field"),
            name_fields=state_config.get("name_fields"),
            address_fields=state_config.get("address_fields"),
            desc_fields=state_config.get("desc_fields"),
            value_fields=state_config.get("value_fields"),
            city_fields=state_config.get("city_fields"),
            source_url=state_config.get("source_url"),
        )

    raise UnknownProviderType(f"Unknown provider_type: {provider_type!r}")
