

from typing import Optional
from azure.cosmos import PartitionKey, CosmosClient
from azure.cosmos.container import ContainerProxy
import os

from dataclasses import dataclass, asdict

END_POINT = os.environ["COSMOS_URI"]
PRIMARY_KEY = os.environ["COSMOS_PRIMARY_KEY"]


DB_NAME = "hg-scalper-db"
CONTAINER_NAME = "hg-scalper-container"

QUERY = """
    SELECT * FROM c WHERE c.shop='{}' and c.item_name='{}'
    ORDER BY c.time_stamp"""

_client: CosmosClient = CosmosClient(END_POINT, PRIMARY_KEY)


@dataclass
class ShopRecord:
    id: str
    shop: str
    item_name: str
    url: str
    available: int
    time_stamp: str


def _get_container() -> ContainerProxy:
    db = _client.create_database_if_not_exists(id=DB_NAME)
    return db.create_container_if_not_exists(id=CONTAINER_NAME,
                                             partition_key=PartitionKey(path="/shop")
                                             )


def upsert(shop_record: ShopRecord):
    _get_container().upsert_item(asdict(shop_record))


def find_latest_available(shop: str, item_name: str) -> Optional[ShopRecord]:
    query = QUERY.format(shop, item_name)
    results = _get_container().query_items(query, enable_cross_partition_query=True)
    for r in results:
        return ShopRecord(
            id=r["id"],
            shop=r["shop"],
            item_name=r["item_name"],
            url=r["url"],
            available=r["available"],
            time_stamp=r["time_stamp"])
    else:
        return None
